"""Validadores de entrada do núcleo EDY Shield (Missão 2).

Validações puras de entrada antes de alcançarem o domínio: chunk size
positivo e digest esperado (hex, tamanho por algoritmo). Migrados de
:mod:`app.core.algorithms.hash_checker` (Missão 2).

Nota de escopo: ``validate_expected`` precisa do tamanho do digest por
algoritmo, obtido via ``hashlib.new`` sobre um membro **já validado** de
:class:`~app.core.crypto.HashAlgorithm` — nenhum nome arbitrário chega ao
``hashlib`` por aqui.
"""

import hashlib
import string

from app.core.crypto import HashAlgorithm


def validate_chunk_size(chunk_size: int) -> None:
    """Validate that ``chunk_size`` is a positive integer (ARES-QA-010).

    Args:
        chunk_size: Value to validate.

    Raises:
        ValueError: If ``chunk_size`` is not a positive ``int`` (bools are
            rejected too, as they are ``int`` subclasses).
    """
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError(f"chunk_size must be a positive integer, got {chunk_size!r}.")


def validate_expected(expected: str, algorithm: HashAlgorithm) -> str:
    """Validate an expected digest string and return it normalized (ARES-QA-009).

    Args:
        expected: Expected hexadecimal digest (any case, optional surrounding
            whitespace).
        algorithm: Algorithm whose digest length is used for validation.

    Returns:
        The trimmed, lower-cased digest string.

    Raises:
        TypeError: If ``expected`` is not a ``str``.
        ValueError: If ``expected`` is not hexadecimal or has the wrong length
            for the algorithm.
    """
    if not isinstance(expected, str):
        raise TypeError(f"expected must be a str, got {type(expected).__name__}.")

    value = expected.strip()
    if not value or any(char not in string.hexdigits for char in value):
        raise ValueError("expected must be a hexadecimal digest string.")

    digest_length = hashlib.new(algorithm.name.lower()).digest_size * 2
    if len(value) != digest_length:
        raise ValueError(
            f"expected must have {digest_length} hexadecimal characters for "
            f"{algorithm.name}, got {len(value)}."
        )
    return value.lower()
