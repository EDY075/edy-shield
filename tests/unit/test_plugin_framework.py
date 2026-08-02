"""Testes do Plugin Framework do EDY Shield (Sprint 3, Missão 6).

Cobre: contratos (Severity, Evidence, ScanContext, ScanResult), interface
base, registro (PluginRegistry) e PluginManager (validação, health check,
execução, tradução de erros).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.plugins import (
    Evidence,
    Plugin,
    PluginManager,
    PluginRegistry,
    ScanContext,
    ScanResult,
    Severity,
)
from app.plugins.contracts import _SEVERITY_RANK
from app.plugins.plugin_errors import (
    PluginError,
    PluginExecutionError,
    PluginNotFoundError,
    PluginRegistrationError,
)


class DummyPlugin(Plugin):
    """Plugin de teste que registra o último contexto recebido."""

    name = "dummy"
    version = "1.0.0"
    description = "Plugin dummy para testes."
    author = "test"

    def __init__(self, *, healthy: bool = True) -> None:
        self.healthy = healthy
        self.last_context: ScanContext | None = None

    def validate(self, context: ScanContext) -> None:
        self.last_context = context
        if context.target is None:
            raise PluginExecutionError("target é obrigatório.", plugin_name=self.name)

    def execute(self, context: ScanContext) -> ScanResult:
        _ = context
        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary="ok",
        )

    def health_check(self) -> bool:
        return self.healthy


class FailingPlugin(Plugin):
    """Plugin cuja execução lança exceção arbitrária."""

    name = "failing"
    version = "0.0.1"
    description = "Plugin que falha."
    author = "test"

    def validate(self, context: ScanContext) -> None:
        _ = context
        raise RuntimeError("boom")

    def execute(self, context: ScanContext) -> ScanResult:
        _ = context
        raise RuntimeError("boom-exec")

    def health_check(self) -> bool:
        return True


class NoNamePlugin(Plugin):
    """Plugin sem nome — deve ser rejeitado pelo registro."""

    name = ""
    version = "1"
    description = "d"
    author = "a"

    def validate(self, context: ScanContext) -> None:
        _ = context

    def execute(self, context: ScanContext) -> ScanResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return True


class PluginA(Plugin):
    """Plugin para teste de ordenação (nome zzz)."""

    name = "zzz"
    version = "1"
    description = "d"
    author = "a"

    def validate(self, context: ScanContext) -> None:
        _ = context

    def execute(self, context: ScanContext) -> ScanResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return True


class PluginB(Plugin):
    """Plugin para teste de ordenação (nome aaa)."""

    name = "aaa"
    version = "1"
    description = "d"
    author = "a"

    def validate(self, context: ScanContext) -> None:
        _ = context

    def execute(self, context: ScanContext) -> ScanResult:
        raise NotImplementedError

    def health_check(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Contratos
# ---------------------------------------------------------------------------


class TestSeverity:
    def test_rank_ordering_is_ascending(self) -> None:
        assert _SEVERITY_RANK[Severity.INFO] < _SEVERITY_RANK[Severity.LOW]
        assert _SEVERITY_RANK[Severity.LOW] < _SEVERITY_RANK[Severity.MEDIUM]
        assert _SEVERITY_RANK[Severity.MEDIUM] < _SEVERITY_RANK[Severity.HIGH]
        assert _SEVERITY_RANK[Severity.HIGH] < _SEVERITY_RANK[Severity.CRITICAL]


class TestEvidence:
    def test_defaults(self) -> None:
        evidence = Evidence(severity=Severity.LOW, message="achado")
        assert evidence.source is None
        assert evidence.metadata == {}

    def test_frozen(self) -> None:
        evidence = Evidence(severity=Severity.INFO, message="x")
        with pytest.raises(FrozenInstanceError):
            evidence.message = "y"  # type: ignore[misc]


class TestScanContext:
    def test_defaults(self) -> None:
        context = ScanContext()
        assert context.target is None
        assert context.options == {}
        assert context.allowed_root is None


class TestScanResult:
    def test_max_severity_empty(self) -> None:
        result = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime.now(UTC),
            summary="s",
        )
        assert result.max_severity() is Severity.INFO

    def test_max_severity_returns_highest(self) -> None:
        result = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime.now(UTC),
            summary="s",
            findings=(
                Evidence(severity=Severity.LOW, message="a"),
                Evidence(severity=Severity.CRITICAL, message="b"),
                Evidence(severity=Severity.MEDIUM, message="c"),
            ),
        )
        assert result.max_severity() is Severity.CRITICAL

    def test_as_dict_serializes_timestamp_utc(self) -> None:
        result = ScanResult(
            plugin_name="p",
            plugin_version="1",
            timestamp=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
            summary="s",
            findings=(Evidence(severity=Severity.HIGH, message="x"),),
            stats={"high": 1},
            observations=("obs",),
        )
        data = result.as_dict()
        assert data["plugin_name"] == "p"
        assert data["timestamp"] == "2026-08-01T12:00:00+00:00"
        assert data["max_severity"] == "HIGH"
        assert data["findings"][0]["severity"] == "HIGH"
        assert data["stats"] == {"high": 1}
        assert data["observations"] == ["obs"]


# ---------------------------------------------------------------------------
# PluginRegistry
# ---------------------------------------------------------------------------


class TestPluginRegistry:
    def test_register_and_get(self) -> None:
        registry = PluginRegistry()
        registry.register(DummyPlugin())
        assert registry.get("dummy") is not None
        assert registry.get("DUMMY") is not None  # case-insensitive

    def test_duplicate_raises(self) -> None:
        registry = PluginRegistry()
        registry.register(DummyPlugin())
        with pytest.raises(PluginRegistrationError):
            registry.register(DummyPlugin())

    def test_empty_name_raises(self) -> None:
        with pytest.raises(PluginRegistrationError):
            PluginRegistry().register(NoNamePlugin())

    def test_contains_and_names(self) -> None:
        registry = PluginRegistry()
        registry.register(DummyPlugin())
        assert registry.contains("dummy")
        assert not registry.contains("nope")
        assert registry.names() == ["dummy"]

    def test_all_sorted(self) -> None:
        registry = PluginRegistry()
        registry.register(PluginA())
        registry.register(PluginB())
        assert [p.name for p in registry.all()] == ["aaa", "zzz"]

    def test_len(self) -> None:
        registry = PluginRegistry()
        assert len(registry) == 0
        registry.register(DummyPlugin())
        assert len(registry) == 1

    def test_get_missing_raises(self) -> None:
        with pytest.raises(PluginNotFoundError):
            PluginRegistry().get("missing")


# ---------------------------------------------------------------------------
# PluginManager
# ---------------------------------------------------------------------------


class TestPluginManager:
    def test_run_success(self) -> None:
        manager = PluginManager()
        plugin = DummyPlugin()
        manager.register(plugin)
        result = manager.run("dummy", ScanContext(target="x"))
        assert result.plugin_name == "dummy"
        assert result.summary == "ok"
        assert plugin.last_context is not None
        assert plugin.last_context.target == "x"

    def test_run_unknown_plugin(self) -> None:
        manager = PluginManager()
        with pytest.raises(PluginNotFoundError):
            manager.run("nope", ScanContext(target="x"))

    def test_run_validation_error_wrapped(self) -> None:
        manager = PluginManager()
        manager.register(FailingPlugin())
        with pytest.raises(PluginExecutionError) as exc_info:
            manager.run("failing", ScanContext(target="x"))
        assert exc_info.value.plugin_name == "failing"
        assert "validação falhou" in str(exc_info.value)

    def test_run_unhealthy_plugin(self) -> None:
        manager = PluginManager()
        manager.register(DummyPlugin(healthy=False))
        with pytest.raises(PluginExecutionError) as exc_info:
            manager.run("dummy", ScanContext(target="x"))
        assert "não está saudável" in str(exc_info.value)

    def test_run_all(self) -> None:
        manager = PluginManager()
        manager.register(DummyPlugin())
        results = manager.run_all(ScanContext(target="x"))
        assert [r.plugin_name for r in results] == ["dummy"]

    def test_list_plugins_metadata(self) -> None:
        manager = PluginManager()
        manager.register(DummyPlugin())
        metadata = manager.list_plugins()
        assert metadata == [
            {
                "name": "dummy",
                "version": "1.0.0",
                "description": "Plugin dummy para testes.",
                "author": "test",
            }
        ]

    def test_plugin_error_is_edyshield_error(self) -> None:
        from app.core.exceptions import EDYShieldError

        assert issubclass(PluginError, EDYShieldError)
