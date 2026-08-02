"""Compat shim: erros de domínio agora vivem em ``app.core.exceptions.domain``.

Re-exporta ``HashError`` e ``UnsupportedAlgorithmError`` da fonte canônica
para preservar a API pública (Missão 2). Imports existentes que usam
``from app.core.models.common import HashError`` continuam funcionando.
"""

from app.core.exceptions.domain import HashError, UnsupportedAlgorithmError

__all__ = ["HashError", "UnsupportedAlgorithmError"]
