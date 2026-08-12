"""Shield-side UX integration tests for delivery truth and safe deep links."""

from __future__ import annotations

import contextlib
import json
import threading
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.integrations.edy_siem import IntegrationRuntime, SiemProducer
from app.integrations.edy_siem.config import investigation_url
from app.integrations.edy_siem.mapper import EventMapper
from app.integrations.edy_siem.outbox import OutboxRepository
from app.services.history import HistoryStore
from app.ui.server import build_default_manager, create_server

NOW = datetime(2026, 8, 12, 12, tzinfo=UTC)


def _alert_builder(mapper: EventMapper, alert_id: str):
    def build(sequence: int) -> dict[str, object]:
        return mapper._event(
            sequence=sequence,
            component="alert-engine",
            event_type="shield.alert.created",
            severity="high",
            timestamp=NOW,
            evidence={"details": {"title": "FIM change"}},
            metadata={"shield_alert_id": alert_id},
        )

    return build


def _request(server, path: str) -> tuple[int, dict[str, object]]:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{server.server_port}{path}", timeout=5
    ) as response:
        return response.status, json.loads(response.read())


def test_delivered_alert_exposes_only_safe_configured_deep_link(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "shield.db"
    monkeypatch.setenv("EDYSHIELD_DB_PATH", str(db_path))
    monkeypatch.setenv("EDY_SIEM_ENABLED", "true")
    monkeypatch.setenv("EDY_SIEM_URL", "http://127.0.0.1:8001")
    monkeypatch.setenv("EDY_SIEM_UI_URL", "http://127.0.0.1:5173")
    monkeypatch.setenv("EDY_SIEM_TOKEN", "secret-token-that-must-never-reach-the-browser")
    repository = OutboxRepository(db_path)
    mapper = EventMapper(repository.instance_id(), "host-1")
    alert_id = "alert-ux-1"
    event_id = repository.enqueue([_alert_builder(mapper, alert_id)], now=NOW)[0]
    repository.mark_sent([event_id], now=NOW)
    runtime = IntegrationRuntime(SiemProducer(repository, mapper), None)
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=db_path)
    history = HistoryStore(tmp_path / "history", db_path=db_path)
    server = create_server(manager=manager, history=history, siem_runtime=runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        status, body = _request(server, f"/api/integrations/edy-siem/alerts/{alert_id}")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        history.close()
        with contextlib.suppress(Exception):
            manager.registry.get("file_integrity").store.close()  # type: ignore[attr-defined]
        repository.close()

    assert status == 200
    assert body["delivery_state"] == "delivered"
    assert body["can_investigate"] is True
    assert body["event_id"] == event_id
    assert body["investigation_url"] == f"http://127.0.0.1:5173/investigate/shield/{event_id}"
    assert "secret-token" not in json.dumps(body)


def test_deep_link_is_disabled_or_rejected_for_unsafe_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EDY_SIEM_ENABLED", "false")
    assert investigation_url("event") is None

    monkeypatch.setenv("EDY_SIEM_ENABLED", "true")
    monkeypatch.setenv("EDY_SIEM_UI_URL", "http://siem.example")
    assert investigation_url("event") is None

    monkeypatch.setenv("EDY_SIEM_UI_URL", "https://user:pass@siem.example")
    assert investigation_url("event") is None


def test_pending_temporary_failure_and_dead_letter_are_reported_truthfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "states.db"
    monkeypatch.setenv("EDYSHIELD_DB_PATH", str(db_path))
    monkeypatch.setenv("EDY_SIEM_ENABLED", "true")
    monkeypatch.setenv("EDY_SIEM_UI_URL", "http://127.0.0.1:5173")
    repository = OutboxRepository(db_path)
    mapper = EventMapper(repository.instance_id(), "host-1")
    alert_ids = ["alert-pending", "alert-retry", "alert-dead"]
    event_ids = repository.enqueue(
        [_alert_builder(mapper, alert_id) for alert_id in alert_ids], now=NOW
    )
    repository.retry_at(
        [event_ids[1]], NOW + timedelta(seconds=30), "SIEM temporarily offline", now=NOW
    )
    repository.mark_dead_letter([event_ids[2]], "contract rejected", now=NOW)
    runtime = IntegrationRuntime(SiemProducer(repository, mapper), None)
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=db_path)
    history = HistoryStore(tmp_path / "history", db_path=db_path)
    server = create_server(manager=manager, history=history, siem_runtime=runtime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        states = [
            _request(server, f"/api/integrations/edy-siem/alerts/{alert_id}")[1]
            for alert_id in alert_ids
        ]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        history.close()
        with contextlib.suppress(Exception):
            manager.registry.get("file_integrity").store.close()  # type: ignore[attr-defined]
        repository.close()

    assert [item["delivery_state"] for item in states] == [
        "pending",
        "temporary_failure",
        "failed",
    ]
    assert all(item["can_investigate"] is False for item in states)
    assert all(item["investigation_url"] is None for item in states)

def test_frontend_shows_real_delivery_states_and_opens_only_http_links() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "app" / "ui" / "static" / "dashboard" / "js" / "pages" / "alerts.js"
    ).read_text(encoding="utf-8")
    styles = (
        root / "app" / "ui" / "static" / "dashboard" / "css" / "dashboard.css"
    ).read_text(encoding="utf-8")
    for marker in (
        "delivery_state",
        "can_investigate",
        "Investigar no EDY SIEM",
        "^https?",
        "noopener,noreferrer",
    ):
        assert marker in source
    assert "state-temporary_failure" in styles
