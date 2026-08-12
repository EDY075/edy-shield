"""HTTP outcome and local-first resilience tests for SIEM delivery."""

from __future__ import annotations

import http.client
import random
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest

from app.integrations.edy_siem.client import (
    InvalidResponseError,
    SiemClient,
    SiemResponse,
    TransportError,
)
from app.integrations.edy_siem.config import INGEST_PATH, SiemConfig, integration_enabled
from app.integrations.edy_siem.mapper import EventMapper
from app.integrations.edy_siem.outbox import OutboxRepository
from app.integrations.edy_siem.producer import build_runtime
from app.integrations.edy_siem.worker import DeliveryWorker

NOW = datetime(2026, 8, 11, 20, tzinfo=UTC)
CONFIG = SiemConfig("http://127.0.0.1:9999", "t" * 32)


Outcome = SiemResponse | Exception | Callable[[dict[str, object]], SiemResponse]


class FakeClient:
    def __init__(self, outcomes: list[Outcome]) -> None:
        self.outcomes = outcomes
        self.envelopes: list[dict[str, object]] = []

    def send(self, envelope: dict[str, object]) -> SiemResponse:
        self.envelopes.append(envelope)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        if callable(outcome):
            return outcome(envelope)
        return outcome


def _enqueue(repo: OutboxRepository, count: int = 1) -> list[str]:
    mapper = EventMapper(repo.instance_id(), "host-1")

    def builder(sequence: int) -> dict[str, Any]:
        return mapper._event(
            sequence=sequence,
            component="scanner",
            event_type="shield.fim.scan.completed",
            severity="info",
            timestamp=NOW,
            evidence={
                "baseline_id": "base-1",
                "scan_id": f"scan-{sequence}",
                "details": {
                    "added": 0,
                    "modified": 0,
                    "removed": 0,
                    "unchanged": 1,
                    "ignored": 0,
                    "duration_ms": 1,
                },
            },
            metadata={},
        )

    return repo.enqueue([builder for _ in range(count)], now=NOW)


def _response_for(client: FakeClient, status: str, *, http_status: int = 202) -> None:
    def response(envelope: dict[str, object]) -> SiemResponse:
        events = cast(list[dict[str, Any]], envelope["events"])
        return SiemResponse(
            http_status,
            {
                "batch_id": envelope["batch_id"],
                "sent_at": "2026-08-11T20:00:00Z",
                "results": [{"event_id": event["event_id"], "status": status} for event in events],
            },
            None,
        )

    client.outcomes.append(response)


@pytest.mark.parametrize("item_status", ["accepted", "duplicate"])
def test_202_accepted_and_duplicate_are_delivered(tmp_path: Path, item_status: str) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    client = FakeClient([InvalidResponseError("prepare acknowledgement")])
    worker = DeliveryWorker(repo, cast(SiemClient, client), CONFIG, random_source=random.Random(0))
    assert worker.run_once(now=NOW)
    _response_for(client, item_status)
    assert worker.run_once(now=NOW.replace(second=1))
    assert repo.get(event_id)["status"] == "sent"  # type: ignore[index]
    repo.close()


def test_explicit_409_duplicate_is_delivered(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    client = FakeClient([TransportError("response lost")])
    worker = DeliveryWorker(repo, cast(SiemClient, client), CONFIG, random_source=random.Random(0))
    worker.run_once(now=NOW)
    _response_for(client, "duplicate", http_status=409)
    worker.run_once(now=NOW.replace(second=1))
    assert repo.get(event_id)["status"] == "sent"  # type: ignore[index]
    assert len(client.envelopes) == 2
    first_event = cast(list[dict[str, Any]], client.envelopes[0]["events"])[0]
    second_event = cast(list[dict[str, Any]], client.envelopes[1]["events"])[0]
    assert first_event["event_id"] == second_event["event_id"]
    repo.close()


@pytest.mark.parametrize("status", [401, 403])
def test_auth_rejection_preserves_event_without_retry_storm(tmp_path: Path, status: int) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    worker = DeliveryWorker(
        repo,
        cast(SiemClient, FakeClient([SiemResponse(status, {}, None)])),
        CONFIG,
    )
    worker.run_once(now=NOW)
    item = repo.get(event_id)
    assert item is not None
    assert item["status"] == "pending"
    assert item["next_attempt_at"] == "2026-08-11T20:15:00.000Z"
    repo.close()


@pytest.mark.parametrize("status", [400, 413, 422])
def test_structural_http_errors_dead_letter(tmp_path: Path, status: int) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    worker = DeliveryWorker(
        repo,
        cast(SiemClient, FakeClient([SiemResponse(status, {}, None)])),
        CONFIG,
    )
    worker.run_once(now=NOW)
    assert repo.get(event_id)["status"] == "dead_letter"  # type: ignore[index]
    repo.close()


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retryable_http_errors_are_rescheduled(tmp_path: Path, status: int) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    worker = DeliveryWorker(
        repo,
        cast(SiemClient, FakeClient([SiemResponse(status, {}, 12)])),
        CONFIG,
    )
    worker.run_once(now=NOW)
    item = repo.get(event_id)
    assert item is not None
    assert item["status"] == "pending"
    assert item["attempt_count"] == 1
    assert item["next_attempt_at"] == "2026-08-11T20:00:12.000Z"
    repo.close()


@pytest.mark.parametrize(
    "error",
    [
        TransportError("timeout"),
        TransportError("connection refused"),
        InvalidResponseError("invalid JSON"),
    ],
)
def test_transport_and_invalid_response_are_retryable(tmp_path: Path, error: Exception) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    worker = DeliveryWorker(
        repo,
        cast(SiemClient, FakeClient([error])),
        CONFIG,
        random_source=random.Random(0),
    )
    worker.run_once(now=NOW)
    assert repo.get(event_id)["status"] == "pending"  # type: ignore[index]
    repo.close()


def test_partially_accepted_batch_updates_each_item(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    first, second = _enqueue(repo, 2)
    client = FakeClient([InvalidResponseError("prepare acknowledgement")])
    worker = DeliveryWorker(repo, cast(SiemClient, client), CONFIG, random_source=random.Random(0))
    worker.run_once(now=NOW)

    def partial(envelope: dict[str, object]) -> SiemResponse:
        return SiemResponse(
            202,
            {
                "batch_id": envelope["batch_id"],
                "results": [
                    {"event_id": first, "status": "accepted"},
                    {"event_id": second, "status": "rejected"},
                ],
            },
            None,
        )

    client.outcomes.append(partial)
    worker.run_once(now=NOW.replace(second=1))
    assert repo.get(first)["status"] == "sent"  # type: ignore[index]
    assert repo.get(second)["status"] == "dead_letter"  # type: ignore[index]
    repo.close()


def test_offline_then_online_drains_same_durable_event(tmp_path: Path) -> None:
    repo = OutboxRepository(tmp_path / "shield.db")
    event_id = _enqueue(repo)[0]
    client = FakeClient([TransportError("offline")])
    worker = DeliveryWorker(repo, cast(SiemClient, client), CONFIG, random_source=random.Random(0))
    assert worker.run_once(now=NOW)
    assert repo.get(event_id)["status"] == "pending"  # type: ignore[index]
    _response_for(client, "accepted")
    assert worker.run_once(now=NOW.replace(second=1))
    assert repo.get(event_id)["status"] == "sent"  # type: ignore[index]
    repo.close()


def test_config_is_disabled_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("EDY_SIEM_ENABLED", raising=False)
    monkeypatch.delenv("EDY_SIEM_URL", raising=False)
    monkeypatch.delenv("EDY_SIEM_TOKEN", raising=False)
    assert integration_enabled() is False
    assert build_runtime(tmp_path / "not-created.db") is None
    assert not (tmp_path / "not-created.db").exists()


@pytest.mark.parametrize("failure", [TimeoutError(), ConnectionRefusedError()])
def test_http_client_wraps_timeout_and_connection_refused(
    monkeypatch: pytest.MonkeyPatch, failure: OSError
) -> None:
    class BrokenConnection:
        sock = None

        def connect(self) -> None:
            raise failure

        def close(self) -> None:
            pass

    monkeypatch.setattr(
        http.client,
        "HTTPConnection",
        lambda *_args, **_kwargs: BrokenConnection(),
    )
    client = SiemClient(CONFIG)
    with pytest.raises(TransportError):
        client.send({"batch_id": "batch-1", "sent_at": "now", "events": []})


def test_http_client_rejects_invalid_json_response() -> None:
    with pytest.raises(InvalidResponseError):
        SiemClient._decode_payload(b"not-json")


def test_valid_config_accepts_https_and_loopback_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDY_SIEM_ENABLED", "true")
    monkeypatch.setenv("EDY_SIEM_URL", "https://siem.example.test/")
    monkeypatch.setenv("EDY_SIEM_TOKEN", "s" * 32)
    config = SiemConfig.from_env()
    assert config.endpoint_url == f"https://siem.example.test{INGEST_PATH}"
    assert "s" * 32 not in repr(config)

    monkeypatch.setenv("EDY_SIEM_URL", "http://[::1]:8001")
    assert SiemConfig.from_env().base_url == "http://[::1]:8001"


@pytest.mark.parametrize(
    ("url", "token"),
    [
        ("", "s" * 32),
        ("http://siem.example.test", "s" * 32),
        ("ftp://127.0.0.1", "s" * 32),
        ("https://user:password@siem.example.test", "s" * 32),
        ("https://siem.example.test?token=bad", "s" * 32),
        ("https://siem.example.test", "short"),
        ("https://siem.example.test", "s" * 31 + "\n"),
    ],
)
def test_invalid_config_is_rejected(monkeypatch: pytest.MonkeyPatch, url: str, token: str) -> None:
    monkeypatch.setenv("EDY_SIEM_ENABLED", "true")
    monkeypatch.setenv("EDY_SIEM_URL", url)
    monkeypatch.setenv("EDY_SIEM_TOKEN", token)
    with pytest.raises(ValueError):
        SiemConfig.from_env()


def test_invalid_enabled_flag_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EDY_SIEM_ENABLED", "perhaps")
    with pytest.raises(ValueError):
        integration_enabled()
