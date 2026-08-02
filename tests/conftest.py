"""Fixtures compartilhadas da suíte de testes da EDY Shield.

Garante que a raiz do projeto esteja em ``sys.path`` para que o pacote
``app`` seja importável em qualquer modo de coleção do pytest.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def plain_text() -> str:
    """Texto plano usado como amostra conhecida nos testes de hash."""
    return "hello"
