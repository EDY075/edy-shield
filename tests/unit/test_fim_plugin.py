"""Testes do plugin FileIntegrityPlugin (Sprint 5 — FIM).

Cobre: validação do contexto, ações baseline/scan/compare, mapeamento de
evidências (novo/modificado/removido/ignorado), tradução de erros e health
check.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.core.fim import FimStore
from app.plugins.builtin.file_integrity_plugin import FileIntegrityPlugin
from app.plugins.contracts import ScanContext, Severity
from app.plugins.plugin_errors import PluginExecutionError


def _write(path: Path, name: str, content: str = "data") -> Path:
    f = path / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    root = tmp_path / "target"
    _write(root, "a.txt", "aaa")
    _write(root, "b.txt", "bbb")
    return root


@pytest.fixture
def plugin(tmp_path: Path) -> FileIntegrityPlugin:
    store = FimStore(tmp_path / "fim")
    return FileIntegrityPlugin(store)


# ---------------------------------------------------------------------------
# Validação
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_baseline_context(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        plugin.validate(ScanContext(target=target_dir, options={"action": "baseline"}))

    def test_invalid_action(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(ScanContext(target=target_dir, options={"action": "nope"}))

    def test_invalid_algorithm(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(
                ScanContext(target=target_dir, options={"action": "baseline", "algorithm": "NOPE"})
            )

    def test_missing_target(self, plugin: FileIntegrityPlugin) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(ScanContext(options={"action": "baseline"}))

    def test_scan_requires_baseline_id(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(ScanContext(target=target_dir, options={"action": "scan"}))

    def test_compare_requires_compare_id(
        self, plugin: FileIntegrityPlugin, target_dir: Path
    ) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(
                ScanContext(
                    target=target_dir,
                    options={"action": "compare", "baseline_id": "x"},
                )
            )

    def test_scan_valid(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        plugin.validate(
            ScanContext(
                target=target_dir,
                options={"action": "scan", "baseline_id": "fim_sha256_20260802T120000Z"},
            )
        )


# ---------------------------------------------------------------------------
# Ação baseline
# ---------------------------------------------------------------------------


class TestBaselineAction:
    def test_create_and_persist(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        result = plugin.execute(ScanContext(target=target_dir, options={"action": "baseline"}))
        assert result.plugin_name == "file_integrity"
        assert result.stats["entries"] == 2
        assert "Baseline: fim_" in result.observations[0]
        # Persistida no store
        assert len(plugin.store.list()) == 1

    def test_default_action_is_baseline(
        self, plugin: FileIntegrityPlugin, target_dir: Path
    ) -> None:
        result = plugin.execute(ScanContext(target=target_dir))
        assert result.stats["entries"] == 2


# ---------------------------------------------------------------------------
# Ação scan
# ---------------------------------------------------------------------------


class TestScanAction:
    def _create_baseline(self, plugin: FileIntegrityPlugin, target_dir: Path) -> str:
        result = plugin.execute(ScanContext(target=target_dir, options={"action": "baseline"}))
        return result.observations[0].replace("Baseline: ", "")

    def test_scan_no_changes(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        baseline_id = self._create_baseline(plugin, target_dir)
        result = plugin.execute(
            ScanContext(
                target=target_dir,
                options={"action": "scan", "baseline_id": baseline_id},
            )
        )
        assert result.stats["added"] == 0
        assert result.stats["modified"] == 0
        assert result.stats["removed"] == 0
        assert result.stats["unchanged"] == 2
        assert "Nenhuma mudança" in result.summary

    def test_scan_detects_changes(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        baseline_id = self._create_baseline(plugin, target_dir)

        _write(target_dir, "a.txt", "changed content")  # modificado
        _write(target_dir, "c.txt", "new")  # novo
        (target_dir / "b.txt").unlink()  # removido

        result = plugin.execute(
            ScanContext(
                target=target_dir,
                options={"action": "scan", "baseline_id": baseline_id},
            )
        )
        assert result.stats["added"] == 1
        assert result.stats["modified"] == 1
        assert result.stats["removed"] == 1

        messages = {f.message for f in result.findings}
        assert any("arquivo novo: c.txt" in m for m in messages)
        assert any("arquivo modificado: a.txt" in m for m in messages)
        assert any("arquivo removido: b.txt" in m for m in messages)

        # Severidades: LOW novo, MEDIUM modificado, HIGH removido
        by_message = {f.message: f.severity for f in result.findings}
        assert by_message["arquivo novo: c.txt"] is Severity.LOW
        assert by_message["arquivo modificado: a.txt"] is Severity.MEDIUM
        assert by_message["arquivo removido: b.txt"] is Severity.HIGH

    def test_scan_unknown_baseline(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.execute(
                ScanContext(
                    target=target_dir,
                    options={"action": "scan", "baseline_id": "fim_sha256_20260802T000000Z"},
                )
            )


# ---------------------------------------------------------------------------
# Ação compare
# ---------------------------------------------------------------------------


class TestCompareAction:
    def test_compare_two_baselines(self, plugin: FileIntegrityPlugin, target_dir: Path) -> None:
        result_a = plugin.execute(ScanContext(target=target_dir, options={"action": "baseline"}))
        id_a = result_a.observations[0].replace("Baseline: ", "")

        _write(target_dir, "b.txt", "changed")
        # baseline_id tem granularidade de segundos — aguarda 1s para evitar
        # colisão de id no FimStore (mesmo segundo sobrescreveria a baseline A).
        time.sleep(1.05)
        result_b = plugin.execute(ScanContext(target=target_dir, options={"action": "baseline"}))
        id_b = result_b.observations[0].replace("Baseline: ", "")
        assert id_a != id_b

        result = plugin.execute(
            ScanContext(
                target=target_dir,
                options={"action": "compare", "baseline_id": id_a, "compare_id": id_b},
            )
        )
        assert result.stats["modified"] == 1
        assert "Baseline A" in result.observations[0]
        assert "Baseline B" in result.observations[1]

    def test_compare_requires_compare_id(
        self, plugin: FileIntegrityPlugin, target_dir: Path
    ) -> None:
        with pytest.raises(PluginExecutionError):
            plugin.validate(
                ScanContext(
                    target=target_dir,
                    options={"action": "compare", "baseline_id": "x"},
                )
            )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealth:
    def test_health_check_true(self, plugin: FileIntegrityPlugin) -> None:
        assert plugin.health_check() is True

    def test_metadata(self, plugin: FileIntegrityPlugin) -> None:
        assert plugin.name == "file_integrity"
        assert plugin.version == "2.0.0"
        assert plugin.author == "EDY Shield Contributors"
