"""Real Shield producer wiring tests without starting a SIEM receiver."""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.alerts.models import AlertEvent, Severity
from app.integrations.edy_siem.mapper import EventMapper
from app.integrations.edy_siem.outbox import OutboxRepository
from app.integrations.edy_siem.producer import SiemProducer
from app.plugins import ScanContext
from app.services.alert_service import AlertService
from app.ui.server import build_default_manager


def test_real_fim_hash_and_alert_flows_persist_offline(tmp_path: Path) -> None:
    db_path = tmp_path / "shield.db"
    monitored = tmp_path / "monitored"
    monitored.mkdir()
    artifact = monitored / "artifact.txt"
    artifact.write_text("version one", encoding="utf-8")

    repository = OutboxRepository(db_path)
    producer = SiemProducer(repository, EventMapper(repository.instance_id(), "host-1"))
    manager = build_default_manager(
        fim_dir=tmp_path / "fim",
        db_path=db_path,
        siem_producer=producer,
    )

    baseline_result = manager.run(
        "file_integrity",
        ScanContext(target=monitored, options={"action": "baseline"}),
    )
    baseline_id = baseline_result.observations[0].removeprefix("Baseline: ")
    artifact.write_text("version two", encoding="utf-8")
    manager.run(
        "file_integrity",
        ScanContext(
            target=monitored,
            options={"action": "scan", "baseline_id": baseline_id},
        ),
    )

    manager.run(
        "hash_checker",
        ScanContext(
            target=artifact,
            options={"algorithm": "SHA256", "expected": hashlib.sha256(b"wrong").hexdigest()},
        ),
    )

    alerts = AlertService(db_path=db_path, telemetry_sink=producer.enqueue_alert)
    alert = alerts.process_and_store(
        AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="artifact.txt",
            data={"event_type": "file_modified"},
        )
    )
    assert alert is not None
    alerts.acknowledge_alert(alert.alert_id, acked_by="analyst")

    event_types = [row["event_type"] for row in repository.list_status("pending")]
    assert "shield.fim.baseline.created" in event_types
    assert "shield.fim.file.modified" in event_types
    assert "shield.fim.scan.completed" in event_types
    assert "shield.hash.mismatch" in event_types
    assert "shield.alert.created" in event_types
    assert "shield.alert.updated" in event_types
    assert repository.count("pending") == len(event_types)

    alerts.close()
    repository.close()


def test_enqueue_failure_never_breaks_local_hash_scan(tmp_path: Path) -> None:
    repository = OutboxRepository(tmp_path / "shield.db")
    producer = SiemProducer(repository, EventMapper(repository.instance_id(), "host-1"))
    manager = build_default_manager(db_path=tmp_path / "shield.db", siem_producer=producer)
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"safe local operation")
    repository.close()

    result = manager.run(
        "hash_checker",
        ScanContext(
            target=artifact,
            options={"algorithm": "SHA256", "expected": "0" * 64},
        ),
    )
    assert "Hash SHA256 calculado com sucesso" in result.summary
    assert result.findings[-1].severity.value == "HIGH"
