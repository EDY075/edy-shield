"""Erros de domínio do plugin framework (Sprint 3, Missão 6).

Hierarquia de exceções específica dos plugins, enraizada em
:class:`app.core.exceptions.EDYShieldError` para que camadas superiores
(services/UI) tratem falhas de plugin com o mesmo mecanismo das demais
falhas de domínio (ADR-005).

Estrutura:

    EDYShieldError
    └── PluginError
        ├── PluginNotFoundError
        ├── PluginRegistrationError
        └── PluginExecutionError
"""

from app.core.exceptions import EDYShieldError


class PluginError(EDYShieldError):
    """Raiz das falhas do domínio de plugins."""


class PluginNotFoundError(PluginError):
    """Plugin solicitado não está registrado no PluginManager."""


class PluginRegistrationError(PluginError):
    """Falha ao registrar um plugin (nome duplicado, tipo inválido)."""


class PluginExecutionError(PluginError):
    """Falha durante a execução de um plugin (validate/execute/health_check).

    Attributes:
        plugin_name: Nome do plugin que falhou.
    """

    def __init__(self, message: str, *, plugin_name: str | None = None) -> None:
        """Initialize with a message and the optional plugin name."""
        super().__init__(message)
        self.plugin_name = plugin_name
