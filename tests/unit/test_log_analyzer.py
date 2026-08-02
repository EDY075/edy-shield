"""Testes do Log Analyzer — primeiro plugin oficial (Sprint 3, Missão 7).

Cobre: validação de contexto (target ausente, extensão inválida, path
fora da raiz), detecção de padrões (FAILED/SUCCESS LOGIN, ERROR, WARNING,
CRITICAL), estatísticas, janela de tempo e execução via PluginManager.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.plugins import PluginManager, ScanContext, ScanResult, Severity
from app.plugins.builtin import LogAnalyzer
from app.plugins.plugin_errors import PluginExecutionError


@pytest.fixture
def log_file(tmp_path: Path) -> Path:
    """Log de exemplo com todos os padrões e timestamps."""
    path = tmp_path / "auth.log"
    path.write_text(
        "\n".join(
            [
                "2026-08-01 10:00:00 INFO service started",
                "2026-08-01 10:01:00 SUCCESS LOGIN user=alice",
                "2026-08-01 10:02:00 FAILED LOGIN user=bob password=wrong",
                "2026-08-01 10:03:00 WARNING disk usage high",
                "2026-08-01 10:04:00 ERROR db connection lost",
                "2026-08-01 10:05:00 CRITICAL service crashed",
                "plain line without timestamp",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


class TestLogAnalyzerValidate:
    def test_missing_target_raises(self) -> None:
        with pytest.raises(PluginExecutionError):
            LogAnalyzer().validate(ScanContext(target=None))

    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(PluginExecutionError) as exc_info:
            LogAnalyzer().validate(ScanContext(target="file.csv"))
        assert "extensões" in str(exc_info.value)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PluginExecutionError) as exc_info:
            LogAnalyzer().validate(ScanContext(target=tmp_path / "nope.log"))
        assert "não pôde acessar" in str(exc_info.value)

    def test_outside_root_raises(self, tmp_path: Path) -> None:
        inside = tmp_path / "inside"
        inside.mkdir()
        outside = tmp_path / "outside.log"
        outside.write_text("x", encoding="utf-8")
        with pytest.raises(PluginExecutionError):
            LogAnalyzer().validate(ScanContext(target=outside, allowed_root=inside))

    def test_valid_file_passes(self, log_file: Path) -> None:
        # Não deve lançar exceção.
        LogAnalyzer().validate(ScanContext(target=log_file))


class TestLogAnalyzerExecute:
    def test_detects_all_patterns(self, log_file: Path) -> None:
        result = LogAnalyzer().execute(ScanContext(target=log_file))
        assert result.plugin_name == "log_analyzer"
        assert isinstance(result, ScanResult)

        categories = [f.metadata["category"] for f in result.findings]
        assert categories.count("failed_login") == 1
        assert categories.count("success_login") == 1
        assert categories.count("error") == 1
        assert categories.count("warning") == 1
        assert categories.count("critical") == 1

    def test_stats(self, log_file: Path) -> None:
        result = LogAnalyzer().execute(ScanContext(target=log_file))
        assert result.stats == {
            "failed_login": 1,
            "success_login": 1,
            "error": 1,
            "warning": 1,
            "critical": 1,
        }

    def test_max_severity_is_critical(self, log_file: Path) -> None:
        result = LogAnalyzer().execute(ScanContext(target=log_file))
        assert result.max_severity() is Severity.CRITICAL

    def test_time_window(self, log_file: Path) -> None:
        result = LogAnalyzer().execute(ScanContext(target=log_file))
        assert any("Janela de tempo" in obs for obs in result.observations)

    def test_empty_log(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.log"
        empty.write_text("", encoding="utf-8")
        result = LogAnalyzer().execute(ScanContext(target=empty))
        assert result.findings == ()
        assert result.stats["error"] == 0
        assert "Nenhum evento" in result.summary

    def test_max_lines_truncates(self, tmp_path: Path) -> None:
        path = tmp_path / "big.log"
        lines = ["2026-08-01 10:00:00 ERROR boom"] * 100
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        result = LogAnalyzer().execute(ScanContext(target=path, options={"max_lines": 10}))
        assert result.stats["error"] == 10
        assert any("truncada" in obs for obs in result.observations)

    def test_encoding_option(self, tmp_path: Path) -> None:
        path = tmp_path / "latin.log"
        path.write_bytes("ERROR ä".encode("latin-1"))
        result = LogAnalyzer().execute(ScanContext(target=path, options={"encoding": "latin-1"}))
        assert result.stats["error"] == 1


class TestLogAnalyzerViaManager:
    def test_run_via_plugin_manager(self, log_file: Path) -> None:
        manager = PluginManager()
        manager.register(LogAnalyzer())
        result = manager.run("log_analyzer", ScanContext(target=log_file))
        assert result.plugin_name == "log_analyzer"

    def test_health_check_true(self) -> None:
        assert LogAnalyzer().health_check() is True

    def test_list_plugins(self) -> None:
        manager = PluginManager()
        manager.register(LogAnalyzer())
        metadata = manager.list_plugins()
        assert metadata[0]["name"] == "log_analyzer"
        assert metadata[0]["version"] == "2.0.0"
