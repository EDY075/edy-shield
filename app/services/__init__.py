"""Camada de serviços (casos de uso) da EDY Shield.

Orquestra o core e centraliza responsabilidades de aplicação que não
pertencem ao domínio puro — notavelmente a segurança de caminhos de
arquivo, o Report Engine (Sprint 3, Missão 8) e o Histórico de varreduras
(Sprint 3, Missão 9). As funções :func:`resolve_safe_path` e
:func:`validate_allowed_root` são re-exportadas aqui para que as camadas
superiores (UI/CLI) importem de um único ponto.

Dependências: ``services → core`` e ``services → plugins`` (direção única,
ver ARCHITECTURE.md §5.4).
"""

from app.services.file_utils import resolve_safe_path, validate_allowed_root
from app.services.history import HistoryStore
from app.services.report_engine import render, to_html, to_json, to_txt

__all__ = [
    "HistoryStore",
    "render",
    "resolve_safe_path",
    "to_html",
    "to_json",
    "to_txt",
    "validate_allowed_root",
]
