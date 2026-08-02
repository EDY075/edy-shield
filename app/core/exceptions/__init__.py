"""Hierarquia de exceções de domínio do EDY Shield (Sprint 2 — Missão 2).

Base da hierarquia de erros do Core. Permite que as camadas superiores
(services, CLI, UI) traduzam falhas de domínio sem vazar tracebacks brutos
(ADR-005).

Fonte canônica: :mod:`app.core.exceptions.domain`. Este pacote re-exporta a
hierarquia completa para consumo externo.
"""

from app.core.exceptions.domain import (
    EDYShieldError,
    FilesystemError,
    HashError,
    UnsupportedAlgorithmError,
    ValidationError,
)

__all__ = [
    "EDYShieldError",
    "FilesystemError",
    "HashError",
    "UnsupportedAlgorithmError",
    "ValidationError",
]
