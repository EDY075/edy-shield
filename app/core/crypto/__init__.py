"""Primitivas criptográficas do EDY Shield (Sprint 2 — Missão 2).

Abstrai o ``hashlib`` com whitelist de algoritmos (nunca aceitar nomes
arbitrários do usuário), emissão de ``DeprecationWarning`` para SHA1/MD5 e
comparação de digests em tempo constante via ``hmac.compare_digest``.

Fonte canônica: :mod:`app.core.crypto.hashing`. Camada consumida por
:mod:`app.core.algorithms`.
"""

from app.core.crypto.hashing import (
    HashAlgorithm,
    new_hasher,
    normalize_algorithm,
    safe_compare,
)

__all__ = ["HashAlgorithm", "new_hasher", "normalize_algorithm", "safe_compare"]
