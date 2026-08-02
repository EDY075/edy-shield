"""Modelos e erros de domínio do núcleo EDY Shield.

Os erros de domínio agora têm fonte canônica em
:mod:`app.core.exceptions.domain` (Missão 2); este pacote os re-exporta
junto dos modelos de resultado para manter a API pública atual
(``HashError``, ``HashResult``, ``HashSource``, ``UnsupportedAlgorithmError``).
"""

from app.core.exceptions.domain import HashError, UnsupportedAlgorithmError
from app.core.models.hashes import HashResult, HashSource

__all__ = ["HashError", "HashResult", "HashSource", "UnsupportedAlgorithmError"]
