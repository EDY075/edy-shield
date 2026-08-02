"""Plugin framework do EDY Shield (Sprint 3, Missão 6).

Infraestrutura oficial de extensões da plataforma. Novos módulos de
cibersegurança (Log Analyzer, futuros IOC Scanner, File Integrity Monitor)
são implementados como **plugins** e executados de forma uniforme pelo
:class:`PluginManager`.

Camada: ``app.plugins`` fica acima do Core (consumo de
``app.core.filesystem``/``app.core.exceptions``) e abaixo de
``app.services``/UI — a UI **nunca** invoca lógica de negócio diretamente,
sempre via Plugin Manager (Missão 9).

Módulos:

* :mod:`app.plugins.contracts` — modelos compartilhados (ScanContext,
  Evidence, ScanResult, Severity).
* :mod:`app.plugins.plugin_base` — interface base para todos os plugins.
* :mod:`app.plugins.plugin_registry` — registro central de plugins.
* :mod:`app.plugins.plugin_manager` — orquestrador de execução.

Exceções do domínio de plugins são definidas em
:mod:`app.plugins.plugin_errors` (hierarquia EDYShieldError).
"""

from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_manager import PluginManager
from app.plugins.plugin_registry import PluginRegistry

__all__ = [
    "Evidence",
    "Plugin",
    "PluginManager",
    "PluginRegistry",
    "ScanContext",
    "ScanResult",
    "Severity",
]
