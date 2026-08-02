"""Testes de funções públicas do server (Sprint 3/5).

Cobre: ``_default_history_dir`` (caminho padrão) e ``serve`` (inicialização
e fechamento do servidor no KeyboardInterrupt — comportamento de limpeza).
"""

from __future__ import annotations

from pathlib import Path

import pytest

import app.ui.server as server_mod
from app.services.history import HistoryStore
from app.ui.server import _default_history_dir, serve


class TestDefaultHistoryDir:
    def test_default_history_dir(self) -> None:
        assert _default_history_dir() == Path.home() / ".edyshield" / "history"


class TestServe:
    def test_serve_closes_server_on_keyboard_interrupt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """serve() inicia o servidor e fecha no KeyboardInterrupt (finally)."""

        class FakeServer:
            def __init__(self, address: tuple, handler_class: type) -> None:
                self.address = address
                self.handler_class = handler_class
                self.closed = False
                self.server_port = 43210

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                self.closed = True

        fake = FakeServer(("127.0.0.1", 0), object)
        monkeypatch.setattr(server_mod, "ThreadingHTTPServer", lambda _addr, _handler: fake)

        manager = server_mod.build_default_manager(
            fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db"
        )
        history = HistoryStore(tmp_path / "history", db_path=tmp_path / "test.db")

        serve(host="127.0.0.1", port=0, manager=manager, history=history)

        assert fake.closed is True
        captured = capsys.readouterr()
        assert "EDY Shield UI em http://127.0.0.1:43210" in captured.out

    def test_serve_uses_default_manager_and_history(self, monkeypatch) -> None:
        """Quando manager/history não são fornecidos, são criados automaticamente."""

        class FakeServer:
            def __init__(self, _address: tuple, _handler_class: type) -> None:
                self.handler_class = _handler_class
                self.closed = False
                self.server_port = 0

            def serve_forever(self) -> None:
                raise KeyboardInterrupt

            def server_close(self) -> None:
                self.closed = True

        fake = FakeServer(("127.0.0.1", 0), object)
        monkeypatch.setattr(server_mod, "ThreadingHTTPServer", lambda _addr, _handler: fake)

        serve(host="127.0.0.1", port=0)

        assert fake.closed is True
