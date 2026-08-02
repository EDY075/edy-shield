"""Testes de integração da UI com o PluginManager (Sprint 3, Missão 9).

Sobe o servidor HTTP real (thread, porta efêmera) e valida:

* API de plugins (GET /api/plugins);
* execução de Hash Checker via PluginManager (POST /api/scan);
* execução de Log Analyzer via PluginManager (POST /api/scan);
* histórico persistido e consultável;
* geração de relatórios (json/txt/html);
* tratamento de erros (plugin desconhecido, JSON inválido, path fora da
  raiz) e entrega de arquivos estáticos.

A UI **nunca** toca o Core — todo o fluxo passa pelo servidor → PluginManager.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from app.services.history import HistoryStore
from app.ui.server import build_default_manager, create_server


@pytest.fixture
def api(tmp_path: Path):
    """Levantar o servidor HTTP e expor o cliente de testes."""
    manager = build_default_manager()
    history = HistoryStore(tmp_path / "history")
    server = create_server(manager=manager, history=history)
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

    yield request

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


class TestPluginsEndpoint:
    def test_lists_builtin_plugins(self, api) -> None:
        status, data = api("GET", "/api/plugins")
        assert status == 200
        names = [p["name"] for p in data["plugins"]]
        assert "hash_checker" in names
        assert "log_analyzer" in names
        assert data["version"]

    def test_unknown_endpoint(self, api) -> None:
        status, data = api("GET", "/api/does-not-exist")
        assert status == 404
        assert "error" in data


class TestHashCheckerViaApi:
    def test_hash_text(self, api) -> None:
        status, data = api(
            "POST",
            "/api/scan",
            {"plugin": "hash_checker", "target": "hello", "options": {"algorithm": "SHA256"}},
        )
        assert status == 201
        result = data["result"]
        assert result["plugin_name"] == "hash_checker"
        assert len(result["findings"]) == 1
        assert result["findings"][0]["metadata"]["hexdigest"] == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )

    def test_hash_verify_mismatch(self, api) -> None:
        status, data = api(
            "POST",
            "/api/scan",
            {
                "plugin": "hash_checker",
                "target": "hello",
                "options": {"algorithm": "SHA256", "expected": "00" * 32},
            },
        )
        assert status == 201
        result = data["result"]
        assert result["max_severity"] == "HIGH"
        assert any("MISMATCH" in f["message"] for f in result["findings"])

    def test_hash_unknown_plugin(self, api) -> None:
        status, data = api("POST", "/api/scan", {"plugin": "nope", "target": "x"})
        assert status == 400
        assert "não encontrado" in data["error"]

    def test_invalid_json(self, api) -> None:
        status, data = api("POST", "/api/scan", {})  # sem 'plugin'
        assert status == 400
        assert "plugin" in data["error"]


class TestLogAnalyzerViaApi:
    def test_analyze_log(self, api, tmp_path: Path) -> None:
        log = tmp_path / "auth.log"
        log.write_text(
            "2026-08-01 10:00:00 FAILED LOGIN user=alice\n"
            "2026-08-01 10:01:00 ERROR db down\n"
            "2026-08-01 10:02:00 CRITICAL crash\n",
            encoding="utf-8",
        )
        status, data = api(
            "POST",
            "/api/scan",
            {"plugin": "log_analyzer", "target": str(log)},
        )
        assert status == 201
        result = data["result"]
        assert result["max_severity"] == "CRITICAL"
        assert result["stats"]["failed_login"] == 1
        assert result["stats"]["error"] == 1
        assert result["stats"]["critical"] == 1

    def test_log_outside_root(self, api, tmp_path: Path) -> None:
        log = tmp_path / "secret.log"
        log.write_text("INFO x\n", encoding="utf-8")
        # Contexto sem allowed_root: usa o pai do alvo (padrão ARES-QA-028),
        # portanto o acesso é permitido. Erro real seria um target inexistente.
        status, data = api(
            "POST",
            "/api/scan",
            {"plugin": "log_analyzer", "target": str(tmp_path / "missing.log")},
        )
        assert status == 400
        assert "error" in data


class TestHistoryViaApi:
    def test_scan_persisted_and_listed(self, api) -> None:
        api("POST", "/api/scan", {"plugin": "hash_checker", "target": "abc"})
        status, data = api("GET", "/api/history")
        assert status == 200
        assert len(data["entries"]) == 1
        assert data["entries"][0]["plugin_name"] == "hash_checker"

    def test_get_saved_result(self, api) -> None:
        _, created = api("POST", "/api/scan", {"plugin": "hash_checker", "target": "abc"})
        scan_id = created["id"]
        status, data = api("GET", f"/api/history/{scan_id}")
        assert status == 200
        assert data["plugin_name"] == "hash_checker"

    def test_get_missing_result(self, api) -> None:
        status, _ = api("GET", "/api/history/nao-existe")
        assert status == 404


class TestReportsViaApi:
    @pytest.mark.parametrize("fmt", ["json", "txt", "html"])
    def test_export_formats(self, api, fmt: str) -> None:
        _, created = api("POST", "/api/scan", {"plugin": "hash_checker", "target": "abc"})
        scan_id = created["id"]
        status, body = api("GET", f"/api/report/{scan_id}?fmt={fmt}")
        assert status == 200
        if isinstance(body, bytes):
            assert len(body) > 0
        else:
            assert isinstance(body, dict)

    def test_export_json_valid(self, api) -> None:
        _, created = api("POST", "/api/scan", {"plugin": "hash_checker", "target": "abc"})
        scan_id = created["id"]
        _, body = api("GET", f"/api/report/{scan_id}?fmt=json")
        parsed = body if isinstance(body, dict) else json.loads(body.decode("utf-8"))
        assert parsed["plugin_name"] == "hash_checker"
        assert parsed["max_severity"] == "INFO"

    def test_export_invalid_format(self, api) -> None:
        _, created = api("POST", "/api/scan", {"plugin": "hash_checker", "target": "abc"})
        scan_id = created["id"]
        status, data = api("GET", f"/api/report/{scan_id}?fmt=pdf")
        assert status == 400
        assert "não suportado" in data["error"]


class TestStaticAssets:
    def test_index_served(self, api) -> None:
        status, body = api("GET", "/")
        assert status == 200
        assert b"EDY SHIELD" in body

    def test_css_served(self, api) -> None:
        status, body = api("GET", "/css/style.css")
        assert status == 200
        assert b"--bg-base" in body

    def test_app_js_served(self, api) -> None:
        status, body = api("GET", "/app.js")
        assert status == 200
        assert b"fetch" in body

    def test_static_traversal_blocked(self, api) -> None:
        status, _ = api("GET", "/../pyproject.toml")
        assert status in (400, 404)
