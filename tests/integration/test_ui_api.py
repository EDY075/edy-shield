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

import contextlib
import json
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

from app.services.history import HistoryStore
from app.ui.server import build_default_manager, create_server


def _close_resources(manager, history) -> None:
    """Fechar conexões SQLite ao fim de cada teste (isolamento)."""
    history.close()
    with contextlib.suppress(Exception):
        manager.registry.get("file_integrity").store.close()  # type: ignore[attr-defined]


@pytest.fixture
def api(tmp_path: Path):
    """Levantar o servidor HTTP e expor o cliente de testes."""
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db")
    history = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
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
    _close_resources(manager, history)


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


@pytest.fixture
def fim_api(tmp_path: Path):
    """Servidor HTTP com FimStore temporário (FIM — Sprint 5)."""
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db")
    history = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
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
    _close_resources(manager, history)


def _make_target(tmp_path: Path) -> Path:
    root = tmp_path / "conf"
    root.mkdir(parents=True, exist_ok=True)
    (root / "app.ini").write_text("versao=1", encoding="utf-8")
    (root / "data.txt").write_text("dados", encoding="utf-8")
    return root


class TestFimViaApi:
    def test_plugin_listed(self, fim_api) -> None:
        status, data = fim_api("GET", "/api/plugins")
        assert status == 200
        names = [p["name"] for p in data["plugins"]]
        assert "file_integrity" in names

    def test_create_baseline(self, fim_api, tmp_path: Path) -> None:
        target = _make_target(tmp_path)
        status, data = fim_api(
            "POST",
            "/api/scan",
            {
                "plugin": "file_integrity",
                "target": str(target),
                "options": {"action": "baseline", "algorithm": "SHA256"},
            },
        )
        assert status == 201
        result = data["result"]
        assert result["plugin_name"] == "file_integrity"
        assert result["stats"]["entries"] == 2
        assert result["max_severity"] == "INFO"

    def test_baselines_listed(self, fim_api, tmp_path: Path) -> None:
        target = _make_target(tmp_path)
        fim_api(
            "POST",
            "/api/scan",
            {"plugin": "file_integrity", "target": str(target), "options": {"action": "baseline"}},
        )
        status, data = fim_api("GET", "/api/fim/baselines")
        assert status == 200
        assert len(data["baselines"]) == 1
        assert data["baselines"][0]["algorithm"] == "SHA256"

    def test_get_baseline_by_id(self, fim_api, tmp_path: Path) -> None:
        target = _make_target(tmp_path)
        _, created = fim_api(
            "POST",
            "/api/scan",
            {"plugin": "file_integrity", "target": str(target), "options": {"action": "baseline"}},
        )
        baseline_id = created["result"]["observations"][0].replace("Baseline: ", "")
        status, data = fim_api("GET", f"/api/fim/baselines/{baseline_id}")
        assert status == 200
        assert data["baseline_id"] == baseline_id
        assert len(data["entries"]) == 2

    def test_scan_detects_change(self, fim_api, tmp_path: Path) -> None:
        target = _make_target(tmp_path)
        _, created = fim_api(
            "POST",
            "/api/scan",
            {"plugin": "file_integrity", "target": str(target), "options": {"action": "baseline"}},
        )
        baseline_id = created["result"]["observations"][0].replace("Baseline: ", "")

        (target / "app.ini").write_text("versao=2", encoding="utf-8")
        (target / "novo.txt").write_text("novo", encoding="utf-8")
        (target / "data.txt").unlink()

        status, data = fim_api(
            "POST",
            "/api/scan",
            {
                "plugin": "file_integrity",
                "target": str(target),
                "options": {"action": "scan", "baseline_id": baseline_id},
            },
        )
        assert status == 201
        result = data["result"]
        assert result["stats"]["added"] == 1
        assert result["stats"]["modified"] == 1
        assert result["stats"]["removed"] == 1
        assert result["max_severity"] == "HIGH"

    def test_scan_missing_baseline_400(self, fim_api, tmp_path: Path) -> None:
        target = _make_target(tmp_path)
        status, data = fim_api(
            "POST",
            "/api/scan",
            {
                "plugin": "file_integrity",
                "target": str(target),
                "options": {"action": "scan", "baseline_id": "fim_sha256_20260802T000000Z"},
            },
        )
        assert status == 400
        assert "error" in data

    def test_report_markdown(self, fim_api) -> None:
        _, created = fim_api(
            "POST",
            "/api/scan",
            {"plugin": "hash_checker", "target": "abc"},
        )
        scan_id = created["id"]
        status, body = fim_api("GET", f"/api/report/{scan_id}?fmt=md")
        assert status == 200
        text = body.decode("utf-8") if isinstance(body, bytes) else str(body)
        assert "EDY SHIELD — Relatório" in text

    def test_get_missing_baseline_404(self, fim_api) -> None:
        status, _ = fim_api("GET", "/api/fim/baselines/fim_sha256_20260802T000000Z")
        assert status == 404


class TestServerEdgeEndpoints:
    """Endpoints reais em casos de borda (validação de comportamento)."""

    def test_icon_svg_served(self, api) -> None:
        status, body = api("GET", "/icon.svg")
        assert status == 200
        assert b"<svg" in body

    def test_post_unknown_endpoint_404(self, api) -> None:
        status, _data = api("POST", "/api/nao-existe", {"plugin": "x"})
        assert status == 404

    def test_scan_empty_body_400(self, api) -> None:
        status, data = api("POST", "/api/scan")
        assert status == 400
        assert "plugin" in data["error"]

    def test_history_entry_missing_id_400(self, api) -> None:
        status, data = api("GET", "/api/history/")
        assert status == 400
        assert "id ausente" in data["error"]

    def test_history_corrupted_entry_500(self, api, tmp_path: Path) -> None:
        # Corrompe um registro no HistoryStore (arquivo JSON inválido)
        history_dir = tmp_path / "history"
        history_dir.mkdir(parents=True, exist_ok=True)
        (history_dir / "corrompido.json").write_text("{invalid json", encoding="utf-8")

        status, data = api("GET", "/api/history/corrompido")
        assert status == 500
        assert "corrompido" in data["error"]

    def test_report_missing_id_400(self, api) -> None:
        status, data = api("GET", "/api/report/")
        assert status == 400
        assert "id ausente" in data["error"]

    def test_report_not_found_404(self, api) -> None:
        status, data = api("GET", "/api/report/nao-existe")
        assert status == 404
        assert "não encontrado" in data["error"]

    def test_css_missing_file_404(self, api) -> None:
        status, _ = api("GET", "/css/nao-existe.css")
        assert status == 404

    def test_static_app_missing_404(self, api) -> None:
        status, _ = api("GET", "/app.nope")
        assert status == 404


@pytest.fixture
def raw_api(tmp_path: Path):
    """Servidor com cliente que aceita corpo bruto (teste de JSON inválido)."""
    manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db")
    history = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")
    server = create_server(manager=manager, history=history)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{server.server_port}"

    def raw_request(method: str, path: str, body: bytes | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(base_url + path, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    yield raw_request

    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
    _close_resources(manager, history)


class TestRawJsonParsing:
    def test_scan_non_dict_json_400(self, raw_api) -> None:
        # Corpo JSON válido mas não-objeto → _read_json levanta ValueError
        status, data = raw_api("POST", "/api/scan", b"[1, 2, 3]")
        assert status == 400
        assert "JSON inválido" in data["error"] or "objeto JSON" in data["error"]

    def test_scan_malformed_json_400(self, raw_api) -> None:
        status, data = raw_api("POST", "/api/scan", b"{not json")
        assert status == 400
        assert "JSON inválido" in data["error"]


class TestFimBaselineEdge:
    def test_fim_baseline_missing_id_400(self, fim_api) -> None:
        status, data = fim_api("GET", "/api/fim/baselines/")
        assert status == 400
        assert "baseline_id ausente" in data["error"]


class TestAnalyzeApi:
    """Endpoints da M2.3 — análise integrada (String + Entropy)."""

    def test_analyze_string(self, api, tmp_path) -> None:
        f = tmp_path / "s.txt"
        f.write_text("the quick brown fox.\nhttp://evil.example.com/x\n", encoding="utf-8")
        status, data = api("POST", "/api/analyze/string", {"target": str(f), "persist": True})
        assert status == 201
        assert data["plugin_name"] == "string_analyzer"
        assert len(data["outcomes"]) == 1

    def test_analyze_entropy(self, api, tmp_path) -> None:
        f = tmp_path / "e.txt"
        f.write_text("plain text line here\n", encoding="utf-8")
        status, data = api("POST", "/api/analyze/entropy", {"target": str(f), "persist": True})
        assert status == 201
        assert data["plugin_name"] == "entropy_analyzer"

    def test_analyze_combined(self, api, tmp_path) -> None:
        f = tmp_path / "c.txt"
        f.write_text("hello world\nhttps://example.com/x\n", encoding="utf-8")
        status, data = api(
            "POST",
            "/api/analyze",
            {"target": str(f), "plugins": ["string_analyzer", "entropy_analyzer"]},
        )
        assert status == 201
        assert data["outcomes"][0]["plugin_name"] == "combined"

    def test_analyze_history(self, api, tmp_path) -> None:
        f = tmp_path / "h.txt"
        f.write_text("sample\n", encoding="utf-8")
        api("POST", "/api/analyze/string", {"target": str(f), "persist": True})
        status, data = api("GET", "/api/analyze/history?limit=50")
        assert status == 200
        assert any(e["plugin_name"] == "string_analyzer" for e in data["entries"])

    def test_analyze_history_without_query(self, api, tmp_path) -> None:
        f = tmp_path / "hq.txt"
        f.write_text("sample\n", encoding="utf-8")
        api("POST", "/api/analyze/string", {"target": str(f), "persist": True})
        # Sem querystring → _query_params retorna {} e usa limites padrão.
        status, data = api("GET", "/api/analyze/history")
        assert status == 200
        assert isinstance(data["entries"], list)

    def test_analyze_missing_target_400(self, api) -> None:
        status, data = api("POST", "/api/analyze/string", {"target": ""})
        assert status == 400
        assert "target" in data["error"]

    def test_get_analyze_by_id(self, api, tmp_path) -> None:
        f = tmp_path / "g.txt"
        f.write_text("plain sample\n", encoding="utf-8")
        _, _ = api("POST", "/api/analyze/string", {"target": str(f), "persist": True})
        target_id = None
        # Recupera via histórico para obter um id persistido.
        _, hist = api("GET", "/api/analyze/history?limit=100")
        for entry in hist["entries"]:
            if entry["plugin_name"] == "string_analyzer":
                target_id = entry["analysis_id"]
                break
        assert target_id is not None
        status, data = api("GET", f"/api/analyze/{target_id}")
        assert status == 200
        assert data["plugin_name"] == "string_analyzer"

    def test_get_analyze_nonexistent_404(self, api) -> None:
        status, _ = api("GET", "/api/analyze/ana_nao_existe")
        assert status == 404

    def test_get_analyze_empty_id_400(self, api) -> None:
        # Rota /api/analyze/{id} sem id → id ausente → 400
        status, data = api("GET", "/api/analyze/")
        assert status == 400
        assert "id ausente" in data["error"]

    def test_analyze_payload_missing_target_400(self, api) -> None:
        status, _ = api("POST", "/api/analyze", {})
        assert status == 400

    def test_analyze_combined_severity_option(self, api, tmp_path) -> None:
        f = tmp_path / "low.txt"
        f.write_text("the quick brown fox jumps over the lazy dog. " * 20, encoding="utf-8")
        status, data = api(
            "POST",
            "/api/analyze",
            {"target": str(f), "severity": "CRITICAL"},
        )
        assert status == 201
        assert data["outcomes"][0]["result"]["findings"] == []

    def test_analyze_bad_json_400(self, raw_api) -> None:
        status, data = raw_api("POST", "/api/analyze/string", b"{not json")
        assert status == 400
        assert "JSON inválido" in data["error"]

    def test_analyze_combined_bad_json_400(self, raw_api) -> None:
        status, data = raw_api("POST", "/api/analyze", b"{not json")
        assert status == 400
        assert "JSON inválido" in data["error"]

    def test_analyze_invalid_plugin_400(self, api, tmp_path) -> None:
        f = tmp_path / "z.txt"
        f.write_text("x\n", encoding="utf-8")
        status, _ = api("POST", "/api/analyze", {"target": str(f), "plugins": ["nao_existe"]})
        assert status == 400
