"""Teste de regressão — versionamento dos plugins built-in.

Política oficial: plugins oficiais internos acompanham a versão da plataforma
(app.__version__). Este teste impede que um plugin built-in fique com versão
desalinhada (ex.: hash_checker/log_analyzer presos em 1.1.0 enquanto o
produto está em 2.0.0).
"""

from __future__ import annotations

from pathlib import Path

from app import __version__
from app.plugins.builtin import FileIntegrityPlugin, HashCheckerPlugin, LogAnalyzer

#: Plugins oficiais internos — devem espelhar a versão da plataforma.
_BUILTIN_PLUGINS = (HashCheckerPlugin, LogAnalyzer, FileIntegrityPlugin)


class TestPluginVersioning:
    def test_all_builtin_plugins_match_platform_version(self) -> None:
        """Todo plugin oficial deve exibir a versão da plataforma."""
        for plugin_cls in _BUILTIN_PLUGINS:
            plugin = plugin_cls()
            assert plugin.version == __version__, (
                f"{plugin.name} está em {plugin.version}, mas a plataforma "
                f"está em {__version__} — plugins oficiais acompanham a release."
            )

    def test_metadata_reports_platform_version(self, tmp_path: Path) -> None:
        """list_plugins (usado pelo /api/plugins) deve reportar a versão."""
        from app.ui.server import build_default_manager

        manager = build_default_manager(fim_dir=tmp_path / "fim", db_path=tmp_path / "test.db")
        for meta in manager.list_plugins():
            assert meta["version"] == __version__, (
                f"{meta['name']} reporta {meta['version']} — deve ser {__version__}."
            )
