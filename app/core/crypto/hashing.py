"""Primitivas criptográficas do núcleo EDY Shield (Missão 2).

Abstrai o ``hashlib`` com whitelist de algoritmos (nunca aceitar nomes
arbitrários do usuário), emissão de ``DeprecationWarning`` para SHA1/MD5 e
comparação de digests em tempo constante via ``hmac.compare_digest``.

Fonte canônica de :class:`HashAlgorithm`, :func:`normalize_algorithm`,
:func:`new_hasher` e :func:`safe_compare` — migrados de
:mod:`app.core.algorithms.hash_checker` (Missão 2).
"""

import hashlib
import hmac
import warnings
from enum import Enum
from typing import Protocol

from app.core.exceptions import UnsupportedAlgorithmError

#: Algorithms considered cryptographically broken for collision resistance.
#: Using them emits a :class:`DeprecationWarning` at runtime (ARES-QA-004).
_WEAK_ALGORITHMS: frozenset[str] = frozenset({"SHA1", "MD5"})


class HashAlgorithm(Enum):
    """Whitelist of hash algorithms supported by the Hash Checker.

    Members are named after the canonical algorithm names. The ``hashlib``
    name is derived via ``member.name.lower()`` only after whitelist
    validation, so unsupported algorithms are rejected at the boundary.
    """

    SHA256 = "SHA256"
    SHA1 = "SHA1"
    MD5 = "MD5"


class _Hasher(Protocol):
    """Minimal hasher interface consumed by the core.

    Represents the subset of the ``hashlib`` hasher API actually used
    (``update`` + ``hexdigest``) so :func:`new_hasher` stays fully typed and
    no ``Any`` leaks into callers (ARES-QA-013).
    """

    def update(self, data: bytes, /) -> None: ...
    def hexdigest(self) -> str: ...


def new_hasher(member: HashAlgorithm) -> _Hasher:
    """Create the ``hashlib`` hasher for a validated algorithm (ARES-QA-013).

    Also emits a :class:`DeprecationWarning` for weak algorithms (ARES-QA-004).

    Args:
        member: A whitelisted :class:`HashAlgorithm` member.

    Returns:
        A fresh ``hashlib`` hasher ready to receive updates.
    """
    if member.name in _WEAK_ALGORITHMS:
        warnings.warn(
            f"{member.name} is cryptographically broken for collision "
            "resistance; use SHA256 unless absolutely required "
            "(ARCHITECTURE.md §6).",
            DeprecationWarning,
            stacklevel=2,
        )
    return hashlib.new(member.name.lower())


def safe_compare(actual: str, expected: str) -> bool:
    """Compare two digest strings in constant time (ARES-QA-003).

    Wraps :func:`hmac.compare_digest` so callers never depend on the stdlib
    spelling directly.

    Args:
        actual: Freshly computed digest (lowercase hex).
        expected: Expected digest (lowercase hex, already normalized).

    Returns:
        ``True`` when the digests match, ``False`` otherwise.
    """
    return hmac.compare_digest(actual, expected)


def normalize_algorithm(algorithm: HashAlgorithm | str) -> HashAlgorithm:
    """Normalize a caller-supplied algorithm into a supported :class:`HashAlgorithm`.

    Accepts :class:`HashAlgorithm` members or case-insensitive strings such as
    ``"sha256"``, ``"SHA-256"`` or ``"Sha1"``. Anything outside the whitelist
    raises :class:`UnsupportedAlgorithmError` — never reaches ``hashlib``.
    Non-string, non-member inputs (``None``, ``int``, ...) are rejected with
    the same domain error instead of leaking a confusing ``AttributeError``
    (ARES-QA-006).

    Args:
        algorithm: Hash algorithm as an enum member or string.

    Returns:
        The normalized :class:`HashAlgorithm` member.

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not in the whitelist or
            is not a valid input type.
    """
    if isinstance(algorithm, HashAlgorithm):
        return algorithm

    if not isinstance(algorithm, str):
        raise UnsupportedAlgorithmError(
            f"algorithm must be a HashAlgorithm or str, got {type(algorithm).__name__}.",
            algorithm=repr(algorithm),
        )

    normalized = algorithm.strip().upper().replace("-", "").replace("_", "")
    try:
        return HashAlgorithm[normalized]
    except KeyError:
        supported = ", ".join(member.name for member in HashAlgorithm)
        raise UnsupportedAlgorithmError(
            f"Unsupported hash algorithm: {algorithm!r}. Supported algorithms: {supported}.",
            algorithm=algorithm,
        ) from None
