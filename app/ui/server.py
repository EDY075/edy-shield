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
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from app import __version__
from app.plugins import PluginManager, PluginRegistry, ScanContext
from app.plugins.builtin import HashCheckerPlugin, LogAnalyzer
from app.plugins.plugin_errors import PluginError
from app.services import HistoryStore
from app.services.report_engine import render

#: Diretório com os assets estáticos da UI.
STATIC_DIR = Path(__file__).resolve().parent / "static"

#: Formatos de relatório aceitos.
_REPORT_FORMATS = ("json", "txt", "html")


def build_default_manager() -> PluginManager:
    """Construir o PluginManager padrão com os plugins built-in.

    Returns:
        Manager com ``log_analyzer`` e ``hash_checker`` registrados.
    """
    registry = PluginRegistry()
    registry.register(LogAnalyzer())
    registry.register(HashCheckerPlugin())
    return PluginManager(registry)


def create_server(
    *,
    manager: PluginManager | None = None,
    history: HistoryStore | None = None,
    static_dir: Path = STATIC_DIR,
) -> ThreadingHTTPServer:
    """Criar o servidor HTTP (ThreadingHTTPServer) com os handlers.

    Args:
        manager: PluginManager a usar (padrão: built-in).
        history: HistoryStore a usar (padrão: diretório ``~/.edyshield``).
        static_dir: Diretório dos assets estáticos.

    Returns:
        Servidor HTTP pronto para ``serve_forever()``.
    """
    handler = _make_handler(manager, history, static_dir)
    return ThreadingHTTPServer(("127.0.0.1", 0), handler)


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    manager: PluginManager | None = None,
    history: HistoryStore | None = None,
) -> None:
    """Iniciar o servidor HTTP em primeiro plano (bloqueante).

    Args:
        host: Endereço de bind.
        port: Porta de bind.
        manager: PluginManager a usar (padrão: built-in).
        history: HistoryStore a usar (padrão: ``~/.edyshield``).
    """
    handler = _make_handler(manager, history, STATIC_DIR)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"EDY Shield UI em http://{host}:{server.server_port} (v{__version__})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _default_history_dir() -> Path:
    """Diretório padrão do histórico (``~/.edyshield``)."""
    return Path.home() / ".edyshield" / "history"


def _make_handler(
    manager: PluginManager | None,
    history: HistoryStore | None,
    static_dir: Path,
) -> type[BaseHTTPRequestHandler]:
    """Criar uma classe handler fechando o contexto da aplicação."""

    app_manager = manager if manager is not None else build_default_manager()
    app_history = history if history is not None else HistoryStore(_default_history_dir())
    assets = static_dir

    class EdyShieldHandler(BaseHTTPRequestHandler):
        """Handler HTTP da API do EDY Shield."""

        # Silence default logging for cleaner tests; logs go through
        # the application logger via the CLI instead.
        def log_message(self, format: str, *args: Any) -> None:
            """Sobrescrever para silenciar logging padrão do http.server."""

        def do_GET(self) -> None:
            """Roteador de requisições GET."""
            path = self.path.split("?", 1)[0]

            if path == "/":
                self._send_file(assets / "index.html", "text/html; charset=utf-8")
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
            elif path.startswith("/api/report/"):
                self._get_report(path)
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "endpoint não encontrado")

        def do_POST(self) -> None:
            """Roteador de requisições POST."""
            path = self.path.split("?", 1)[0]
            if path == "/api/scan":
                self._post_scan()
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

        def _read_json(self) -> dict[str, Any]:
            """Ler e decodificar o corpo JSON da requisição."""
            length = int(self.headers.get("Content-Length", "0"))
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
            """Responder com bytes e cabeçalhos padrão."""
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_error(self, status: HTTPStatus, message: str) -> None:
            """Responder com erro JSON."""
            self._send_json(
                {"error": message, "status": int(status)},
                status=status,
            )

    return EdyShieldHandler
