"""Hierarquia de exceções de domínio do EDY Shield (Missão 2).

Fonte canônica da hierarquia de erros do Core (ADR-005 — Erros de domínio
customizados). Permite que services e UI traduzam falhas de domínio sem
vazar tracebacks brutos.

Estrutura:

    EDYShieldError                 (raiz da hierarquia)
    ├── HashError                  (falhas do domínio de hash/integridade)
    │   └── UnsupportedAlgorithmError
    ├── ValidationError            (falhas de validação de entrada)
    └── FilesystemError            (falhas de filesystem seguras)
"""


class EDYShieldError(Exception):
    """Raiz da hierarquia de erros de domínio do EDY Shield.

    Todas as exceções de domínio herdam desta classe. Expõe o atributo
    ``message`` com a descrição legível da falha.

    Attributes:
        message: Descrição humana da falha.
    """

    def __init__(self, message: str) -> None:
        """Initialize the error with a human-readable message."""
        super().__init__(message)
        self.message = message


class HashError(EDYShieldError):
    """Base exception for all hash-related domain failures.

    Attributes:
        message: Human-readable description of the failure.
    """


class UnsupportedAlgorithmError(HashError):
    """Raised when a requested hash algorithm is not in the supported whitelist.

    This is the domain-level signal that an algorithm name was rejected before
    it ever reached ``hashlib`` — arbitrary algorithm names are never accepted
    (see ARCHITECTURE.md §6 — segurança-first).

    Attributes:
        algorithm: The offending algorithm value, or ``None`` when the input
            was not even a string (e.g. ``None`` or an ``int``).
    """

    def __init__(self, message: str, *, algorithm: str | None = None) -> None:
        """Initialize with a message and the optional offending algorithm."""
        super().__init__(message)
        self.algorithm = algorithm


class ValidationError(EDYShieldError):
    """Raised when a caller-supplied input fails boundary validation.

    Reserved for validation failures of user input (chunk size, expected
    digest, encoding) that should be surfaced as domain errors by higher
    layers instead of leaking raw tracebacks.
    """


class FilesystemError(EDYShieldError):
    """Raised for safe filesystem failures (path traversal, etc.).

    Base for filesystem-domain failures that higher layers must translate
    without exposing absolute paths or raw OS errors.
    """
