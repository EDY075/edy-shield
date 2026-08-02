"""Logging centralizado do EDY Shield (Missão 3).

Configura um logger raiz ``edy_shield`` com formato único e nível
configurável via :class:`~app.core.config.settings.Settings`.

Política de segurança (ARES-QA-005): **nunca** registrar conteúdo de arquivo
— apenas hashes e metadados. **Nunca** registrar segredos ou caminhos
absolutos em mensagens de erro de domínio.
"""

from __future__ import annotations

import logging
import sys

from app.core.config.settings import Settings

#: Logger raiz da aplicação. Todos os módulos usam ``get_logger``.
_ROOT_LOGGER_NAME = "edy_shield"

#: Formato único de log (data | nível | módulo | mensagem).
_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

#: Flag para manter o setup idempotente.
_configured = False


def setup_logging(settings: Settings) -> None:
    """Configurar o logger raiz ``edy_shield`` (idempotente).

    Configura o nível, o formato e um ``StreamHandler`` em ``stderr``.
    Chamadas repetidas não duplicam handlers.

    Args:
        settings: Configuração da aplicação (``log_level`` é usado).
    """
    global _configured

    logger = logging.getLogger(_ROOT_LOGGER_NAME)

    if not _configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        _configured = True

    logger.setLevel(settings.log_level.upper())


def get_logger(name: str) -> logging.Logger:
    """Retornar um logger filho de ``edy_shield``.

    Args:
        name: Nome do módulo/classe que vai logar (ex.: ``"cli.hash_cmd"``).

    Returns:
        Logger nomeado ``edy_shield.<name>``.
    """
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
