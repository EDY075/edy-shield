"""Interface base para todos os plugins do EDY Shield (Sprint 3, Missão 6).

Todo plugin implementa :class:`Plugin` e fornece:

* **Metadados** — ``name``, ``version``, ``description``, ``author``.
* **Ciclo de vida** — :meth:`Plugin.validate`, :meth:`Plugin.execute` e
  :meth:`Plugin.health_check`, invocados pelo :class:`PluginManager`.

A UI **nunca** invoca um plugin diretamente: ela chama o Plugin Manager,
que valida o contexto, executa o plugin e traduz falhas de domínio em
:class:`app.plugins.plugin_errors.PluginError` (Missão 9).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.plugins.contracts import ScanContext, ScanResult


class Plugin(ABC):
    """Contrato base de um plugin da plataforma EDY Shield.

    Subclasses devem definir os metadados como atributos de classe e
    implementar os três métodos abstratos do ciclo de vida.
    """

    #: Identificador único do plugin (slug, lowercase com underscores).
    name: str
    #: Versão semântica do plugin (ex.: ``"1.1.0"``).
    version: str
    #: Descrição curta exibida em relatórios e na UI.
    description: str
    #: Autor/mantenedor do plugin.
    author: str

    @abstractmethod
    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Deve verificar a presença/validade de ``context.target`` e
        ``context.options`` sem realizar a varredura em si. Falhas devem
        lançar :class:`app.plugins.plugin_errors.PluginExecutionError`.

        Args:
            context: Contexto fornecido pelo PluginManager.
        """

    @abstractmethod
    def execute(self, context: ScanContext) -> ScanResult:
        """Executar a varredura e retornar um :class:`ScanResult`.

        Args:
            context: Contexto já validado pelo PluginManager.

        Returns:
            Resultado padronizado da varredura.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Verificar se o plugin está pronto para executar.

        Returns:
            ``True`` quando o plugin está saudável e pode executar,
            ``False`` caso contrário.
        """
