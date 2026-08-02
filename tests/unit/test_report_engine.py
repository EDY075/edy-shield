"""Testes do Report Engine (Sprint 3, Missão 8).

Cobre: serialização JSON (pretty/minified, UTC), TXT (estrutura completa),
HTML (estrutura, escaping anti-injeção, autônomo) e o dispatcher
``render`` (formatos válidos e inválido).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.plugins import Evidence, ScanResult, Severity
from app.services.report_engine import render, to_html, to_json, to_txt


@pytest.fixture
def result() -> ScanResult:
    """ScanResult de exemplo com todos os campos preenchidos."""
    return ScanResult(
        plugin_name="log_analyzer",
        plugin_version="2.0.0",
        timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
        summary="3 evento(s) detectado(s) em 4 linhas.",
        findings=(
            Evidence(
                severity=Severity.CRITICAL,
                message="Evento crítico registrado no log.",
                source="linha 4",
                metadata={"category": "critical"},
            ),
            Evidence(
                severity=Severity.HIGH,
                message="Tentativa de login falhou.",
                source="linha 2",
                metadata={"category": "failed_login"},
            ),
        ),
        stats={"critical": 1, "failed_login": 1, "error": 0},
        observations=("Arquivo analisado: auth.log", "Janela de tempo: 10:00 → 10:05"),
    )


class TestToJson:
    def test_pretty_valid_json(self, result: ScanResult) -> None:
        parsed = json.loads(to_json(result))
        assert parsed["plugin_name"] == "log_analyzer"
        assert parsed["plugin_version"] == "2.0.0"
        assert parsed["max_severity"] == "CRITICAL"
        assert parsed["timestamp"] == "2026-08-01T12:00:00+00:00"
        assert len(parsed["findings"]) == 2
        assert parsed["stats"] == {"critical": 1, "failed_login": 1, "error": 0}

    def test_pretty_indents(self, result: ScanResult) -> None:
        assert "\n  " in to_json(result)

    def test_minified(self, result: ScanResult) -> None:
        compact = to_json(result, pretty=False)
        assert "\n" not in compact.strip()
        assert json.loads(compact)["plugin_name"] == "log_analyzer"

    def test_roundtrip_serializes_datetime(self, result: ScanResult) -> None:
        # timestamp é datetime → as_dict converte para ISO antes do json.
        parsed = json.loads(to_json(result))
        assert parsed["timestamp"].endswith("+00:00")


class TestToTxt:
    def test_structure_contains_all_sections(self, result: ScanResult) -> None:
        text = to_txt(result)
        assert "RELATÓRIO DE VARREDURA" in text
        assert "RESUMO" in text
        assert "ESTATÍSTICAS" in text
        assert "ACHADOS" in text
        assert "OBSERVAÇÕES" in text

    def test_contains_metadata(self, result: ScanResult) -> None:
        text = to_txt(result)
        assert "log_analyzer" in text
        assert "v2.0.0" in text
        assert "2026-08-01T12:00:00" in text
        assert "Crítica" in text

    def test_contains_findings_and_observations(self, result: ScanResult) -> None:
        text = to_txt(result)
        assert "linha 4" in text
        assert "Evento crítico registrado no log." in text
        assert "Arquivo analisado: auth.log" in text

    def test_empty_result(self) -> None:
        empty = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            summary="s",
        )
        text = to_txt(empty)
        assert "nenhum achado" in text
        assert "sem estatísticas" in text


class TestToHtml:
    def test_standalone_document(self, result: ScanResult) -> None:
        doc = to_html(result)
        assert doc.startswith("<!DOCTYPE html>")
        assert "<html" in doc
        assert "</html>" in doc
        assert 'lang="pt-BR"' in doc
        assert "<style>" in doc

    def test_contains_all_sections(self, result: ScanResult) -> None:
        doc = to_html(result)
        assert "Resumo" in doc
        assert "Estatísticas" in doc
        assert "Achados" in doc
        assert "Observações" in doc

    def test_escapes_dangerous_content(self) -> None:
        dangerous = ScanResult(
            plugin_name="evil",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, tzinfo=UTC),
            summary='<script>alert("xss")</script>',
            findings=(
                Evidence(
                    severity=Severity.HIGH,
                    message="<img src=x onerror=alert(1)>",
                    source="<b>bold</b>",
                ),
            ),
            observations=("</li><li>injected",),
        )
        doc = to_html(dangerous)
        assert "<script>alert" not in doc
        assert "<img src=x" not in doc
        assert "&lt;script&gt;alert" in doc
        assert "&lt;img src=x" in doc
        assert "&lt;/li&gt;&lt;li&gt;injected" in doc

    def test_severity_badge_present(self, result: ScanResult) -> None:
        doc = to_html(result)
        assert "Crítica" in doc
        assert "background:" in doc


class TestRender:
    @pytest.mark.parametrize("fmt", ["json", "txt", "html"])
    def test_valid_formats(self, result: ScanResult, fmt: str) -> None:
        output = render(result, fmt)
        assert isinstance(output, str)
        assert len(output) > 0

    def test_uppercase_normalized(self, result: ScanResult) -> None:
        assert render(result, "JSON") == render(result, "json")

    def test_invalid_format_raises(self, result: ScanResult) -> None:
        with pytest.raises(ValueError) as exc_info:
            render(result, "pdf")
        assert "não suportado" in str(exc_info.value)
