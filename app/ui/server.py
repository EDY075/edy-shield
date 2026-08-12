"""Servidor HTTP da UI do EDY Shield (Sprint 3, Missão 9).

Ponte entre a interface web e o PluginManager: expõe uma API REST mínima
(100% stdlib, sem framework) que a UI consome via ``fetch``. **Toda a lógica
de negócio vive nos plugins/serviços** — a interface apenas envia comandos
e recebe JSON; ela nunca chama o Core nem o filesystem diretamente.

Endpoints:

* ``GET  /``                     — dashboard (index.html)
* ``GET  /css/style.css``        — folha de estilos
* ``GET  /app.js``               — lógica de interface (fetch p/ API)
* ``GET  /api/plugins``          — lista plugins registrados
* ``POST /api/scan``             — executa um plugin (body: JSON)
* ``GET  /api/history``          — lista histórico de varreduras
* ``GET  /api/history/{id}``     — carrega um ScanResult salvo
* ``GET  /api/report/{id}?fmt=`` — gera relatório (json|txt|html)

Uso:

    from app.ui.server import create_server, serve
    serve(host="127.0.0.1", port=8000)
"""

from __future__ import annotations

import json
import os
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

from app import __version__
from app.core.alerts.models import AlertRecord
from app.core.fim import DEFAULT_FIM_DIR, FimStore
from app.integrations.edy_siem import IntegrationRuntime, SiemProducer, build_runtime
from app.plugins import PluginManager, PluginRegistry, ScanContext
from app.plugins.builtin import (
    EntropyAnalyzerPlugin,
    FileIntegrityPlugin,
    HashCheckerPlugin,
    LogAnalyzer,
    StringAnalyzerPlugin,
)
from app.plugins.plugin_errors import PluginError
from app.services import HistoryStore
from app.services.alert_service import AlertService, AlertServiceError
from app.services.analysis_service import AnalysisService
from app.services.report_engine import render

#: Timestamp de inicialização do servidor (para cálculo de uptime).
_START_TIME: float = time.time()

#: Diretório com os assets estáticos da UI.
STATIC_DIR = Path(__file__).resolve().parent / "static"

#: Diretório do Dashboard M4.1 (SPA SOC/SIEM).
DASHBOARD_DIR = STATIC_DIR / "dashboard"


def build_default_manager(
    fim_dir: Path | None = None,
    db_path: Path | None = None,
    siem_producer: SiemProducer | None = None,
) -> PluginManager:
    """Construir o PluginManager padrão com os plugins built-in.

    Args:
        fim_dir: Diretório legado do FimStore do plugin ``file_integrity``;
            ``None`` usa o padrão (``~/.edyshield/fim``).
        db_path: Caminho do banco SQLite do FimStore; ``None`` usa o padrão
            (``~/.edyshield/edy_shield.db``). Injetável para testes.

    Returns:
        Manager com ``log_analyzer``, ``hash_checker``,
        ``file_integrity``, ``string_analyzer`` e ``entropy_analyzer``
        registrados.
    """
    registry = PluginRegistry()
    registry.register(LogAnalyzer())
    registry.register(
        HashCheckerPlugin(
            telemetry_sink=siem_producer.enqueue_hash_scan if siem_producer else None
        )
    )
    registry.register(StringAnalyzerPlugin())
    registry.register(EntropyAnalyzerPlugin())
    store = FimStore(
        fim_dir if fim_dir is not None else DEFAULT_FIM_DIR,
        db_path=db_path,
    )
    registry.register(
        FileIntegrityPlugin(
            store,
            baseline_sink=siem_producer.enqueue_baseline if siem_producer else None,
            scan_sink=siem_producer.enqueue_fim_scan if siem_producer else None,
        )
    )
    return PluginManager(registry)


def create_server(
    *,
    manager: PluginManager | None = None,
    history: HistoryStore | None = None,
    alert_service: AlertService | None = None,
    siem_runtime: IntegrationRuntime | None = None,
    static_dir: Path = STATIC_DIR,
) -> ThreadingHTTPServer:
    """Criar o servidor HTTP (ThreadingHTTPServer) com os handlers.

    Args:
        manager: PluginManager a usar (padrão: built-in).
        history: HistoryStore a usar (padrão: diretório ``~/.edyshield``).
        alert_service: AlertService a usar (padrão: instância nova).
        static_dir: Diretório dos assets estáticos.

    Returns:
        Servidor HTTP pronto para ``serve_forever()``.
    """
    handler = _make_handler(manager, history, alert_service, static_dir, siem_runtime)
    return ThreadingHTTPServer(("127.0.0.1", 0), handler)


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    manager: PluginManager | None = None,
    history: HistoryStore | None = None,
    alert_service: AlertService | None = None,
    siem_runtime: IntegrationRuntime | None = None,
) -> None:
    """Iniciar o servidor HTTP em primeiro plano (bloqueante).

    Args:
        host: Endereço de bind.
        port: Porta de bind.
        manager: PluginManager a usar (padrão: built-in).
        history: HistoryStore a usar (padrão: ``~/.edyshield``).
        alert_service: AlertService a usar (padrão: instância nova).
    """
    runtime = siem_runtime if siem_runtime is not None else build_runtime()
    server: ThreadingHTTPServer | None = None
    try:
        if runtime is not None:
            runtime.start()
        handler = _make_handler(manager, history, alert_service, STATIC_DIR, runtime)
        server = ThreadingHTTPServer((host, port), handler)
        print(f"EDY Shield UI em http://{host}:{server.server_port} (v{__version__})")
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        if runtime is not None:
            runtime.close()


def _default_history_dir() -> Path:
    """Diretório padrão do histórico (``~/.edyshield``)."""
    return Path.home() / ".edyshield" / "history"


def _default_db_path() -> Path:
    """Caminho padrão do banco SQLite único."""
    from app.core.storage import DEFAULT_DB_PATH

    return DEFAULT_DB_PATH


def _make_handler(
    manager: PluginManager | None,
    history: HistoryStore | None,
    alert_service: AlertService | None,
    static_dir: Path,
    siem_runtime: IntegrationRuntime | None,
) -> type[BaseHTTPRequestHandler]:
    """Criar uma classe handler fechando o contexto da aplicação."""

    siem_producer = siem_runtime.producer if siem_runtime is not None else None
    app_manager = (
        manager
        if manager is not None
        else build_default_manager(siem_producer=siem_producer)
    )
    app_history = history if history is not None else HistoryStore(_default_history_dir())
    app_analysis = AnalysisService(manager=app_manager)
    # AlertService: injetável (testes) ou instância nova (produção).
    # Respeita EDYSHIELD_DB_PATH quando não injetada.
    if alert_service is not None:
        app_alerts = alert_service
    else:
        env_db = os.environ.get("EDYSHIELD_DB_PATH")
        app_alerts = AlertService(
            db_path=Path(env_db) if env_db else None,
            telemetry_sink=siem_producer.enqueue_alert if siem_producer else None,
        )
    assets = static_dir
    start_time = _START_TIME

    class EdyShieldHandler(BaseHTTPRequestHandler):
        """Handler HTTP da API do EDY Shield."""

        # Hardening M4.6: não expor stack Python/versão no header Server
        server_version = "EDYShield"
        sys_version = ""

        # Silence default logging for cleaner tests; logs go through
        # the application logger via the CLI instead.
        def log_message(self, format: str, *args: Any) -> None:
            """Sobrescrever para silenciar logging padrão do http.server."""

        def do_GET(self) -> None:
            """Roteador de requisições GET."""
            path = self.path.split("?", 1)[0]

            if path == "/":
                self._send_file(assets / "index.html", "text/html; charset=utf-8")
            elif path == "/icon.svg":
                self._send_file(assets / "icon.svg", "image/svg+xml; charset=utf-8")
            elif path == "/css/style.css":
                self._send_file(assets / "css" / "style.css", "text/css; charset=utf-8")
            elif path == "/app.js":
                self._send_file(assets / "app.js", "application/javascript; charset=utf-8")
            elif path == "/api/plugins":
                self._send_json({"plugins": app_manager.list_plugins(), "version": __version__})
            elif path == "/api/history":
                self._send_json({"entries": app_history.list()})
            elif path.startswith("/api/history/"):
                self._get_history_entry(path)
            elif path == "/api/analyze/history":
                self._get_analyze_history()
            elif path.startswith("/api/analyze/"):
                self._get_analyze_entry(path)
            elif path == "/api/alerts":
                self._get_alerts()
            elif path == "/api/alerts/stats":
                self._get_alert_stats()
            elif path == "/api/alerts/rules":
                self._get_alert_rules()
            elif path.startswith("/api/alerts/") and path.endswith("/comments"):
                self._get_alert_comments(path)
            elif path.startswith("/api/alerts/") and path.endswith("/related"):
                self._get_related_alerts(path)
            elif path.startswith("/api/alerts/") and "/export/" in path:
                self._get_alert_export(path)
            elif path.startswith("/api/alerts/"):
                self._get_alert_detail(path)
            elif path == "/api/health":
                self._get_health()
            elif path == "/api/fim/baselines":
                self._get_fim_baselines()
            elif path.startswith("/api/fim/baselines/"):
                self._get_fim_baseline(path)
            elif path.startswith("/api/report/"):
                self._get_report(path)
            elif path == "/dashboard" or path == "/dashboard/":
                self._send_file(DASHBOARD_DIR / "index.html", "text/html; charset=utf-8")
            elif path.startswith("/dashboard/"):
                self._serve_dashboard_asset(path)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint não encontrado")

        def do_POST(self) -> None:
            """Roteador de requisições POST."""
            path = self.path.split("?", 1)[0]
            if path == "/api/scan":
                self._post_scan()
            elif path == "/api/analyze":
                self._post_analyze()
            elif path == "/api/analyze/string":
                self._post_analyze_plugin("string_analyzer")
            elif path == "/api/analyze/entropy":
                self._post_analyze_plugin("entropy_analyzer")
            elif path == "/api/alerts/batch":
                self._post_alerts_batch()
            elif path.startswith("/api/alerts/") and path.endswith("/comment"):
                self._post_alert_comment(path)
            elif path.startswith("/api/alerts/") and "/" in path.removeprefix("/api/alerts/"):
                self._post_alert_action(path)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint não encontrado")

        # ------------------------------------------------------------------
        # Handlers internos
        # ------------------------------------------------------------------

        def _post_scan(self) -> None:
            """Executar um plugin com o payload JSON fornecido.

            Body: ``{"plugin": "...", "target": "...", "options": {...}}``.
            """
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, f"JSON inválido: {exc}")
                return

            plugin_name = payload.get("plugin")
            if not isinstance(plugin_name, str):
                self._send_error(HTTPStatus.BAD_REQUEST, "campo 'plugin' obrigatório")
                return

            context = ScanContext(
                target=payload.get("target"),
                options=payload.get("options") or {},
            )
            try:
                result = app_manager.run(plugin_name, context)
            except PluginError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            scan_id = app_history.save(result)
            self._send_json(
                {"id": scan_id, "result": result.as_dict()},
                status=HTTPStatus.CREATED,
            )

        def _get_history_entry(self, path: str) -> None:
            """Carregar um ScanResult salvo pelo id."""
            scan_id = path.removeprefix("/api/history/")
            if not scan_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            try:
                result = app_history.get(scan_id)
            except PluginError as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            if result is None:
                self._send_error(HTTPStatus.NOT_FOUND, "registro não encontrado")
                return
            self._send_json(result.as_dict())

        def _get_analyze_history(self) -> None:
            """Listar análises persistidas com filtros via querystring."""
            params = self._query_params()
            plugin = params.get("plugin")
            severity = params.get("severity")
            category = params.get("category")
            since = params.get("since")
            limit = int(params.get("limit", "100"))
            entries = app_analysis.history(
                plugin=plugin,
                severity=severity,
                category=category,
                since=since,
                limit=limit,
            )
            self._send_json({"entries": entries})

        def _get_analyze_entry(self, path: str) -> None:
            """Carregar uma análise completa pelo id."""
            analysis_id = path.removeprefix("/api/analyze/").split("/", 1)[0]
            if not analysis_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            try:
                record = app_analysis.get(analysis_id)
            except Exception as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            if record is None:
                self._send_error(HTTPStatus.NOT_FOUND, "análise não encontrada")
                return
            self._send_json(record)

        def _post_analyze(self) -> None:
            """Executar análise (String e/ou Entropy) com o payload JSON."""
            payload = self._read_analyze_payload()
            if isinstance(payload, dict) and "error" in payload:
                self._send_error(HTTPStatus.BAD_REQUEST, str(payload["error"]))
                return
            assert isinstance(payload, dict)

            target = payload.get("target")
            if not target:
                self._send_error(HTTPStatus.BAD_REQUEST, "campo 'target' obrigatório")
                return
            plugins: list[str] = payload.get("plugins") or ["string_analyzer", "entropy_analyzer"]
            recursive = bool(payload.get("recursive", False))
            categories = payload.get("categories")
            severity = payload.get("severity")
            persist = bool(payload.get("persist", True))

            try:
                outcomes = app_analysis.analyze(
                    target,
                    plugins=plugins,
                    recursive=recursive,
                    categories=categories,
                    severity=severity,
                    persist=persist,
                )
            except Exception as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json(
                {
                    "outcomes": [
                        {
                            "plugin_name": out.plugin_name,
                            "target": out.target,
                            "duration_ms": out.duration_ms,
                            "result": out.result.as_dict(),
                        }
                        for out in outcomes
                    ]
                },
                status=HTTPStatus.CREATED,
            )

        def _post_analyze_plugin(self, plugin_name: str) -> None:
            """Executar análise isolada de um plugin específico."""
            try:
                payload = self._read_json()
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, f"JSON inválido: {exc}")
                return

            target = payload.get("target")
            if not target:
                self._send_error(HTTPStatus.BAD_REQUEST, "campo 'target' obrigatório")
                return
            categories = payload.get("categories")
            severity = payload.get("severity")
            persist = bool(payload.get("persist", True))

            try:
                outcomes = app_analysis.analyze(
                    target,
                    plugins=[plugin_name],
                    categories=categories,
                    severity=severity,
                    persist=persist,
                )
            except Exception as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            self._send_json(
                {
                    "plugin_name": plugin_name,
                    "outcomes": [
                        {
                            "target": out.target,
                            "duration_ms": out.duration_ms,
                            "result": out.result.as_dict(),
                        }
                        for out in outcomes
                    ],
                },
                status=HTTPStatus.CREATED,
            )

        def _query_params(self) -> dict[str, str]:
            """Parsear querystring da requisição."""
            query = self.path.split("?", 1)
            if len(query) != 2:
                return {}
            return dict(part.split("=", 1) for part in query[1].split("&") if "=" in part)

        # ------------------------------------------------------------------
        # Handlers de API — Alertas e Health (M4.2)
        # ------------------------------------------------------------------

        def _get_alerts(self) -> None:
            """Listar alertas com filtros opcionais via querystring."""
            params = self._query_params()
            severity_str = params.get("severity")
            status_str = params.get("status")
            source = params.get("source")
            rule_id = params.get("rule_id")
            since = params.get("since")
            try:
                limit = int(params.get("limit", "50"))
            except ValueError:
                limit = 50
            try:
                offset = int(params.get("offset", "0"))
            except ValueError:
                offset = 0

            from app.core.alerts.models import AlertStatus, Severity

            try:
                severity = Severity(severity_str) if severity_str else None
            except ValueError:
                severity = None
            try:
                status = AlertStatus(status_str) if status_str else None
            except ValueError:
                status = None

            alerts = app_alerts.list_alerts(
                severity=severity,
                status=status,
                source=source,
                rule_id=rule_id,
                since=since,
                limit=limit,
                offset=offset,
            )
            # Filtro textual opcional (q) sobre title/target
            q = params.get("q", "").lower()
            if q:
                alerts = [
                    a
                    for a in alerts
                    if q in (a.title or "").lower()
                    or q in (a.target or "").lower()
                    or q in (a.alert_id or "").lower()
                    or q in (a.source or "").lower()
                ]
            self._send_json(
                {
                    "alerts": [a.to_dict() for a in alerts],
                    "count": len(alerts),
                }
            )

        def _get_alert_stats(self) -> None:
            """Retornar estatísticas agregadas dos alertas (store + engine)."""
            stats = app_alerts.stats()
            store = stats["store"]
            engine = stats["engine"]
            self._send_json(
                {
                    "total": store["total"],
                    "by_status": store["by_status"],
                    "by_severity": store["by_severity"],
                    "by_source": store["by_source"],
                    "engine_events_processed": engine.get("events_processed", 0),
                    "engine_alerts_created": engine.get("alerts_created", 0),
                    "engine_alerts_deduplicated": engine.get("alerts_deduplicated", 0),
                    "dedup_cache_size": stats["dedup_cache_size"],
                }
            )

        def _get_alert_detail(self, path: str) -> None:
            """Carregar um alerta pelo ID."""
            alert_id = path.removeprefix("/api/alerts/")
            if not alert_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            record = app_alerts.get_alert(alert_id)
            if record is None:
                self._send_error(HTTPStatus.NOT_FOUND, "alerta não encontrado")
                return
            self._send_json(record.to_dict())

        def _get_alert_rules(self) -> None:
            """Listar regras ativas do motor de alertas."""
            rules = app_alerts.list_rules()
            self._send_json(
                {
                    "rules": [
                        {
                            "rule_id": r.rule_id,
                            "name": r.name,
                            "source": r.source,
                            "condition_key": r.condition_key,
                            "operator": r.operator,
                            "condition_value": str(r.condition_value),
                            "target_severity": r.target_severity.value,
                            "enabled": r.enabled,
                            "priority": r.priority,
                            "suppression_window_seconds": r.suppression_window_seconds,
                        }
                        for r in rules
                    ],
                    "count": len(rules),
                }
            )

        def _post_alerts_batch(self) -> None:
            """Executar ação em lote sobre múltiplos alertas.

            Body: {"alert_ids": [...], "action": "ack|resolve|suppress", "note": "..."}
            """
            try:
                payload = self._read_json()
            except ValueError:
                self._send_error(HTTPStatus.BAD_REQUEST, "JSON inválido")
                return

            alert_ids: list[str] = payload.get("alert_ids", []) if isinstance(payload, dict) else []
            action: str = payload.get("action", "") if isinstance(payload, dict) else ""
            note: str = payload.get("note", "") if isinstance(payload, dict) else ""
            by: str = payload.get("by", "webui") if isinstance(payload, dict) else "webui"

            if not alert_ids or not action:
                self._send_error(HTTPStatus.BAD_REQUEST, "alert_ids e action são obrigatórios")
                return

            results: list[dict[str, object]] = []
            errors: list[dict[str, str]] = []
            for aid in alert_ids:
                try:
                    if action == "ack":
                        r = app_alerts.acknowledge_alert(aid, acked_by=by, note=note)
                    elif action == "resolve":
                        r = app_alerts.resolve_alert(aid, resolved_by=by, resolution_note=note)
                    elif action == "suppress":
                        r = app_alerts.suppress_alert(aid, reason=note)
                    elif action == "reopen":
                        r = app_alerts.reopen_alert(aid, reason=note)
                    else:
                        errors.append({"alert_id": aid, "error": f"ação desconhecida: {action}"})
                        continue
                    results.append(r.to_dict())
                except AlertServiceError as exc:
                    errors.append({"alert_id": aid, "error": str(exc)})

            self._send_json({"success": results, "errors": errors, "total": len(alert_ids)})

        def _post_alert_action(self, path: str) -> None:
            """Executar ação de ciclo de vida em um alerta (ack/resolve/suppress/reopen)."""
            parts = path.removeprefix("/api/alerts/").split("/", 1)
            if len(parts) != 2 or not parts[0]:
                self._send_error(
                    HTTPStatus.BAD_REQUEST, "formato esperado: /api/alerts/{id}/{action}"
                )
                return
            alert_id, action = parts[0], parts[1]

            try:
                payload = self._read_json()
            except ValueError:
                payload = {}

            note = payload.get("note", "") if isinstance(payload, dict) else ""
            by = payload.get("by", "webui") if isinstance(payload, dict) else "webui"

            try:
                if action == "ack":
                    record = app_alerts.acknowledge_alert(alert_id, acked_by=by, note=note)
                elif action == "resolve":
                    record = app_alerts.resolve_alert(
                        alert_id, resolved_by=by, resolution_note=note
                    )
                elif action == "suppress":
                    record = app_alerts.suppress_alert(alert_id, reason=note)
                elif action == "reopen":
                    record = app_alerts.reopen_alert(alert_id, reason=note)
                else:
                    self._send_error(HTTPStatus.BAD_REQUEST, f"ação desconhecida: {action}")
                    return
            except AlertServiceError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return
            self._send_json(record.to_dict())

        # --- M4.4 Investigation Workspace ---

        def _get_alert_comments(self, path: str) -> None:
            """Listar comentários de investigação de um alerta."""
            alert_id = path.removeprefix("/api/alerts/").replace("/comments", "")
            if not alert_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            comments = app_alerts.get_comments(alert_id)
            self._send_json({"comments": comments, "count": len(comments)})

        def _post_alert_comment(self, path: str) -> None:
            """Adicionar comentário de investigação a um alerta."""
            alert_id = path.removeprefix("/api/alerts/").replace("/comment", "")
            if not alert_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            try:
                payload = self._read_json()
            except ValueError:
                self._send_error(HTTPStatus.BAD_REQUEST, "JSON inválido")
                return
            author = payload.get("author", "analyst") if isinstance(payload, dict) else "analyst"
            body = payload.get("body", "") if isinstance(payload, dict) else ""
            if not body:
                self._send_error(HTTPStatus.BAD_REQUEST, "body é obrigatório")
                return
            comment = app_alerts.add_comment(alert_id, author, body)
            self._send_json(comment, status=HTTPStatus.CREATED)

        def _get_related_alerts(self, path: str) -> None:
            """Listar alertas com o mesmo fingerprint (eventos correlacionados)."""
            alert_id = path.removeprefix("/api/alerts/").replace("/related", "")
            if not alert_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return
            record = app_alerts.get_alert(alert_id)
            if record is None:
                self._send_error(HTTPStatus.NOT_FOUND, "alerta não encontrado")
                return
            related = app_alerts.list_related_alerts(record.fingerprint, exclude_id=alert_id)
            self._send_json(
                {
                    "related": [r.to_dict() for r in related],
                    "count": len(related),
                }
            )

        def _get_alert_export(self, path: str) -> None:
            """Exportar investigação de um alerta em Markdown ou JSON.

            Rota: /api/alerts/{id}/export/{format}
            """
            parts = path.removeprefix("/api/alerts/").split("/")
            if len(parts) != 3 or parts[1] != "export":
                self._send_error(
                    HTTPStatus.BAD_REQUEST, "formato: /api/alerts/{id}/export/{md|json}"
                )
                return
            alert_id, fmt = parts[0], parts[2]
            record = app_alerts.get_alert(alert_id)
            if record is None:
                self._send_error(HTTPStatus.NOT_FOUND, "alerta não encontrado")
                return
            comments = app_alerts.get_comments(alert_id)
            related = app_alerts.list_related_alerts(record.fingerprint, exclude_id=alert_id)

            if fmt == "json":
                self._send_json(
                    {
                        "alert": record.to_dict(),
                        "comments": comments,
                        "related": [r.to_dict() for r in related],
                    }
                )
                return

            if fmt == "md":
                md = _build_markdown_export(record, comments, related)
                self._send_bytes(
                    md.encode("utf-8"),
                    "text/markdown; charset=utf-8",
                )
                return

            self._send_error(HTTPStatus.BAD_REQUEST, f"formato não suportado: {fmt}")

        def _get_health(self) -> None:
            """Retornar saúde do sistema (CPU, memória, disco, SQLite, analisadores)."""
            import platform
            import sqlite3
            import sys

            from app.core.storage import DEFAULT_DB_PATH

            # Saúde do SQLite
            sqlite_ok = True
            sqlite_error: str | None = None
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=1)
                conn.execute("SELECT 1")
                conn.close()
            except Exception as exc:
                sqlite_ok = False
                sqlite_error = str(exc)

            # Plugins/analisadores ativos
            plugins = app_manager.list_plugins()

            # Eventos processados hoje (do engine stats)
            engine_stats = app_alerts.stats().get("engine", {})

            uptime_seconds = time.time() - start_time

            self._send_json(
                {
                    "status": "online" if sqlite_ok else "degraded",
                    "uptime_seconds": round(uptime_seconds, 1),
                    "python_version": sys.version.split()[0],
                    "platform": platform.platform(),
                    "sqlite": {
                        "status": "ok" if sqlite_ok else "error",
                        "error": sqlite_error,
                        "path": str(DEFAULT_DB_PATH),
                    },
                    "analyzers": {
                        "count": len(plugins),
                        "names": [p["name"] for p in plugins] if isinstance(plugins, list) else [],
                    },
                    "alert_engine": {
                        "events_processed": engine_stats.get("events_processed", 0),
                        "alerts_created": engine_stats.get("alerts_created", 0),
                        "alerts_deduplicated": engine_stats.get("alerts_deduplicated", 0),
                    },
                    "dedup_cache_size": app_alerts.stats().get("dedup_cache_size", 0),
                }
            )

        def _read_analyze_payload(self) -> dict[str, Any]:
            """Ler o payload do endpoint /api/analyze (JSON)."""
            try:
                return self._read_json()
            except ValueError:
                return {"error": "JSON inválido"}

        def _get_fim_baselines(self) -> None:
            """Listar metadados das baselines do FIM (dropdown da UI)."""
            store = self._fim_store()
            self._send_json({"baselines": store.list()})

        def _get_fim_baseline(self, path: str) -> None:
            """Carregar uma baseline pelo id (visualização/edição futura)."""
            baseline_id = path.removeprefix("/api/fim/baselines/")
            if not baseline_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "baseline_id ausente")
                return
            store = self._fim_store()
            try:
                baseline = store.load(baseline_id)
            except PluginError as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
                return
            except Exception as exc:
                self._send_error(HTTPStatus.NOT_FOUND, str(exc))
                return
            self._send_json(baseline.to_dict())

        def _fim_store(self) -> FimStore:
            """Obter o FimStore do plugin file_integrity registrado."""
            plugin = app_manager.registry.get("file_integrity")
            return cast(FimStore, plugin.store)  # type: ignore[attr-defined]

        def _get_report(self, path: str) -> None:
            """Gerar relatório (json|txt|html) de um ScanResult salvo."""
            scan_id = path.removeprefix("/api/report/")
            if not scan_id:
                self._send_error(HTTPStatus.BAD_REQUEST, "id ausente")
                return

            query = self.path.split("?", 1)
            fmt = "txt"
            if len(query) == 2:
                params = dict(part.split("=", 1) for part in query[1].split("&") if "=" in part)
                fmt = params.get("fmt", "txt")

            try:
                result = app_history.get(scan_id)
            except PluginError as exc:
                self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc))
                return
            if result is None:
                self._send_error(HTTPStatus.NOT_FOUND, "registro não encontrado")
                return

            try:
                content = render(result, fmt)
            except ValueError as exc:
                self._send_error(HTTPStatus.BAD_REQUEST, str(exc))
                return

            content_type = {
                "json": "application/json; charset=utf-8",
                "txt": "text/plain; charset=utf-8",
                "html": "text/html; charset=utf-8",
                "md": "text/markdown; charset=utf-8",
            }[fmt]
            self._send_bytes(content.encode("utf-8"), content_type)

        def _send_file(self, path: Path, content_type: str) -> None:
            """Servir um arquivo estático, se existir dentro do assets."""
            try:
                resolved = path.resolve()
                resolved.relative_to(assets.resolve())
            except (OSError, ValueError):
                self._send_error(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
                return
            if not resolved.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
                return
            self._send_bytes(resolved.read_bytes(), content_type)

        def _serve_dashboard_asset(self, path: str) -> None:
            """Servir um asset estático do Dashboard M4.1 (SPA).

            Mapeia ``/dashboard/css/dashboard.css`` -> ``DASHBOARD_DIR/css/dashboard.css``
            e alike para JS. Valida path traversal (contention dentro de DASHBOARD_DIR).
            """
            rel = path.removeprefix("/dashboard/")
            # Rejeitar path traversal (.., //, etc.)
            if ".." in rel or rel.startswith("/"):
                self._send_error(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
                return
            file_path = DASHBOARD_DIR / rel
            content_types = {
                ".css": "text/css; charset=utf-8",
                ".js": "application/javascript; charset=utf-8",
                ".html": "text/html; charset=utf-8",
                ".svg": "image/svg+xml; charset=utf-8",
                ".png": "image/png",
                ".ico": "image/x-icon",
            }
            ext = file_path.suffix.lower()
            ct = content_types.get(ext, "application/octet-stream")
            try:
                resolved = file_path.resolve()
                resolved.relative_to(DASHBOARD_DIR.resolve())
            except (OSError, ValueError):
                self._send_error(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
                return
            if not resolved.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "arquivo não encontrado")
                return
            self._send_bytes(resolved.read_bytes(), ct)

        def _read_json(self) -> dict[str, Any]:
            """Ler e decodificar o corpo JSON da requisição (limitado a 1MB)."""
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1024 * 1024:
                raise ValueError("payload excede o limite de 1MB")
            raw = self.rfile.read(length) if length else b""
            if not raw:
                return {}
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("payload deve ser um objeto JSON")
            return data

        def _send_json(self, data: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            """Responder com JSON."""
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_bytes(body, "application/json; charset=utf-8", status=status)

        def _send_bytes(
            self,
            body: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            """Responder com bytes e cabeçalhos padrão + Security Headers (M4.6)."""
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            # --- Hardening M4.6: Security Headers ---
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; "
                "base-uri 'self'; form-action 'self'",
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Permissions-Policy",
                "geolocation=(), microphone=(), camera=(), usb=()",
            )
            self.send_header("X-XSS-Protection", "1; mode=block")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            """Responder com erro JSON."""
            self._send_json(
                {"error": message, "status": int(status)},
                status=status,
            )

    return EdyShieldHandler


def _build_markdown_export(
    record: AlertRecord,
    comments: list[dict[str, Any]],
    related: list[AlertRecord],
) -> str:
    """Construir relatório Markdown de investigação de um alerta."""
    lines: list[str] = []
    lines.append(f"# Investigação — Alerta {record.alert_id}")
    lines.append("")
    lines.append(f"**Título:** {record.title}")
    lines.append(f"**Severidade:** {record.severity.value}")
    lines.append(f"**Status:** {record.status.value}")
    lines.append(f"**Origem:** {record.source}")
    lines.append(f"**Regra:** {record.rule_id}")
    lines.append(f"**Alvo:** {record.target}")
    lines.append(f"**Fingerprint:** `{record.fingerprint}`")
    lines.append(f"**Count:** {record.count}")
    lines.append(f"**Primeira Ocorrência:** {record.first_seen_at}")
    lines.append(f"**Última Ocorrência:** {record.last_seen_at}")
    lines.append("")
    if record.description:
        lines.append("## Descrição")
        lines.append(record.description)
        lines.append("")
    lines.append("## Detalhes / Evidências")
    lines.append("```json")
    lines.append(json.dumps(record.details, indent=2, ensure_ascii=False, default=str))
    lines.append("```")
    lines.append("")
    if comments:
        lines.append("## Comentários de Investigação")
        for c in comments:
            lines.append(f"### {c.get('author', 'N/A')} — {c.get('created_at', '')}")
            lines.append(c.get("body", ""))
            lines.append("")
    if related:
        lines.append("## Alertas Semelhantes (mesmo fingerprint)")
        for r in related:
            lines.append(
                f"- **{r.alert_id}** — {r.severity.value} — {r.status.value} — {r.last_seen_at}"
            )
        lines.append("")
    if record.acknowledged_at:
        lines.append("## Reconhecimento")
        lines.append(f"- **Por:** {record.acknowledged_by or 'N/A'}")
        lines.append(f"- **Quando:** {record.acknowledged_at}")
        lines.append("")
    if record.resolved_at:
        lines.append("## Resolução")
        lines.append(f"- **Por:** {record.resolved_by or 'N/A'}")
        lines.append(f"- **Quando:** {record.resolved_at}")
        if record.resolution_note:
            lines.append(f"- **Nota:** {record.resolution_note}")
        lines.append("")
    lines.append("---")
    lines.append("*Gerado por EDY Shield — Investigation Workspace (M4.4)*")
    return "\n".join(lines)


if __name__ == "__main__":
    serve()
