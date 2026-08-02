"""Registro central de plugins do EDY Shield (Sprint 3, Missão 6).

Mantém o catálogo de plugins disponíveis no processo. O registro é
**imutável após o registro de cada plugin** (nomes únicos, sem sobrescrita
silenciosa) e permite listar, buscar e verificar a existência de plugins.

O :class:`PluginManager` consulta este registro para executar plugins pelo
nome — a UI nunca interage com ele diretamente (Missão 9).
"""

from __future__ import annotations

from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginNotFoundError, PluginRegistrationError


class PluginRegistry:
    """Catálogo de plugins registrados, indexado por nome (case-insensitive).

    Exemplo:

        registry = PluginRegistry()
        registry.register(LogAnalyzer())
        registry.get("log_analyzer")  # → LogAnalyzer instance
    """

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._plugins: dict[str, Plugin] = {}

    def register(self, plugin: Plugin) -> None:
        """Registrar um plugin no catálogo.

        Args:
            plugin: Instância do plugin a registrar.

        Raises:
            PluginRegistrationError: Se o plugin já estiver registrado ou
                tiver um nome vazio/duplicado (normalizado).
        """
        if not isinstance(plugin, Plugin):
            raise PluginRegistrationError(
                f"plugin deve ser instância de Plugin, got {type(plugin).__name__}.",
            )
        key = plugin.name.strip().lower()
        if not key:
            raise PluginRegistrationError("plugin.name não pode ser vazio.")
        if key in self._plugins:
            raise PluginRegistrationError(f"plugin já registrado: {plugin.name}.")
        self._plugins[key] = plugin

    def get(self, name: str) -> Plugin:
        """Buscar um plugin pelo nome (case-insensitive).

        Args:
            name: Nome do plugin.

        Returns:
            Instância registrada do plugin.

        Raises:
            PluginNotFoundError: Se não houver plugin com esse nome.
        """
        key = name.strip().lower()
        try:
            return self._plugins[key]
        except KeyError:
            raise PluginNotFoundError(f"plugin não encontrado: {name}.") from None

    def contains(self, name: str) -> bool:
        """Verificar se um plugin está registrado (case-insensitive).

        Args:
            name: Nome do plugin.

        Returns:
            ``True`` quando registrado, ``False`` caso contrário.
        """
        return name.strip().lower() in self._plugins

    def names(self) -> list[str]:
        """Listar os nomes dos plugins registrados, em ordem alfabética.

        Returns:
            Lista de nomes únicos.
        """
        return sorted(plugin.name for plugin in self._plugins.values())

    def all(self) -> list[Plugin]:
        """Listar todas as instâncias registradas, em ordem alfabética.

        Returns:
            Lista de plugins.
        """
        return sorted(self._plugins.values(), key=lambda plugin: plugin.name.lower())

    def __len__(self) -> int:
        """Número de plugins registrados."""
        return len(self._plugins)
