"""Analysis Service do EDY Shield (v2.1 — M2.3).

Orquestra a execução de análises (String Analyzer e/ou Entropy Analyzer)
sobre arquivos ou diretórios, com:

* execução **isolada** (um plugin) ou **combinada** (``--string --entropy``);
* medição de duração;
* mesclagem de resultados combinados (ordenação por severidade e
  deduplicação de achados idênticos);
* persistência opcional em SQLite via :class:`AnalysisStore`;
* recuperação de análises anteriores com filtros.

A **lógica de negócio vive aqui** (nunca na CLI nem na UI). CLI e API apenas
consomem este service (SPRINT/ADR-002).

Camada: ``app.services`` (use cases) — acima de ``app.plugins``/Core.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import Any

from app.plugins import PluginManager, PluginRegistry, ScanContext, ScanResult, Severity
from app.plugins.builtin import EntropyAnalyzerPlugin, StringAnalyzerPlugin
from app.plugins.contracts import Evidence
from app.plugins.plugin_errors import PluginExecutionError, PluginNotFoundError
from app.services.analysis_store import AnalysisRecord, AnalysisStore

#: Nomes canônicos dos plugins de análise suportados.
STRING_PLUGIN = "string_analyzer"
ENTROPY_PLUGIN = "entropy_analyzer"
_SUPPORTED = frozenset({STRING_PLUGIN, ENTROPY_PLUGIN})

#: Ordem de severidade para ordenação descrescente no resultado combinado.
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


@dataclass(frozen=True, slots=True)
class AnalysisOutcome:
    """Resultado de uma execução do service.

    Attributes:
        plugin_name: Plugin executado (ou ``"combined"``).
        result: :class:`ScanResult` consolidado (mesclado quando combinado).
        target: Alvo analisado.
        duration_ms: Tempo total de execução.
    """

    plugin_name: str
    result: ScanResult
    target: str
    duration_ms: float


class AnalysisService:
    """Camada de casos de uso para análise de conteúdos (String/Entropy).

    Args:
        manager: PluginManager já com os plugins registrados. Quando
            ``None``, um manager com String + Entropy é construído.
        store: AnalysisStore a usar; ``None`` usa o padrão.
    """

    def __init__(
        self,
        manager: PluginManager | None = None,
        store: AnalysisStore | None = None,
    ) -> None:
        self._manager = manager if manager is not None else _build_analysis_manager()
        self._store = store if store is not None else AnalysisStore()

    @property
    def manager(self) -> PluginManager:
        """O manager de plugins usado pelo service."""
        return self._manager

    @property
    def store(self) -> AnalysisStore:
        """O store de análises usado pelo service."""
        return self._store

    def analyze(
        self,
        target: str | Path,
        *,
        plugins: list[str] | None = None,
        recursive: bool = False,
        categories: list[str] | None = None,
        severity: str | None = None,
        persist: bool = True,
    ) -> list[AnalysisOutcome]:
        """Analisar arquivo ou diretório com os plugins solicitados.

        Args:
            target: Arquivo ou diretório a analisar.
            plugins: Nomes de plugins em ``{string_analyzer, entropy_analyzer}``.
                ``None`` usa ambos.
            recursive: Quando True e ``target`` é diretório, desce em
                subdiretórios.
            categories: Categorias a filtrar (String). ``None`` = todas.
            severity: Limiar mínimo de severidade (ex. ``HIGH``).
            persist: Quando True, persiste cada análise no SQLite.

        Returns:
            Lista de outcomes (um por arquivo/plugin).

        Raises:
            PluginNotFoundError: Se nenhum analisador válido for informado.
        """
        names = plugins if plugins is not None else [STRING_PLUGIN, ENTROPY_PLUGIN]
        names = self._resolve_names(names)
        path = Path(target)
        files = self._collect_files(path, recursive)
        outcomes: list[AnalysisOutcome] = []

        if len(names) == 1:
            for file_path in files:
                outcome = self._analyze_file(file_path, names[0], categories, severity)
                if outcome is None:
                    continue
                if persist:
                    self._store.save(_to_record(outcome))
                outcomes.append(outcome)
            return outcomes

        for file_path in files:
            outcome = self._analyze_combined(file_path, categories, severity)
            if persist:
                self._store.save(_to_record(outcome))
            outcomes.append(outcome)
        return outcomes

    # ------------------------------------------------------------------
    # Execução
    # ------------------------------------------------------------------

    def _analyze_file(
        self,
        path: Path,
        plugin_name: str,
        categories: list[str] | None,
        severity: str | None,
    ) -> AnalysisOutcome | None:
        """Executar um único plugin sobre um arquivo (mede duração)."""
        started = time.monotonic()
        options: dict[str, object] = {}
        if plugin_name == STRING_PLUGIN and categories:
            options["categories"] = categories
        try:
            result = self._manager.run(plugin_name, ScanContext(target=str(path), options=options))
        except PluginExecutionError:
            raise
        elapsed = (time.monotonic() - started) * 1000.0
        if severity and not _meets(result.max_severity(), severity):
            return None
        return AnalysisOutcome(
            plugin_name=plugin_name,
            result=result,
            target=str(path),
            duration_ms=elapsed,
        )

    def _analyze_combined(
        self,
        path: Path,
        categories: list[str] | None,
        severity: str | None,
    ) -> AnalysisOutcome:
        """Executar String + Entropy e mesclar resultados."""
        started = time.monotonic()
        options: dict[str, object] = {}
        if categories:
            options["categories"] = categories
        results = [
            self._manager.run(STRING_PLUGIN, ScanContext(target=str(path), options=options)),
            self._manager.run(ENTROPY_PLUGIN, ScanContext(target=str(path), options=options)),
        ]
        elapsed = (time.monotonic() - started) * 1000.0
        merged = self._merge(results)

        if severity and not _meets(merged.max_severity(), severity):
            merged = _blank_result(merged, path.name)
        outcome = AnalysisOutcome(
            plugin_name="combined",
            result=merged,
            target=str(path),
            duration_ms=elapsed,
        )
        return outcome

    def _merge(self, results: list[ScanResult]) -> ScanResult:
        """Mesclar múltiplos ScanResult em um consolidado.

        Ordena por severidade (desc) e deduplica por
        ``(severity, source, message)``.
        """
        if not results:
            raise ValueError("nenhum resultado para mesclar")
        base = results[0]
        findings: list[Evidence] = []
        for r in results:
            findings.extend(r.findings)

        seen: set[tuple[str, str, str]] = set()
        unique: list[Evidence] = []
        for finding in findings:
            key = (finding.severity.value, finding.source or "", finding.message)
            if key in seen:
                continue
            seen.add(key)
            unique.append(finding)
        unique.sort(key=lambda f: _SEVERITY_RANK[f.severity], reverse=True)

        stats: dict[str, int] = {}
        for r in results:
            for stat_key, value in r.stats.items():
                stats[stat_key] = stats.get(stat_key, 0) + value
        stats["total_combined"] = len(unique)

        observations = tuple(observation for r in results for observation in r.observations)[:96]

        return ScanResult(
            plugin_name="combined",
            plugin_version="1.0.0",
            timestamp=base.timestamp,
            summary=_combined_summary(results),
            findings=tuple(unique),
            stats=stats,
            observations=observations,
        )

    def history(
        self,
        *,
        plugin: str | None = None,
        severity: str | None = None,
        category: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, object]]:
        """Recuperar análises anteriores com filtros."""
        return self._store.list(
            plugin=plugin,
            severity=severity,
            category=category,
            since=since,
            limit=limit,
        )

    def get(self, analysis_id: str) -> dict[str, Any] | None:
        """Recuperar uma análise completa pelo id."""
        return self._store.get(analysis_id)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_names(self, names: list[str]) -> list[str]:
        """Filtrar para os plugins suportados e garantir registro."""
        known = [n for n in names if n in _SUPPORTED]
        if not known:
            raise PluginNotFoundError(f"nenhum analisador válido: {names}")
        self._register_defaults()
        return [n for n in names if n in _SUPPORTED]

    def _register_defaults(self) -> None:
        """Garantir que String e Entropy estejam registrados no manager."""
        for plugin in (_factory_str(), _factory_entropy()):
            if not self._manager.registry.contains(plugin.name):
                self._manager.register(plugin)

    def _collect_files(self, path: Path, recursive: bool) -> list[Path]:
        """Coletar arquivos a analisar (arquivo único ou diretório)."""
        if path.is_file():
            return [path]
        if not path.is_dir():
            return [path]  # deixa o plugin/leitura reportar erro real
        pattern = "**/*" if recursive else "*"
        return sorted(p for p in path.glob(pattern) if p.is_file())


# ----------------------------------------------------------------------
# Helpers de módulo
# ----------------------------------------------------------------------


def _factory_str() -> StringAnalyzerPlugin:
    """Instanciar o plugin de String (registro automático)."""
    return StringAnalyzerPlugin()


def _factory_entropy() -> EntropyAnalyzerPlugin:
    """Instanciar o plugin de Entropy (registro automático)."""
    return EntropyAnalyzerPlugin()


def _build_analysis_manager() -> PluginManager:
    """Construir um manager com String + Entropy registrados."""
    registry = PluginRegistry()
    registry.register(StringAnalyzerPlugin())
    registry.register(EntropyAnalyzerPlugin())
    return PluginManager(registry)


def _meets(severity: Severity, minimum: str) -> bool:
    """Verificar se a severidade atende ao limite mínimo."""
    try:
        minimum_sev = Severity(minimum.upper())
    except ValueError:
        return True
    return _SEVERITY_RANK[severity] >= _SEVERITY_RANK[minimum_sev]


def _combined_summary(results: list[ScanResult]) -> str:
    """Gerar um resumo legível para o resultado combinado."""
    names = ", ".join(f"{r.plugin_name} v{r.plugin_version}" for r in results)
    total = sum(len(r.findings) for r in results)
    return f"Análise combinada ({names}): {total} achado(s)."


def _to_record(outcome: AnalysisOutcome) -> AnalysisRecord:
    """Converter um outcome em record persistível."""
    result = outcome.result
    return AnalysisRecord(
        analysis_id=AnalysisStore.build_id(outcome.plugin_name),
        target=outcome.target,
        timestamp=result.timestamp.astimezone(UTC),
        plugin_name=outcome.plugin_name,
        severity=result.max_severity().value,
        evidence_count=len(result.findings),
        duration_ms=outcome.duration_ms,
        version=result.plugin_version,
        category=_derive_category(outcome.plugin_name),
        score=_entropy_score(result),
        result=result,
    )


def _entropy_score(result: ScanResult) -> int:
    """Extrair o score do resultado (entropy), se disponível."""
    try:
        return int(result.stats.get("score", 0))
    except (TypeError, ValueError):
        return 0


def _derive_category(plugin_name: str) -> str:
    """Derivar uma categoria de agregação por plugin."""
    if plugin_name == STRING_PLUGIN:
        return "string"
    if plugin_name == ENTROPY_PLUGIN:
        return "entropy"
    return "combined"


def _blank_result(reference: ScanResult, target_name: str) -> ScanResult:
    """Produzir um ScanResult vazio a partir de um de referência.

    Usado quando o resultado não atinge o limiar mínimo de severidade:
    preserva identidade do resultado original mas zera os achados.
    """
    return ScanResult(
        plugin_name=reference.plugin_name,
        plugin_version=reference.plugin_version,
        timestamp=reference.timestamp,
        summary=f"{target_name}: nenhum achado atende ao limiar.",
        findings=(),
        stats={"total": 0},
    )
