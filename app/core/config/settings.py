"""Configuração da aplicação EDY Shield (Missão 3).

``Settings`` é a fonte única de configuração da aplicação: uma
:class:`dataclasses.dataclass` congelada carregada a partir de variáveis de
ambiente (prefixo ``EDY_``) com padrões seguros. Nenhum módulo do Core
depende de UI ou CLI.

Uso:

    from app.core.config import Settings, load_settings

    settings = load_settings()
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: Padrões canônicos (evitam acessar atributos de classe em dataclass slots).
DEFAULT_HASH_ALGORITHM = "SHA256"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_CHUNK_SIZE = 65536
DEFAULT_ENCODING = "utf-8"


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração congelada da aplicação (Missão 3).

    Attributes:
        default_hash_algorithm: Algoritmo usado quando o usuário não
            especifica um (``EDY_DEFAULT_HASH_ALGORITHM``).
        log_level: Nível do logger raiz ``edy_shield``
            (``EDY_LOG_LEVEL``).
        allowed_root: Diretório permitido para operações de arquivo;
            ``None`` significa o diretório de trabalho atual
            (``EDY_ALLOWED_ROOT``).
        chunk_size: Bytes lidos por iteração ao hashear arquivos
            (``EDY_CHUNK_SIZE``).
        encoding: Encoding usado para fontes de texto (``EDY_TEXT_ENCODING``).
    """

    default_hash_algorithm: str = DEFAULT_HASH_ALGORITHM
    log_level: str = DEFAULT_LOG_LEVEL
    allowed_root: Path | None = None
    chunk_size: int = DEFAULT_CHUNK_SIZE
    encoding: str = DEFAULT_ENCODING


def _env_chunk_size() -> int:
    """Ler e validar ``EDY_CHUNK_SIZE``.

    Returns:
        Valor do chunk size (default 65536 quando não definido).

    Raises:
        ValueError: Se o valor não for um inteiro positivo.
    """
    raw = os.getenv("EDY_CHUNK_SIZE")
    if raw is None:
        return DEFAULT_CHUNK_SIZE
    try:
        chunk_size = int(raw)
    except ValueError as exc:
        raise ValueError(f"EDY_CHUNK_SIZE must be an integer, got {raw!r}.") from exc
    if chunk_size <= 0:
        raise ValueError(f"EDY_CHUNK_SIZE must be a positive integer, got {chunk_size}.")
    return chunk_size


def _env_allowed_root() -> Path | None:
    """Ler ``EDY_ALLOWED_ROOT`` como caminho.

    Returns:
        ``Path`` quando definido, ``None`` caso contrário.
    """
    raw = os.getenv("EDY_ALLOWED_ROOT")
    return Path(raw) if raw is not None else None


def load_settings() -> Settings:
    """Carregar ``Settings`` a partir do ambiente, com validação de tipos.

    Lê as variáveis ``EDY_*`` uma única vez e converte os valores para os
    tipos declarados. Valores inválidos levantam :class:`ValueError` com
    mensagem legível — nunca um ``TypeError`` obscuro de conversão.

    Returns:
        Instância imutável de :class:`Settings`.

    Raises:
        ValueError: Se ``EDY_CHUNK_SIZE`` não for um inteiro positivo.
    """
    return Settings(
        default_hash_algorithm=os.getenv("EDY_DEFAULT_HASH_ALGORITHM", DEFAULT_HASH_ALGORITHM),
        log_level=os.getenv("EDY_LOG_LEVEL", DEFAULT_LOG_LEVEL),
        allowed_root=_env_allowed_root(),
        chunk_size=_env_chunk_size(),
        encoding=os.getenv("EDY_TEXT_ENCODING", DEFAULT_ENCODING),
    )
