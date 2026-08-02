"""Testes do formato Markdown do Report Engine (Sprint 5 — FIM).

Cobre: to_markdown (estrutura, estatísticas, achados, observações) e o
dispatcher render (aceita md/markdown e rejeita formatos desconhecidos).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.plugins import Evidence, ScanResult, Severity
from app.services.report_engine import render, to_markdown


@pytest.fixture
def result() -> ScanResult:
    """ScanResult típico do File Integrity Monitor."""
    return ScanResult(
        plugin_name="file_integrity",
        plugin_version="2.0.0",
        timestamp=datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC),
        summary="2 mudança(s) detectada(s): 1 novo(s), 1 modificado(s), 0 removido(s).",
        findings=(
            Evidence(
                severity=Severity.LOW,
                message="arquivo novo: novo.txt",
                metadata={"hexdigest": "ab" * 32, "size_bytes": "5"},
            ),
            Evidence(
                severity=Severity.MEDIUM,
                message="arquivo modificado: app.ini",
                metadata={"old_digest": "ab" * 32, "new_digest": "cd" * 32, "size_bytes": "8"},
            ),
        ),
        stats={"added": 1, "modified": 1, "removed": 0, "unchanged": 3},
        observations=("Baseline: fim_sha256_20260802T120000Z", "Algoritmo: SHA256"),
    )


class TestToMarkdown:
    def test_structure_has_expected_sections(self, result: ScanResult) -> None:
        md = to_markdown(result)
        assert "# EDY SHIELD — Relatório de Varredura" in md
        assert "## Resumo" in md
        assert "## Estatísticas" in md
        assert "## Achados" in md
        assert "## Observações" in md

    def test_metadata_lines(self, result: ScanResult) -> None:
        md = to_markdown(result)
        assert "`file_integrity` v2.0.0" in md
        assert "2026-08-02T12:00:00+00:00" in md
        assert "`Média`" in md  # max_severity MEDIUM → label "Média"

    def test_stats_table(self, result: ScanResult) -> None:
        md = to_markdown(result)
        assert "| `added` | 1 |" in md
        assert "| `unchanged` | 3 |" in md

    def test_findings_listed(self, result: ScanResult) -> None:
        md = to_markdown(result)
        assert "- **Baixa** arquivo novo: novo.txt" in md
        assert "- **Média** arquivo modificado: app.ini" in md

    def test_observations_listed(self, result: ScanResult) -> None:
        md = to_markdown(result)
        assert "- Baseline: fim_sha256_20260802T120000Z" in md
        assert "- Algoritmo: SHA256" in md

    def test_empty_findings_and_observations(self) -> None:
        empty = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 2, 12, 0, 0, tzinfo=UTC),
            summary="ok",
        )
        md = to_markdown(empty)
        assert "_(nenhum achado)_" in md
        assert "_(nenhuma observação)_" in md
        assert "_(sem estatísticas)_" in md

    def test_no_plaintext_leak_of_metadata(self, result: ScanResult) -> None:
        # Metadata (digests) não deve vazar para o Markdown — apenas message
        md = to_markdown(result)
        assert "ababab" not in md or "old_digest" not in md


class TestRenderMarkdown:
    @pytest.mark.parametrize("fmt", ["md", "markdown", " MD ", "Markdown"])
    def test_accepts_markdown_aliases(self, result: ScanResult, fmt: str) -> None:
        out = render(result, fmt)
        assert out.startswith("# EDY SHIELD")

    def test_rejects_unknown(self, result: ScanResult) -> None:
        with pytest.raises(ValueError):
            render(result, "pdf")
