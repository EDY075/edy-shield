"""Operações seguras de filesystem do EDY Shield (Sprint 2 — Missão 2).

Fronteira única de validação de caminhos: contenção na raiz permitida,
rejeição de ``..``/symlinks que escapam e de arquivos especiais (FIFO,
devices, sockets). Migra a lógica hoje residente em
``app.services.file_utils`` para o Core.

Fonte canônica: :mod:`app.core.filesystem.safe_path`.
"""

from app.core.filesystem.safe_path import (
    ensure_regular_file,
    is_within_root,
    resolve_safe_path,
    validate_allowed_root,
)

__all__ = [
    "ensure_regular_file",
    "is_within_root",
    "resolve_safe_path",
    "validate_allowed_root",
]
