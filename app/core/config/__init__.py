"""Configuração do EDY Shield (Sprint 2 — Missão 3).

Centraliza as definições de configuração da aplicação baseadas em
``dataclasses`` (padrão ``Settings``) e leitura de variáveis de ambiente
(prefixo ``EDY_``). Nenhum módulo do Core depende de UI ou CLI.
"""

from app.core.config.settings import Settings, load_settings

__all__ = ["Settings", "load_settings"]
