"""Plugins oficiais (built-in) do EDY Shield (Sprint 3, Missões 7 e 9).

Cada módulo deste pacote implementa um :class:`Plugin` concreto registrado
no :class:`PluginManager` padrão da aplicação.

Plugins atuais:

* :class:`LogAnalyzer` — análise de logs (Missão 7).
* :class:`HashCheckerPlugin` — cálculo/verificação de hashes (Missão 9).
"""

from app.plugins.builtin.hash_checker_plugin import HashCheckerPlugin
from app.plugins.builtin.log_analyzer import LogAnalyzer

__all__ = ["HashCheckerPlugin", "LogAnalyzer"]
