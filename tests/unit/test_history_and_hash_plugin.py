"""Testes do HistoryStore e do plugin Hash Checker (Sprint 3, Missão 9).

Cobre: persistência/leitura do histórico, listagem ordenada, limpeza,
proteção contra path traversal via id, e o plugin Hash Checker (texto,
arquivo, verificação MATCH/MISMATCH, validação e execução via manager).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.plugins import Evidence, PluginManager, ScanContext, ScanResult, Severity
from app.plugins.builtin import HashCheckerPlugin
from app.plugins.plugin_errors import PluginExecutionError
from app.services.history import HistoryError, HistoryStore

# ---------------------------------------------------------------------------
# ScanResult.from_dict
# ---------------------------------------------------------------------------


class TestScanResultFromDict:
    def test_roundtrip(self) -> None:
        original = ScanResult(
            plugin_name="log_analyzer",
            plugin_version="0.1.0",
            timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
            summary="sum",
            findings=(Evidence(severity=Severity.CRITICAL, message="x", source="linha 1"),),
            stats={"critical": 1},
            observations=("obs",),
        )
        restored = ScanResult.from_dict(original.as_dict())
        assert restored == original

    def test_roundtrip_empty(self) -> None:
        original = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            summary="s",
        )
        restored = ScanResult.from_dict(original.as_dict())
        assert restored.findings == ()
        assert restored.observations == ()


# ---------------------------------------------------------------------------
# HistoryStore
# ---------------------------------------------------------------------------


class TestHistoryStore:
    def test_save_and_get(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        result = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
            summary="s",
        )
        scan_id = store.save(result)
        assert store.get(scan_id) == result

    def test_get_missing(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        assert store.get("nao-existe") is None

    def test_list_sorted_desc(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        older = ScanResult(
            plugin_name="a",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC),
            summary="s",
        )
        newer = ScanResult(
            plugin_name="b",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
            summary="s",
        )
        store.save(older)
        store.save(newer)
        entries = store.list()
        assert len(entries) == 2
        assert entries[0]["plugin_name"] == "b"  # mais recente primeiro

    def test_clear(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        result = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            summary="s",
        )
        store.save(result)
        assert store.clear() == 1
        assert store.list() == []

    def test_unsafe_id_raises(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        with pytest.raises(HistoryError):
            store.get("../escape")

    def test_base_dir_created(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "nested" / "history")
        assert store.base_dir.is_dir()

    def test_corrupt_file_raises(self, tmp_path: Path) -> None:
        store = HistoryStore(tmp_path / "history")
        (store.base_dir / "corrupt.json").write_text("{not json", encoding="utf-8")
        with pytest.raises(HistoryError):
            store.get("corrupt")


# ---------------------------------------------------------------------------
# HashCheckerPlugin
# ---------------------------------------------------------------------------


class TestHashCheckerPlugin:
    def test_hash_text(self) -> None:
        result = HashCheckerPlugin().execute(
            ScanContext(target="hello", options={"algorithm": "SHA256"})
        )
        assert result.findings[0].metadata["hexdigest"] == (
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )
        assert result.stats["bytes"] == 5

    def test_hash_file(self, tmp_path: Path) -> None:
        path = tmp_path / "data.txt"
        path.write_text("hello", encoding="utf-8")
        result = HashCheckerPlugin().execute(ScanContext(target=path))
        assert result.findings[0].metadata["source"] == "file"
        assert result.stats["bytes"] == 5

    def test_verify_match(self) -> None:
        digest = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        result = HashCheckerPlugin().execute(
            ScanContext(target="hello", options={"expected": digest})
        )
        assert any("MATCH" in f.message for f in result.findings)
        assert result.max_severity() is Severity.INFO

    def test_verify_mismatch(self) -> None:
        result = HashCheckerPlugin().execute(
            ScanContext(target="hello", options={"expected": "00" * 32})
        )
        assert any("MISMATCH" in f.message for f in result.findings)
        assert result.max_severity() is Severity.HIGH

    def test_validate_missing_target(self) -> None:
        with pytest.raises(PluginExecutionError):
            HashCheckerPlugin().validate(ScanContext(target=None))

    def test_validate_invalid_algorithm(self) -> None:
        with pytest.raises(PluginExecutionError):
            HashCheckerPlugin().validate(ScanContext(target="x", options={"algorithm": "FOO"}))

    def test_run_via_manager(self) -> None:
        manager = PluginManager()
        manager.register(HashCheckerPlugin())
        result = manager.run("hash_checker", ScanContext(target="hello"))
        assert result.plugin_name == "hash_checker"

    def test_health_check(self) -> None:
        assert HashCheckerPlugin().health_check() is True


class TestDefaultManager:
    def test_build_default_manager_registers_both(self) -> None:
        from app.ui.server import build_default_manager

        manager = build_default_manager()
        assert manager.registry.contains("hash_checker")
        assert manager.registry.contains("log_analyzer")
