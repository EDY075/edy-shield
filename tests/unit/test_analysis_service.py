"""Testes dos AnalysisStore e AnalysisService do EDY Shield (v2.1 — M2.3).

Cobre: persistência SQLite (análises), filtros (severidade/plugin/categoria/
data), execução isolada e combinada, ordenação por severidade, deduplicação,
recursão e formato JSON do relatório.
"""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.plugins.contracts import Evidence, ScanResult, Severity
from app.plugins.plugin_errors import PluginExecutionError, PluginNotFoundError
from app.services.analysis_service import (
    AnalysisService,
    _derive_category,
    _entropy_score,
    _meets,
)
from app.services.analysis_store import AnalysisRecord, AnalysisStore


def _make_result(
    plugin_name: str,
    *,
    findings: list[Evidence] | None = None,
) -> ScanResult:
    return ScanResult(
        plugin_name=plugin_name,
        plugin_version="1.0.0",
        timestamp=datetime.now(UTC),
        summary="ok",
        findings=tuple(findings or []),
        stats={"total": len(findings or [])},
    )


def _record(
    _store: AnalysisStore,
    *,
    target: str = "a.txt",
    plugin: str = "string_analyzer",
    severity: str = "MEDIUM",
    category: str | None = "url",
    score: int = 0,
    duration_ms: float = 5.0,
) -> AnalysisRecord:
    return AnalysisRecord(
        analysis_id=AnalysisStore.build_id(plugin),
        target=target,
        timestamp=datetime.now(UTC),
        plugin_name=plugin,
        severity=severity,
        evidence_count=2,
        duration_ms=duration_ms,
        version="1.0.0",
        category=category,
        score=score,
        result=_make_result(plugin),
    )


class TestAnalysisStore:
    def test_save_and_get(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "db.sqlite")
        rec = _record(store)
        store.save(rec)
        got = store.get(rec.analysis_id)
        assert got is not None
        assert got["plugin_name"] == "string_analyzer"
        assert got["target"] == "a.txt"
        assert got["severity"] == "MEDIUM"
        assert got["payload"]["plugin_name"] == "string_analyzer"

    def test_list_ordered_newest_first(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store, target="old,", severity="LOW"))
        store.save(_record(store, target="new,", severity="HIGH"))
        entries = store.list()
        assert len(entries) == 2
        assert entries[0]["target"] == "new,"
        assert entries[0]["severity"] == "HIGH"

    def test_filter_by_severity(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store, severity="HIGH"))
        store.save(_record(store, severity="LOW"))
        high = store.list(severity="HIGH")
        assert len(high) == 1 and high[0]["severity"] == "HIGH"

    def test_filter_by_plugin(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store, plugin="string_analyzer"))
        store.save(_record(store, plugin="entropy_analyzer"))
        only = store.list(plugin="entropy_analyzer")
        assert len(only) == 1 and only[0]["plugin_name"] == "entropy_analyzer"

    def test_filter_by_category(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store, category="url"))
        store.save(_record(store, category="hash"))
        urls = store.list(category="url")
        assert len(urls) == 1 and urls[0]["category"] == "url"

    def test_since_filter(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store))
        earlier = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        entries = store.list(since=earlier)
        assert len(entries) == 1

    def test_clear(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        store.save(_record(store))
        removed = store.clear()
        assert removed == 1
        assert store.list() == []

    def test_get_missing_returns_none(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        assert store.get("ana_x_nao_existe") is None


class TestAnalysisServiceIsolated:
    def test_single_plugin_string(self, tmp_path: Path) -> None:
        f = tmp_path / "s.txt"
        f.write_text("the quick brown fox.\n", encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(f, plugins=["string_analyzer"], persist=True)
        assert len(outs) == 1
        assert outs[0].plugin_name == "string_analyzer"

    def test_single_plugin_entropy(self, tmp_path: Path) -> None:
        f = tmp_path / "e.txt"
        b64 = (
            __import__("base64")
            .b64encode(bytes(random.getrandbits(8) for _ in range(3000)))
            .decode()
        )
        f.write_text(b64, encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(f, plugins=["entropy_analyzer"], persist=True)
        assert outs[0].plugin_name == "entropy_analyzer"
        assert outs[0].duration_ms >= 0

    def test_invalid_plugin_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "x.txt"
        f.write_text("a", encoding="utf-8")
        svc = AnalysisService()
        with pytest.raises(PluginNotFoundError):
            svc.analyze(f, plugins=["nao_existe"])


class TestCombined:
    def test_combined_runs_both(self, tmp_path: Path) -> None:
        f = tmp_path / "c.txt"
        f.write_text("normal line.\nhttp://evil.example.com/x\n", encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(f, plugins=["string_analyzer", "entropy_analyzer"], persist=True)
        assert len(outs) == 1
        assert outs[0].plugin_name == "combined"
        assert outs[0].result.stats.get("total_combined", 0) == len(outs[0].result.findings)

    def test_merge_orders_by_severity(self, tmp_path: Path) -> None:
        f = tmp_path / "c.txt"
        blob = (
            __import__("base64")
            .b64encode(bytes(random.getrandbits(8) for _ in range(4000)))
            .decode()
        )
        f.write_text("http://evil.example.com/x\n" + blob, encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        out = svc.analyze(f, plugins=["string_analyzer", "entropy_analyzer"], persist=False)[0]
        # Verificar ordenação decrescente de severidade (rank)
        result = out.result
        sev_order = [_sev_value(e) for e in result.findings]
        assert sev_order == sorted(sev_order, key=_sev_rank_text, reverse=True)

    def test_directory_recursive(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.txt").write_text("hello world\n", encoding="utf-8")
        (sub / "b.log").write_text("normal log line\n", encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(tmp_path, plugins=["string_analyzer"], recursive=True, persist=False)
        assert len(outs) >= 2  # a.txt + b.log (+ possivelmente __init__ etc)

    def test_severity_filter_excludes(self, tmp_path: Path) -> None:
        f = tmp_path / "low.txt"
        f.write_text("the quick brown fox jumps over the lazy dog. " * 20, encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(f, plugins=["string_analyzer"], severity="HIGH", persist=False)
        # texto sem achados high -> excluído
        assert outs == []


def _sev_value(e: Evidence) -> str:
    return e.severity.value


def _sev_rank_text(sev: str) -> int:
    order = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    return order.index(sev)


class TestAnalysisServiceExtras:
    def test_manager_and_store_properties(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        assert svc.manager is not None
        assert svc.store is store

    def test_string_with_categories_filter(self, tmp_path: Path) -> None:
        f = tmp_path / "cat.txt"
        f.write_text("https://example.com/x\n307f1abb8c9a3d040b21c1ec0ea433a5d\n", encoding="utf-8")
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        outs = svc.analyze(f, plugins=["string_analyzer"], categories=["url"], persist=False)
        # Filtro por categoria 'url' mantém apenas o finding da URL e exclui o hash.
        assert outs and len(outs[0].result.findings) == 1
        assert "example.com" in outs[0].result.findings[0].message

    def test_combined_with_categories_option(self, tmp_path: Path) -> None:
        f = tmp_path / "comb.txt"
        f.write_text("https://evil.example.com/x\nplain text\n", encoding="utf-8")
        svc = AnalysisService()
        outs = svc.analyze(
            f, plugins=["string_analyzer", "entropy_analyzer"], categories=["url"], persist=False
        )
        assert outs and outs[0].result.stats.get("total_combined", 0) >= 1

    def test_combined_severity_blanks_result_when_missing_threshold(self, tmp_path: Path) -> None:
        f = tmp_path / "low.txt"
        f.write_text("the quick brown fox jumps over the lazy dog. " * 20, encoding="utf-8")
        svc = AnalysisService()
        out = svc.analyze(
            f,
            plugins=["string_analyzer", "entropy_analyzer"],
            severity="CRITICAL",
            persist=False,
        )[0]
        # Resultado em branco após não atingir CRITICAL -> 0 findings
        assert out.result.findings == ()

    def test_history_and_get_roundtrip(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        svc = AnalysisService(store=store)
        f = tmp_path / "h.txt"
        f.write_text("sample content\n", encoding="utf-8")
        svc.analyze(f, plugins=["string_analyzer"], persist=True)
        entries = svc.history(plugin="string_analyzer", limit=10)
        assert entries and entries[0]["plugin_name"] == "string_analyzer"
        got = svc.get(entries[0]["analysis_id"])
        assert got is not None and got["plugin_name"] == "string_analyzer"

    def test_resolve_names_invalid_raises(self) -> None:
        svc = AnalysisService()
        with pytest.raises(PluginNotFoundError):
            svc._resolve_names(["nada"])

    def test_collect_unresolvable_path_returns_path(self, tmp_path: Path) -> None:
        svc = AnalysisService()
        ghost = tmp_path / "ghost.txt"
        assert svc._collect_files(ghost, recursive=False) == [ghost]

    def test_meets_invalid_minimum_returns_true(self) -> None:
        assert _meets(Severity.LOW, "not-a-severity") is True

    def test_derive_category_mapping(self) -> None:
        assert _derive_category("string_analyzer") == "string"
        assert _derive_category("entropy_analyzer") == "entropy"
        assert _derive_category("combined") == "combined"

    def test_merge_empty_raises_valueerror(self) -> None:
        svc = AnalysisService()
        with pytest.raises(ValueError):
            svc._merge([])

    def test_entropy_score_non_int_returns_zero(self) -> None:
        r = ScanResult(
            plugin_name="x",
            plugin_version="1",
            timestamp=datetime.now(UTC),
            summary="s",
            findings=(),
            stats={"score": "not-a-number"},
        )
        assert _entropy_score(r) == 0

    def test_store_db_path_and_close(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        assert store.db_path == tmp_path / "t.db"
        store.close()  # não deve levantar

    def test_store_get_corrupted_payload(self, tmp_path: Path) -> None:
        store = AnalysisStore(tmp_path / "a", db_path=tmp_path / "t.db")
        rec = _record(store)
        store.save(rec)
        # Corrompe o payload diretamente no banco
        from app.services.analysis_store import AnalysisError

        store._db.execute(
            "UPDATE analyses SET payload = ? WHERE analysis_id = ?",
            ("{{{not-json", rec.analysis_id),
        )
        with pytest.raises(AnalysisError):
            store.get(rec.analysis_id)

    def test_empty_manager_registers_defaults(self) -> None:
        from app.plugins import PluginManager, PluginRegistry

        svc = AnalysisService(manager=PluginManager(PluginRegistry()), store=None)
        svc._register_defaults()
        assert svc.manager.registry.contains("string_analyzer")
        assert svc.manager.registry.contains("entropy_analyzer")

    def test_merge_deduplicates_identical_findings(self) -> None:
        from app.services.analysis_service import _build_analysis_manager

        svc = AnalysisService(manager=_build_analysis_manager())
        ev = Evidence(severity=Severity.LOW, source="url", message="https://example.com/x")
        r1 = ScanResult(
            plugin_name="a",
            plugin_version="1",
            timestamp=datetime.now(UTC),
            summary="1",
            findings=(ev,),
            stats={"total": 1},
        )
        r2 = ScanResult(
            plugin_name="b",
            plugin_version="1",
            timestamp=datetime.now(UTC),
            summary="2",
            findings=(ev,),
            stats={"total": 1},
        )
        merged = svc._merge([r1, r2])
        # Achado duplicado é mesclado uma única vez (não duplicado).
        assert merged.stats["total_combined"] == 1
        assert len(merged.findings) == 1

    def test_plugin_execution_error_reraised(self, tmp_path: Path) -> None:
        from app.plugins import PluginManager, PluginRegistry
        from app.plugins.builtin import StringAnalyzerPlugin

        registry = PluginRegistry()
        registry.register(StringAnalyzerPlugin())
        svc = AnalysisService(manager=PluginManager(registry))
        ghost = tmp_path / "ghost_target.txt"
        # Target inexistente → plugin sem conteúdo → PluginExecutionError
        with pytest.raises(PluginExecutionError):
            svc._analyze_file(ghost, "string_analyzer", None, None)


def _sev_value_dup(e: Evidence) -> str:
    return e.severity.value
