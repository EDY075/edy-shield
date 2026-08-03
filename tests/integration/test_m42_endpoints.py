"""Testes de integração dos novos endpoints da M4.2 — Blue Team Overview.

Valida que os endpoints de API adicionados na sprint M4.2 funcionam
corretamente:

* ``GET /api/alerts`` — listar alertas com filtros.
* ``GET /api/alerts/stats`` — estatísticas agregadas (store + engine).
* ``GET /api/alerts/rules`` — regras ativas do motor de alertas.
* ``GET /api/health`` — saúde do sistema (SQLite, analisadores, uptime).
* ``POST /api/alerts/{id}/{action}`` — ações de ciclo de vida (ack/resolve/suppress/reopen).
* Path traversal em ``/api/alerts/`` rejeitado (404).

Nenhuma regressão nos endpoints existentes.
"""

from __future__ import annotations

import contextlib
import json
import os
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app.core.alerts.models import AlertEvent, AlertSource, Severity
from app.services.alert_service import AlertService
from app.services.history import HistoryStore
from app.ui.server import build_default_manager, create_server


def _close_resources(manager, history, alert_service) -> None:
    """Fechar conexões SQLite ao fim de cada teste."""
    history.close()
    alert_service.close()
    with contextlib.suppress(Exception):
        manager.registry.get("file_integrity").store.close()  # type: ignore[attr-defined]


@pytest.fixture
def m42_api(tmp_path: Path):
    """Levantar o servidor HTTP com AlertService para testes M4.2."""
    db_path = tmp_path / "test.db"
    os.environ["EDYSHIELD_DB_PATH"] = str(db_path)
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=db_path)
    history = HistoryStore(tmp_path / "history", db_path=db_path)
    alert_service = AlertService(db_path=db_path)
    server = create_server(manager=manager, history=history, alert_service=alert_service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_port}"

    def request(method: str, path: str, body: dict | None = None) -> tuple[int, dict | bytes]:
        url = base_url + path
        data = None
        headers = {}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                if "json" in content_type:
                    return resp.status, json.loads(raw)
                return resp.status, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                return exc.code, json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return exc.code, raw

    # Pré-popular alertas para os testes terem dados
    _seed_alerts(alert_service)

    yield request

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    _close_resources(manager, history, alert_service)
    del os.environ["EDYSHIELD_DB_PATH"]


def _seed_alerts(service: AlertService) -> None:
    """Criar alguns alertas de teste no AlertService."""
    events = [
        AlertEvent(
            source=AlertSource.FIM,
            event_type="file_modified",
            severity=Severity.CRITICAL,
            target="/etc/passwd",
            data={"change_type": "modified", "event_type": "file_modified"},
        ),
        AlertEvent(
            source=AlertSource.STRING_ANALYZER,
            event_type="string_match",
            severity=Severity.HIGH,
            target="/app/config.yaml",
            data={"category": "secret", "match_count": 3, "event_type": "string_match"},
        ),
        AlertEvent(
            source=AlertSource.ENTROPY_ANALYZER,
            event_type="high_entropy",
            severity=Severity.MEDIUM,
            target="/tmp/suspicious.bin",
            data={"entropy": 7.2, "event_type": "high_entropy"},
        ),
    ]
    for event in events:
        service.process_and_store(event)


class TestAlertsListEndpoint:
    """GET /api/alerts — listar alertas."""

    def test_list_alerts_returns_200(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts")
        assert status == 200
        assert "alerts" in data
        assert "count" in data
        assert isinstance(data["alerts"], list)

    def test_list_alerts_with_severity_filter(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts?severity=CRITICAL")
        assert status == 200
        for alert in data["alerts"]:
            assert alert["severity"] == "CRITICAL"

    def test_list_alerts_with_status_filter(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts?status=NEW")
        assert status == 200
        for alert in data["alerts"]:
            assert alert["status"] == "NEW"

    def test_list_alerts_with_limit(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts?limit=2")
        assert status == 200
        assert data["count"] <= 2

    def test_list_alerts_invalid_severity_returns_200(self, m42_api) -> None:
        """Severidade inexistente simplesmente não filtra (None no backend)."""
        status, _data = m42_api("GET", "/api/alerts?severity=BOGUS")
        assert status == 200


class TestAlertStatsEndpoint:
    """GET /api/alerts/stats — estatísticas agregadas."""

    def test_stats_returns_200(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts/stats")
        assert status == 200
        assert "total" in data
        assert "by_status" in data
        assert "by_severity" in data
        assert "by_source" in data
        assert "engine_events_processed" in data
        assert "dedup_cache_size" in data

    def test_stats_total_is_int(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts/stats")
        assert status == 200
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_stats_by_severity_has_expected_keys(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts/stats")
        assert status == 200
        by_severity = data["by_severity"]
        assert isinstance(by_severity, dict)


class TestAlertRulesEndpoint:
    """GET /api/alerts/rules — regras ativas."""

    def test_rules_returns_200(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts/rules")
        assert status == 200
        assert "rules" in data
        assert "count" in data
        assert isinstance(data["rules"], list)
        assert data["count"] == len(data["rules"])

    def test_rules_have_expected_fields(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts/rules")
        assert status == 200
        if data["rules"]:
            rule = data["rules"][0]
            assert "rule_id" in rule
            assert "name" in rule
            assert "source" in rule
            assert "target_severity" in rule
            assert "enabled" in rule


class TestHealthEndpoint:
    """GET /api/health — saúde do sistema."""

    def test_health_returns_200(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/health")
        assert status == 200
        assert "status" in data
        assert "uptime_seconds" in data
        assert "sqlite" in data
        assert "analyzers" in data

    def test_health_sqlite_status(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/health")
        assert status == 200
        assert data["sqlite"]["status"] in ("ok", "error")

    def test_health_uptime_positive(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/health")
        assert status == 200
        assert data["uptime_seconds"] >= 0

    def test_health_python_version(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/health")
        assert status == 200
        assert "python_version" in data
        assert len(data["python_version"]) > 0

    def test_health_analyzers_count(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/health")
        assert status == 200
        assert isinstance(data["analyzers"]["count"], int)
        assert data["analyzers"]["count"] >= 0


class TestAlertActionsEndpoint:
    """POST /api/alerts/{id}/{action} — ações de ciclo de vida."""

    def test_alert_not_found_returns_400(self, m42_api) -> None:
        status, data = m42_api("POST", "/api/alerts/FAKE-001/ack", {"by": "test"})
        assert status == 400
        assert "error" in data

    def test_alert_action_unknown_action_returns_400(self, m42_api) -> None:
        status, data = m42_api("POST", "/api/alerts/FAKE-001/bogus", {})
        assert status == 400
        assert "error" in data

    def test_alert_ack_then_resolve(self, m42_api) -> None:
        # Buscar um alerta real
        status, data = m42_api("GET", "/api/alerts?limit=1")
        assert status == 200
        assert data["count"] > 0
        alert_id = data["alerts"][0]["alert_id"]

        # ACK
        status, data = m42_api("POST", f"/api/alerts/{alert_id}/ack", {"by": "analyst"})
        assert status == 200
        assert data["status"] == "ACKNOWLEDGED"
        assert data["acknowledged_by"] == "analyst"

        # Resolve
        status, data = m42_api(
            "POST",
            f"/api/alerts/{alert_id}/resolve",
            {"by": "analyst", "note": "Fixed"},
        )
        assert status == 200
        assert data["status"] == "RESOLVED"


class TestDashboardM42CssAndJs:
    """Validar que novos estilos e scripts M4.2 são servidos."""

    def test_dashboard_css_contains_light_theme(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/css/dashboard.css")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert '[data-theme="light"]' in text
        assert "theme-toggle" in text
        assert "quick-actions" in text
        assert "bar-chart" in text
        assert "timeline" in text

    def test_dashboard_js_app_contains_theme_toggle(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/app.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "edy-shield-theme" in text
        assert "localStorage" in text
        assert "EDY" in text
        assert "auto" in text.lower() or "AUTO_REFRESH" in text

    def test_dashboard_js_page_dashboard_has_real_api(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/dashboard.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "/api/alerts/stats" in text
        assert "/api/health" in text
        assert "quick-actions" in text
        assert "bar-chart" in text
        assert "timeline" in text
        assert "critical-banner" in text

    def test_dashboard_js_page_alerts_has_real_api(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/alerts.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "/api/alerts" in text
        assert "AlertsPage" in text

    def test_dashboard_js_page_health_has_real_api(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/health.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "/api/health" in text
        assert "HealthPage" in text

    def test_dashboard_js_page_rules_has_real_api(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/rules.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "/api/alerts/rules" in text
        assert "RulesPage" in text

    def test_dashboard_js_page_settings_has_theme(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/settings.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "setTheme" in text
        assert "edy-shield-theme" in text

    def test_dashboard_html_contains_theme_toggle(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "themeToggle" in text
        assert "onlineIndicator" in text


class TestNoRegressionM42:
    """Garantir que endpoints existentes continuam funcionando."""

    def test_plugins_still_works(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/plugins")
        assert status == 200
        assert "plugins" in data

    def test_dashboard_still_served(self, m42_api) -> None:
        status, _ = m42_api("GET", "/dashboard")
        assert status == 200

    def test_path_traversal_still_rejected(self, m42_api) -> None:
        status, _ = m42_api("GET", "/dashboard/../app.js")
        assert status == 404


class TestRouterLifecycleM42:
    """Validar lifecycle do Router SPA — onLoad, onUnload, fetch cancel\u00e1vel."""

    def test_router_js_has_on_load(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onLoad" in text
        assert "route.onLoad" in text

    def test_router_js_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text
        assert "prevRoute.onUnload" in text or "route.onUnload" in text

    def test_router_js_has_abort_controller(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "AbortController" in text
        assert "createSignal" in text
        assert "abortFetch" in text

    def test_router_js_same_route_guard(self, m42_api) -> None:
        """Router n\u00e3o recarrega se hash n\u00e3o mudou."""
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "currentRoute === hash" in text

    def test_router_js_try_catch_on_load(self, m42_api) -> None:
        """onLoad tem tratamento de erro (try/catch)."""
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "try" in text
        assert 'route.onLoad' in text

    def test_router_js_loading_global(self, m42_api) -> None:
        """Router mostra loading durante troca de p\u00e1gina."""
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "loading-container" in text or "spinner" in text

    def test_router_js_error_state_render(self, m42_api) -> None:
        """Erro de render mostra p\u00e1gina de erro em vez de crashar."""
        status, body = m42_api("GET", "/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "errorStateHTML" in text
        assert "Erro ao renderizar" in text

    def test_dashboard_page_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/dashboard.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text
        assert "removeEventListener" in text

    def test_alerts_page_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/alerts.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text

    def test_health_page_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/health.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text

    def test_rules_page_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/rules.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text

    def test_settings_page_has_on_unload(self, m42_api) -> None:
        status, body = m42_api("GET", "/dashboard/js/pages/settings.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "onUnload" in text

    def test_app_js_single_timer_pattern(self, m42_api) -> None:
        """app.js usa padr\u00e3o de timer \u00fanico (clear antes de set)."""
        status, body = m42_api("GET", "/dashboard/js/app.js")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else body
        assert "clearInterval" in text
        assert "setInterval" in text
        assert "edy-refresh" in text


class TestAlertBatchEndpoint:
    """POST /api/alerts/batch — ações em lote sobre alertas."""

    def test_batch_missing_fields_400(self, m42_api) -> None:
        status, data = m42_api("POST", "/api/alerts/batch", {})
        assert status == 400
        assert "error" in data

    def test_batch_empty_ids_400(self, m42_api) -> None:
        status, data = m42_api("POST", "/api/alerts/batch", {"alert_ids": [], "action": "ack"})
        assert status == 400
        assert "error" in data

    def test_batch_unknown_action_is_error(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts?limit=1")
        assert status == 200
        alerts = data["alerts"]
        if alerts:
            aid = alerts[0]["alert_id"]
            status, data = m42_api("POST", "/api/alerts/batch", {"alert_ids": [aid], "action": "nuke"})
            assert status == 200
            assert len(data["errors"]) > 0
            assert "error" in data["errors"][0]

    def test_batch_ack_then_resolve(self, m42_api) -> None:
        status, data = m42_api("GET", "/api/alerts?status=NEW&limit=5")
        assert status == 200
        ids = [a["alert_id"] for a in data["alerts"]]
        if not ids:
            return
        status, data = m42_api("POST", "/api/alerts/batch", {"alert_ids": ids[:2], "action": "ack", "by": "batch-test"})
        assert status == 200
        assert len(data["success"]) == len(ids[:2])
        assert len(data["errors"]) == 0
        status, data = m42_api("POST", "/api/alerts/batch", {"alert_ids": ids[:2], "action": "resolve", "note": "Batch test"})
        assert status == 200
        for s in data["success"]:
            assert s["status"] == "RESOLVED"
