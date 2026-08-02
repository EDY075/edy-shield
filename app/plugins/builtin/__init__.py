"""Plugins oficiais (built-in) do EDY Shield (Sprint 3, Missões 7 e 9; Sprint 5; v2.1).

Cada módulo deste pacote implementa um :class:`Plugin` concreto registrado
no :class:`PluginManager` padrão da aplicação.

Plugins atuais:

* :class:`LogAnalyzer` — análise de logs (Missão 7).
* :class:`HashCheckerPlugin` — cálculo/verificação de hashes (Missão 9).
* :class:`FileIntegrityPlugin` — baseline + detecção de mudanças (Sprint 5).
* :class:`StringAnalyzerPlugin` — análise de strings suspeitas (v2.1 — M2.1).
* :class:`EntropyAnalyzerPlugin` — análise de entropia (v2.1 — M2.2).
"""

from app.plugins.builtin.entropy_analyzer_plugin import EntropyAnalyzerPlugin
from app.plugins.builtin.file_integrity_plugin import FileIntegrityPlugin
from app.plugins.builtin.hash_checker_plugin import HashCheckerPlugin
from app.plugins.builtin.log_analyzer import LogAnalyzer
from app.plugins.builtin.string_analyzer_plugin import StringAnalyzerPlugin

__all__ = [
    "EntropyAnalyzerPlugin",
    "FileIntegrityPlugin",
    "HashCheckerPlugin",
    "LogAnalyzer",
    "StringAnalyzerPlugin",
]
