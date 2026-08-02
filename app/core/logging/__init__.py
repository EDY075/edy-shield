"""Logging centralizado do EDY Shield (Sprint 2 — Missão 3).

Configura um logger raiz único com formato padrão, nível configurável via
``Settings`` e políticas de segurança (nunca logar conteúdo de arquivos —
apenas hashes e metadados; nunca logar segredos).
"""

from app.core.logging.logger import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
