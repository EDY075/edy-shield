"""Contract-focused tests for real Shield fact mapping."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

from app import __version__
from app.core.alerts.models import AlertRecord
from app.core.alerts.models import Severity as AlertSeverity
from app.core.fim.models import Baseline, BaselineEntry, FimDiff, Snapshot
from app.integrations.edy_siem.mapper import EventMapper
from app.integrations.edy_siem.outbox import OutboxRepository
from app.integrations.edy_siem.producer import SiemProducer
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity

NOW = "2026-08-11T20:00:00Z"
A_HASH = "a" * 64
B_HASH = "b" * 64
C_HASH = "c" * 64


def _facts() -> tuple[Baseline, Snapshot, FimDiff]:
    baseline = Baseline(
        baseline_id="fim-baseline-1",
        algorithm="SHA256",
        created_at=NOW,
        root="C:/monitored",
        entries=(
            BaselineEntry("changed.txt", A_HASH, 10, NOW),
            BaselineEntry("removed.txt", B_HASH, 20, NOW),
        ),
    )
    snapshot = Snapshot(
        root=baseline.root,
        algorithm=baseline.algorithm,
        created_at=NOW,
        entries=(
            BaselineEntry("changed.txt", C_HASH, 11, NOW),
            BaselineEntry("new.txt", B_HASH, 12, NOW),
        ),
    )
    diff = FimDiff(
        baseline_id=baseline.baseline_id,
        algorithm=baseline.algorithm,
        scanned_at=NOW,
        added=("new.txt",),
        modified=("changed.txt",),
        removed=("removed.txt",),
    )
    return baseline, snapshot, diff


def _assert_common(event: dict[str, object], event_type: str) -> None:
    assert event["schema_version"] == "1.0"
    assert event["event_type"] == event_type
    assert event["timestamp"] == "2026-08-11T20:00:00.000Z"
    assert uuid.UUID(str(event["event_id"])).version == 4
    assert event["severity"] in {"info", "low", "medium", "high", "critical"}
    assert event["source"] == {
        "product": "edy-shield",
            "product_version": __version__,
        "instance_id": "00000000-0000-4000-8000-000000000001",
        "component": str(event_type).split(".")[1]
        if event_type.startswith("shield.hash")
        else ("alert_engine" if event_type.startswith("shield.alert") else "fim"),
    }
    assert isinstance(event["asset"], dict)
    assert isinstance(event["evidence"], dict)
    assert isinstance(event["metadata"], dict)


def test_maps_baseline_created() -> None:
    baseline, _, _ = _facts()
    event = EventMapper("00000000-0000-4000-8000-000000000001", "host-1").baseline_created(
        baseline, 1
    )
    _assert_common(event, "shield.fim.baseline.created")
    assert event["evidence"] == {
        "hash_algorithm": "sha256",
        "baseline_id": "fim-baseline-1",
        "baseline_status": "created",
        "details": {"file_count": 2},
    }


def test_maps_created_modified_and_deleted_files() -> None:
    baseline, snapshot, _ = _facts()
    mapper = EventMapper("00000000-0000-4000-8000-000000000001", "host-1")
    created = mapper.file_change(
        sequence=1,
        change="added",
        baseline=baseline,
        snapshot=snapshot,
        path="new.txt",
        scan_id="scan-1",
    )
    modified = mapper.file_change(
        sequence=2,
        change="modified",
        baseline=baseline,
        snapshot=snapshot,
        path="changed.txt",
        scan_id="scan-1",
    )
    deleted = mapper.file_change(
        sequence=3,
        change="removed",
        baseline=baseline,
        snapshot=snapshot,
        path="removed.txt",
        scan_id="scan-1",
    )

    _assert_common(created, "shield.fim.file.added")
    _assert_common(modified, "shield.fim.file.modified")
    _assert_common(deleted, "shield.fim.file.removed")
    assert created["evidence"]["current_hash"] == B_HASH  # type: ignore[index]
    assert modified["evidence"]["previous_hash"] == A_HASH  # type: ignore[index]
    assert modified["evidence"]["current_hash"] == C_HASH  # type: ignore[index]
    assert deleted["evidence"]["previous_hash"] == B_HASH  # type: ignore[index]
    assert "current_hash" not in deleted["evidence"]  # type: ignore[operator]


def test_maps_scan_completed() -> None:
    _, _, diff = _facts()
    event = EventMapper("00000000-0000-4000-8000-000000000001", "host-1").scan_completed(
        diff, "scan-1", 42, 4
    )
    _assert_common(event, "shield.fim.scan.completed")
    assert event["evidence"]["details"] == {  # type: ignore[index]
        "added": 1,
        "modified": 1,
        "removed": 1,
        "unchanged": 0,
        "ignored": 0,
        "duration_ms": 42,
    }


def test_maps_file_hash_mismatch_only(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    producer = SiemProducer(
        repo, EventMapper(repo.instance_id(), "host-1")
    )
    context = ScanContext(
        target=tmp_path / "artifact.bin",
        options={"algorithm": "SHA256", "expected": A_HASH},
    )
    result = ScanResult(
        plugin_name="hash_checker",
        plugin_version="2.0.0",
        timestamp=datetime(2026, 8, 11, 20, tzinfo=UTC),
        summary="mismatch",
        findings=(
            Evidence(
                Severity.INFO,
                "hash",
                metadata={"hexdigest": B_HASH, "source": "file"},
            ),
            Evidence(Severity.HIGH, "Verificacao: MISMATCH"),
        ),
    )
    event_id = producer.enqueue_hash_scan(context, result)[0]
    payload = repo.get(event_id)["payload"]  # type: ignore[index]
    assert payload["event_type"] == "shield.hash.mismatch"
    assert payload["evidence"]["file_path"] == "artifact.bin"
    assert payload["evidence"]["previous_hash"] == A_HASH
    assert payload["evidence"]["current_hash"] == B_HASH
    repo.close()


def test_does_not_export_hash_mismatch_for_text_input(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    producer = SiemProducer(repo, EventMapper(repo.instance_id(), "host-1"))
    result = ScanResult(
        plugin_name="hash_checker",
        plugin_version="2.0.0",
        timestamp=datetime.now(UTC),
        summary="mismatch",
        findings=(
            Evidence(
                Severity.INFO,
                "hash",
                metadata={"hexdigest": B_HASH, "source": "text"},
            ),
            Evidence(Severity.HIGH, "MISMATCH"),
        ),
    )
    assert producer.enqueue_hash_scan(
        ScanContext(target="plain text", options={"expected": A_HASH}), result
    ) == []
    repo.close()


def test_maps_security_alert_created_and_updated() -> None:
    mapper = EventMapper("00000000-0000-4000-8000-000000000001", "host-1")
    alert = AlertRecord(
        alert_id="ALT-1",
        fingerprint="f" * 64,
        title="Critical integrity alert",
        description="Protected artifact changed",
        source="fim",
        rule_id="FIM-001",
        severity=AlertSeverity.CRITICAL,
        first_seen_at=NOW,
        last_seen_at=NOW,
        details={
            "file_path": "config/app.ini",
            "previous_hash": "a" * 64,
            "current_hash": "b" * 64,
            "baseline_status": "modified",
            "mitre": ["T1565.001"],
        },
    )
    created = mapper.security_alert(alert, 1)
    updated = mapper.security_alert(alert, 2, action="updated", previous_status="NEW")
    _assert_common(created, "shield.alert.created")
    _assert_common(updated, "shield.alert.updated")
    assert created["severity"] == "critical"
    assert created["evidence"]["file_path"] == "config/app.ini"  # type: ignore[index]
    assert created["metadata"]["x_mitre"] == ["T1565.001"]  # type: ignore[index]
    assert updated["evidence"]["details"]["previous_status"] == "NEW"  # type: ignore[index]


def test_producer_maps_one_event_for_each_fim_fact(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    producer = SiemProducer(repo, EventMapper(repo.instance_id(), "host-1"))
    baseline, snapshot, diff = _facts()
    event_ids = producer.enqueue_fim_scan(baseline, snapshot, diff, "scan-1", 9)
    payloads = [repo.get(event_id)["payload"] for event_id in event_ids]  # type: ignore[index]
    assert [payload["event_type"] for payload in payloads] == [
        "shield.fim.file.added",
        "shield.fim.file.modified",
        "shield.fim.file.removed",
        "shield.fim.scan.completed",
    ]
    assert [payload["sequence"] for payload in payloads] == [1, 2, 3, 4]
    repo.close()
