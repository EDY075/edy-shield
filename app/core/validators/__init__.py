"""Validadores de entrada do EDY Shield (Sprint 2 — Missão 2).

Validações puras de entrada antes de alcançarem o domínio: digest esperado
(hex, tamanho por algoritmo), chunk size positivo, encoding conhecido.
Sem dependências de UI/CLI.

Fonte canônica: :mod:`app.core.validators.input`.
"""

from app.core.validators.input import validate_chunk_size, validate_expected

__all__ = ["validate_chunk_size", "validate_expected"]
