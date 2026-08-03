"""Testes de integração do Dashboard M4.1 (SPA SOC/SIEM).

Valida que o servidor HTTP serve corretamente:

* ``GET /dashboard`` — HTML principal do dashboard.
* ``GET /dashboard/css/dashboard.css`` — CSS do tema dark.
* ``GET /dashboard/js/app.js`` — Bootstrap JS.
* ``GET /dashboard/js/router.js`` — Router SPA.
* ``GET /dashboard/js/components/toast.js`` — Toast system.
* ``GET /dashboard/nonexistent`` — 404 para assets inexistentes.
* ``GET /dashboard/../secret`` — Path traversal rejeitado (404).

Os testesExisting API endpoints continuam funcionando (nenhuma regressão).
"""

from __future__ import annotations

import contextlib
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app.services.history import HistoryStore
from app.ui.server import build_default_manager, create_server


def _close_resources(manager, history) -> None:
    history.close()
    with contextlib.suppress(Exception):
        manager.registry.get("file_integrity").store.close()  # type: ignore[attr-defined]


@pytest.fixture
def dash(tmp_path: Path):
    """Levantar o servidor HTTP e expor o cliente de testes do dashboard."""
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db")
    history = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
    server = create_server(manager=manager, history=history)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_port}"

    def get(path: str) -> tuple[int, bytes]:
        url = base_url + path
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    yield {"get": get, "base_url": base_url}

    server.shutdown()
    server.server_close()
    _close_resources(manager, history)


class TestDashboardServing:
    """Servir arquivos do dashboard via rota /dashboard."""

    def test_dashboard_html(self, dash) -> None:
        """GET /dashboard deve retornar HTML 200 com o layout SPA."""
        status, body = dash["get"]("/dashboard")
        assert status == 200
        text = body.decode("utf-8")
        assert "<html" in text.lower()
        assert "EDY Shield" in text
        assert "sidebar" in text.lower()
        assert "app-layout" in text

    def test_dashboard_html_trailing_slash(self, dash) -> None:
        """GET /dashboard/ (com slash) tambem deve funcionar."""
        status, _ = dash["get"]("/dashboard/")
        assert status == 200

    def test_dashboard_css(self, dash) -> None:
        """GET /dashboard/css/dashboard.css deve servir o CSS do tema dark."""
        status, body = dash["get"]("/dashboard/css/dashboard.css")
        assert status == 200
        text = body.decode("utf-8")
        assert "--bg-base" in text
        assert "sidebar" in text
        assert "toast" in text

    def test_dashboard_js_app(self, dash) -> None:
        """GET /dashboard/js/app.js deve servir o bootstrap."""
        status, body = dash["get"]("/dashboard/js/app.js")
        assert status == 200
        text = body.decode("utf-8")
        assert "DOMContentLoaded" in text
        assert "Router" in text

    def test_dashboard_js_router(self, dash) -> None:
        """GET /dashboard/js/router.js deve servir o router SPA."""
        status, body = dash["get"]("/dashboard/js/router.js")
        assert status == 200
        text = body.decode("utf-8")
        assert "Router" in text
        assert "register" in text
        assert "navigate" in text
        assert "onLoad" in text

    def test_dashboard_js_toast(self, dash) -> None:
        """GET /dashboard/js/components/toast.js deve servir o toast system."""
        status, body = dash["get"]("/dashboard/js/components/toast.js")
        assert status == 200
        text = body.decode("utf-8")
        assert "Toast" in text
        assert "toast-container" in text

    def test_dashboard_js_components(self, dash) -> None:
        """GET /dashboard/js/components/components.js deve servir os componentes."""
        status, body = dash["get"]("/dashboard/js/components/components.js")
        assert status == 200
        text = body.decode("utf-8")
        assert "Components" in text
        assert "loadingHTML" in text
        assert "statCardHTML" in text

    def test_dashboard_page_scripts(self, dash) -> None:
        """Todos os scripts de pagina devem ser servidos."""
        pages = [
            "dashboard",
            "alerts",
            "rules",
            "assets",
            "logs",
            "ioc",
            "health",
            "settings",
        ]
        for page in pages:
            status, body = dash["get"](f"/dashboard/js/pages/{page}.js")
            assert status == 200, f"Page {page}.js should return 200, got {status}"
            assert "Router.register" in body.decode("utf-8")

    def test_dashboard_nonexistent_asset(self, dash) -> None:
        """GET /dashboard/nonexistent deve retornar 404."""
        status, _ = dash["get"]("/dashboard/nonexistent")
        assert status == 404

    def test_dashboard_path_traversal_rejected(self, dash) -> None:
        """Path traversal (..) deve ser rejeitado com 404."""
        status, _ = dash["get"]("/dashboard/../app.js")
        assert status == 404


class TestDashboardNoRegression:
    """Garantir que endpoints existentes continuam funcionando."""

    def test_root_still_works(self, dash) -> None:
        """GET / deve continuar servindo o index.html original."""
        status, _ = dash["get"]("/")
        assert status == 200

    def test_api_plugins_still_works(self, dash) -> None:
        """GET /api/plugins deve continuar retornando JSON."""
        status, body = dash["get"]("/api/plugins")
        assert status == 200
        data = json.loads(body)
        assert "plugins" in data

    def test_old_css_still_works(self, dash) -> None:
        """GET /css/style.css deve continuar servindo o CSS antigo."""
        status, _ = dash["get"]("/css/style.css")
        assert status == 200

    def test_old_app_js_still_works(self, dash) -> None:
        """GET /app.js deve continuar servindo o JS antigo."""
        status, _ = dash["get"]("/app.js")
        assert status == 200
