"""Testes do plugin EntropyAnalyzerPlugin do EDY Shield (v2.1 — M2.2).

Cobre: execução via PluginManager, validação, mapeamento de severidade,
tradução do ScanResult e erros de contexto.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugins import PluginManager, ScanContext, Severity
from app.plugins.builtin import EntropyAnalyzerPlugin
from app.plugins.plugin_errors import PluginExecutionError


class TestEntropyAnalyzerPlugin:
    def test_metadata(self) -> None:
        plugin = EntropyAnalyzerPlugin()
        assert plugin.name == "entropy_analyzer"
        assert plugin.version == "2.3.0"
        assert plugin.author == "EDY Shield Contributors"

    def test_validate_missing_target_raises(self) -> None:
        plugin = EntropyAnalyzerPlugin()
        with pytest.raises(PluginExecutionError):
            plugin.validate(ScanContext(target=None))

    def test_validate_missing_file_raises(self, tmp_path: Path) -> None:
        plugin = EntropyAnalyzerPlugin()
        with pytest.raises(PluginExecutionError):
            plugin.validate(ScanContext(target=tmp_path / "missing.txt"))

    def test_effective_root_uses_allowed_root_when_set(self, tmp_path: Path) -> None:

        plugin = EntropyAnalyzerPlugin()
        guard = tmp_path.parent
        ctx = ScanContext(target=tmp_path / "f.txt", allowed_root=guard)
        assert plugin._effective_root(tmp_path / "f.txt", ctx) == guard

    def test_effective_root_defaults_to_parent(self, tmp_path: Path) -> None:
        plugin = EntropyAnalyzerPlugin()
        target = tmp_path / "f.txt"
        ctx = ScanContext(target=target)
        assert plugin._effective_root(target, ctx) == target.resolve().parent

    def test_health_check_true(self) -> None:
        assert EntropyAnalyzerPlugin().health_check() is True

    def test_run_via_manager(self, tmp_path: Path) -> None:
        target = tmp_path / "log.txt"
        target.write_text(("abcdefghijklmnopqrstuvwxyz0123456789" * 10) + "\n", encoding="utf-8")

        manager = PluginManager()
        manager.register(EntropyAnalyzerPlugin())
        result = manager.run("entropy_analyzer", ScanContext(target=target))

        assert result.plugin_name == "entropy_analyzer"
        assert result.stats["total_metrics"] >= 1
        assert result.findings
        assert result.findings[0].metadata["entropy"]

    def test_severity_mapping_is_valid(self, tmp_path: Path) -> None:
        # Conteúdo uniforme de alta entropia -> severidade HIGH.
        target = tmp_path / "high.txt"
        target.write_text(bytes(range(256)).decode("latin1") * 20, encoding="latin1")

        manager = PluginManager()
        manager.register(EntropyAnalyzerPlugin())
        result = manager.run("entropy_analyzer", ScanContext(target=target))
        severities = {f.severity for f in result.findings}
        assert severities <= set(Severity)
        assert Severity.HIGH in severities

    def test_run_registered_in_builtin(self) -> None:
        from app.plugins.builtin import __all__ as builtin_all

        assert "EntropyAnalyzerPlugin" in builtin_all

    def test_observations_present(self, tmp_path: Path) -> None:
        target = tmp_path / "plain.txt"
        target.write_text("texto simples " * 50, encoding="utf-8")
        manager = PluginManager()
        manager.register(EntropyAnalyzerPlugin())
        result = manager.run("entropy_analyzer", ScanContext(target=target))
        assert result.observations
        assert any("bits/unidade" in o for o in result.observations)
