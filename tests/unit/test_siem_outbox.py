"""Durability, lease and recovery tests for the SIEM outbox."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import app.integrations.edy_siem.outbox as outbox_module
from app.integrations.edy_siem.mapper import EventMapper
from app.integrations.edy_siem.outbox import OutboxCapacityError, OutboxRepository

NOW = datetime(2026, 8, 11, 20, tzinfo=UTC)


def _builder(mapper: EventMapper, marker: str = "one"):
    def build(sequence: int) -> dict[str, object]:
        return mapper._event(
            sequence=sequence,
            component="scanner",
            event_type="shield.fim.scan.completed",
            severity="info",
            timestamp=NOW,
            evidence={
                "baseline_id": "base-1",
                "scan_id": f"scan-{marker}",
                "details": {
                    "added": 0,
                    "modified": 0,
                    "removed": 0,
                    "unchanged": 1,
                    "ignored": 0,
                    "duration_ms": 1,
                },
            },
            metadata={"correlation_id": f"scan-{marker}"},
        )

    return build


def test_instance_id_persists_across_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "shield.db"
    first = OutboxRepository(db_path)
    instance_id = first.instance_id()
    first.close()
    second = OutboxRepository(db_path)
    assert second.instance_id() == instance_id
    second.close()


def test_enqueue_lease_retry_sent_and_dead_letter(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")
    first_id, second_id = repo.enqueue(
        [_builder(mapper, "one"), _builder(mapper, "two")], now=NOW
    )
    assert repo.count("pending") == 2
    original_payload = repo.get(first_id)["payload"]  # type: ignore[index]

    batch = repo.lease(now=NOW, limit=1)
    assert batch is not None
    assert batch.items[0].event_id == first_id
    assert batch.items[0].attempt_count == 1
    assert repo.get(first_id)["status"] == "in_flight"  # type: ignore[index]
    assert repo.get(first_id)["payload"] == original_payload  # type: ignore[index]

    retry_at = NOW + timedelta(seconds=10)
    repo.retry_at([first_id], retry_at, "network offline", now=NOW)
    retried = repo.get(first_id)
    assert retried is not None
    assert retried["status"] == "pending"
    assert retried["attempt_count"] == 1
    assert retried["next_attempt_at"] == "2026-08-11T20:00:10.000Z"
    assert repo.lease(now=NOW, limit=1).items[0].event_id == second_id  # type: ignore[union-attr]

    repo.mark_sent([second_id], now=NOW)
    repo.mark_dead_letter([first_id], "invalid contract", now=retry_at)
    assert repo.get(second_id)["status"] == "sent"  # type: ignore[index]
    assert repo.get(first_id)["status"] == "dead_letter"  # type: ignore[index]
    repo.close()


def test_expired_in_flight_lease_recovers_after_crash(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")
    event_id = repo.enqueue([_builder(mapper)], now=NOW)[0]
    first = repo.lease(now=NOW, lease_seconds=30)
    assert first is not None
    assert repo.lease(now=NOW + timedelta(seconds=29)) is None
    recovered = repo.lease(now=NOW + timedelta(seconds=31))
    assert recovered is not None
    assert recovered.items[0].event_id == event_id
    assert recovered.items[0].attempt_count == 2
    repo.close()


def test_payload_over_64_kib_goes_directly_to_dead_letter(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")

    def oversized(sequence: int) -> dict[str, object]:
        event = _builder(mapper)(sequence)
        event["metadata"] = {"x_padding": "x" * (65 * 1024)}
        return event

    event_id = repo.enqueue([oversized], now=NOW)[0]
    item = repo.get(event_id)
    assert item is not None
    assert item["status"] == "dead_letter"
    assert "64 KiB" in item["last_error"]
    repo.close()


def test_batch_is_limited_to_100_events(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")
    repo.enqueue([_builder(mapper, str(i)) for i in range(101)], now=NOW)
    batch = repo.lease(now=NOW, limit=1000)
    assert batch is not None
    assert len(batch.items) == 100
    assert len(json.dumps(batch.envelope()).encode()) < 1024 * 1024
    assert repo.count("pending") == 1
    repo.close()


def test_concurrent_enqueue_allocates_unique_sequences(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(
            pool.map(
                lambda marker: repo.enqueue([_builder(mapper, marker)], now=NOW)[0],
                [str(index) for index in range(20)],
            )
        )
    assert len(set(ids)) == 20
    sequences = {repo.get(event_id)["sequence"] for event_id in ids}  # type: ignore[index]
    assert sequences == set(range(1, 21))
    repo.close()


def test_capacity_limit_preserves_existing_events_and_audits_drop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(outbox_module, "MAX_OUTBOX_EVENTS", 1)
    repo = OutboxRepository(tmp_path / "shield.db")
    mapper = EventMapper(repo.instance_id(), "host-1")
    first_id = repo.enqueue([_builder(mapper, "first")], now=NOW)[0]
    with pytest.raises(OutboxCapacityError):
        repo.enqueue([_builder(mapper, "second")], now=NOW)
    assert repo.count() == 1
    assert repo.get(first_id) is not None
    state = repo.integration_state()
    assert state["dropped_count"] == 1
    assert state["last_enqueue_error"] == "outbox capacity reached"
    repo.close()
