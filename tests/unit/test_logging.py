"""Testes do logging centralizado do EDY Shield (Missão 3)."""

import logging

import pytest

from app.core.config import Settings
from app.core.logging import get_logger, setup_logging


class TestSetupLogging:
    """Configuração do logger raiz."""

    def test_sets_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        settings = Settings(log_level="DEBUG")
        monkeypatch.setattr("app.core.logging.logger._configured", False)
        setup_logging(settings)
        logger = logging.getLogger("edy_shield")
        assert logger.level == logging.DEBUG

    def test_idempotent_handlers(self) -> None:
        setup_logging(Settings(log_level="INFO"))
        logger = logging.getLogger("edy_shield")
        count_before = len(logger.handlers)
        setup_logging(Settings(log_level="INFO"))
        count_after = len(logger.handlers)
        assert count_after == count_before
        assert count_after >= 1


class TestGetLogger:
    """Criação de loggers nomeados."""

    def test_child_name(self) -> None:
        logger = get_logger("cli.hash_cmd")
        assert logger.name == "edy_shield.cli.hash_cmd"

    def test_returns_logger_instance(self) -> None:
        assert isinstance(get_logger("foo"), logging.Logger)

    def test_emits_without_error(self, caplog: pytest.LogCaptureFixture) -> None:
        setup_logging(Settings(log_level="DEBUG"))
        logger = get_logger("test")
        with caplog.at_level(logging.DEBUG, logger="edy_shield.test"):
            logger.debug("mensagem de teste")
        assert "mensagem de teste" in caplog.text
