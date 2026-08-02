"""Segurança de caminhos de arquivo — fronteira de validação da EDY Shield (shim).

A lógica foi migrada para o Core em :mod:`app.core.filesystem.safe_path`
(Missão 2). Este módulo permanece como **re-export** para preservar a
fronteira de serviços e a compatibilidade com imports existentes
(``app.core.algorithms.hash_checker`` e testes). Nenhuma lógica nova deve
ser adicionada aqui — novas funcionalidades de path vão para o Core.
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
