"""Plugin Manager do EDY Shield (Sprint 3, Missão 6).

Ponto único de execução de plugins: recebe um :class:`ScanContext`, valida
o plugin, executa e devolve um :class:`ScanResult` padronizado. Traduz
qualquer falha do ciclo de vida em :class:`PluginError` para que camadas
superiores (services/UI — Missão 9) tratem de forma uniforme.

A UI **nunca** executa plugins diretamente — sempre via PluginManager.
"""

from __future__ import annotations

from app.plugins.contracts import ScanContext, ScanResult
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError
from app.plugins.plugin_registry import PluginRegistry


class PluginManager:
    """Orquestra o ciclo de vida de execução dos plugins registrados.

    Exemplo:

        manager = PluginManager(registry)
        result = manager.run("log_analyzer", ScanContext(target=path))
    """

    def __init__(self, registry: PluginRegistry | None = None) -> None:
        """Initialize the manager.

        Args:
            registry: Registro a usar; quando ``None``, um novo registro
                vazio é criado.
        """
        self._registry = registry if registry is not None else PluginRegistry()

    @property
    def registry(self) -> PluginRegistry:
        """O registro de plugins associado a este manager."""
        return self._registry

    def register(self, plugin: Plugin) -> None:
        """Registrar um plugin no registro associado.

        Args:
            plugin: Instância do plugin a registrar.
        """
        self._registry.register(plugin)

    def run(self, plugin_name: str, context: ScanContext) -> ScanResult:
        """Executar um plugin pelo nome com o contexto fornecido.

        O fluxo completo é: localizar → ``validate`` → ``health_check`` →
        ``execute``. Falhas do plugin são traduzidas em
        :class:`PluginExecutionError` (com ``plugin_name``), nunca vazam
        exceções de implementação.

        Args:
            plugin_name: Nome do plugin a executar.
            context: Contexto da varredura.

        Returns:
            Resultado padronizado da varredura.

        Raises:
            PluginNotFoundError: Se o plugin não estiver registrado.
            PluginExecutionError: Se a validação, health check ou execução
                falhar.
        """
        plugin = self.registry.get(plugin_name)

        self._validate(plugin, context)
        self._health_check(plugin)
        return self._execute(plugin, context)

    def run_all(self, context: ScanContext) -> list[ScanResult]:
        """Executar todos os plugins registrados com o mesmo contexto.

        Nota: falhas individuais são propagadas (sem modo ``continue``),
        pois um plugin com erro deve ser visível — não silenciado.

        Args:
            context: Contexto compartilhado da varredura.

        Returns:
            Lista de resultados, na ordem alfabética dos plugins.
        """
        return [self.run(name, context) for name in self.registry.names()]

    def list_plugins(self) -> list[dict[str, str]]:
        """Listar metadados dos plugins para exibição (ex.: dashboard).

        Returns:
            Lista de dicionários com ``name``, ``version``, ``description``
            e ``author`` de cada plugin registrado.
        """
        return [
            {
                "name": plugin.name,
                "version": plugin.version,
                "description": plugin.description,
                "author": plugin.author,
            }
            for plugin in self.registry.all()
        ]

    def _validate(self, plugin: Plugin, context: ScanContext) -> None:
        """Executar ``plugin.validate`` traduzindo falhas."""
        try:
            plugin.validate(context)
        except Exception as exc:
            if isinstance(exc, PluginExecutionError):
                raise
            raise PluginExecutionError(
                f"validação falhou no plugin {plugin.name}: {exc}",
                plugin_name=plugin.name,
            ) from exc

    def _health_check(self, plugin: Plugin) -> None:
        """Executar ``plugin.health_check`` traduzindo falhas."""
        try:
            healthy = plugin.health_check()
        except Exception as exc:
            raise PluginExecutionError(
                f"health_check falhou no plugin {plugin.name}: {exc}",
                plugin_name=plugin.name,
            ) from exc
        if not healthy:
            raise PluginExecutionError(
                f"plugin {plugin.name} não está saudável para executar.",
                plugin_name=plugin.name,
            )

    def _execute(self, plugin: Plugin, context: ScanContext) -> ScanResult:
        """Executar ``plugin.execute`` traduzindo falhas."""
        try:
            return plugin.execute(context)
        except Exception as exc:
            raise PluginExecutionError(
                f"execução falhou no plugin {plugin.name}: {exc}",
                plugin_name=plugin.name,
            ) from exc
