"""File Integrity Monitor como plugin oficial do EDY Shield (Sprint 5 — v2.0).

Envolve a API pública do Core FIM (:mod:`app.core.fim`) como um
:class:`Plugin`, para que a **UI e a CLI consumam o FIM via PluginManager** —
a mesma via de todos os demais módulos (Missão 9). Nenhuma lógica de negócio
fica na interface.

Ações suportadas via ``context.options["action"]``:

* ``"baseline"`` (padrão) — cria uma baseline de integridade do alvo e
  persiste via :class:`FimStore`; retorna INFO com ``baseline_id``.
* ``"scan"`` — carrega a baseline (``options["baseline_id"]``), re-varrer o
  alvo e compara; retorna evidências por mudança (novo/modificado/removido).
* ``"compare"`` — compara duas baselines persistidas sem re-varrer o disco.

Mapeamento mudança → evidência (spec FIM, seção 5):

| Mudança          | Severity | message                     |
|------------------|----------|-----------------------------|
| Arquivo novo     | LOW      | ``arquivo novo: <path>``    |
| Modificação      | MEDIUM   | ``arquivo modificado: <path>`` |
| Remoção          | HIGH     | ``arquivo removido: <path>`` |
| Symlink ignorado | INFO     | ``symlink ignorado: <path>`` |
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from app.core.exceptions import EDYShieldError
from app.core.filesystem.safe_path import resolve_safe_path
from app.core.fim import FimStore, compare_baseline_snapshot, create_baseline, scan_snapshot
from app.core.fim.models import Baseline, BaselineEntry, FimDiff, Snapshot
from app.core.logging import get_logger
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError

#: Ações suportadas pelo plugin.
_ACTIONS = frozenset({"baseline", "scan", "compare"})

#: Algoritmos aceitos (whitelist do Core).
_ALGORITHMS = frozenset({"SHA256", "SHA1", "MD5"})

BaselineSink = Callable[[Baseline], object]
FimScanSink = Callable[[Baseline, Snapshot, FimDiff, str, int], object]
_logger = get_logger("plugins.file_integrity")


class FileIntegrityPlugin(Plugin):
    """Plugin que cria baselines de integridade e detecta mudanças no alvo.

    Exemplo:

        plugin = FileIntegrityPlugin()
        result = plugin.execute(
            ScanContext(
                target=Path("conf"),
                options={"action": "baseline", "algorithm": "SHA256"},
            )
        )
    """

    name = "file_integrity"
    version = "2.3.0"
    description = (
        "Cria baseline de integridade (hashes + metadados) e detecta "
        "modificação, criação e remoção de arquivos em varreduras posteriores."
    )
    author = "EDY Shield Contributors"

    def __init__(
        self,
        store: FimStore | None = None,
        *,
        baseline_sink: BaselineSink | None = None,
        scan_sink: FimScanSink | None = None,
    ) -> None:
        """Initialize the plugin with an optional FimStore.

        Args:
            store: Store de baselines; quando ``None``, usa o diretório
                padrão (``~/.edyshield/fim``).
        """
        self._store = store if store is not None else FimStore()
        self._baseline_sink = baseline_sink
        self._scan_sink = scan_sink

    @property
    def store(self) -> FimStore:
        """O FimStore usado pelo plugin."""
        return self._store

    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Raises:
            PluginExecutionError: Se a ação, o target ou o baseline_id
                forem inválidos/ausentes.
        """
        action = str(context.options.get("action", "baseline")).strip().lower()
        if action not in _ACTIONS:
            raise PluginExecutionError(
                f"File Integrity Monitor suporta ações {sorted(_ACTIONS)}; got {action!r}.",
                plugin_name=self.name,
            )

        algorithm = str(context.options.get("algorithm", "SHA256")).strip().upper()
        if algorithm not in _ALGORITHMS:
            raise PluginExecutionError(
                f"algoritmo inválido: {algorithm!r}. Use SHA256|SHA1|MD5.",
                plugin_name=self.name,
            )

        if action in ("baseline", "scan") and context.target is None:
            raise PluginExecutionError(
                "File Integrity Monitor exige um diretório ou arquivo como target.",
                plugin_name=self.name,
            )

        if action in ("scan", "compare") and not context.options.get("baseline_id"):
            raise PluginExecutionError(
                "File Integrity Monitor exige baseline_id nas ações scan/compare.",
                plugin_name=self.name,
            )

        if action == "compare" and not context.options.get("compare_id"):
            raise PluginExecutionError(
                "File Integrity Monitor exige compare_id na ação compare.",
                plugin_name=self.name,
            )

        # Validar o target na fronteira de segurança (padrão ARES-QA-028).
        if context.target is not None and action != "compare":
            target = Path(str(context.target))
            try:
                resolve_safe_path(
                    target,
                    allowed_root=self._effective_root(target, context),
                    strict=True,
                )
            except Exception as exc:
                raise PluginExecutionError(
                    f"File Integrity Monitor não pôde acessar o alvo: {exc}",
                    plugin_name=self.name,
                ) from exc

    def execute(self, context: ScanContext) -> ScanResult:
        """Executar a ação solicitada e retornar um ScanResult.

        Args:
            context: Contexto já validado.

        Returns:
            Resultado padronizado (baseline → INFO; scan/compare → evidências).
        """
        action = str(context.options.get("action", "baseline")).strip().lower()
        algorithm = str(context.options.get("algorithm", "SHA256")).strip().upper()
        recursive = bool(context.options.get("recursive", True))
        chunk_size = int(context.options.get("chunk_size", 65536))
        follow_symlinks = bool(context.options.get("follow_symlinks", False))

        if action == "baseline":
            return self._execute_baseline(context, algorithm, recursive, chunk_size)
        if action == "scan":
            return self._execute_scan(context, recursive, chunk_size, follow_symlinks)
        return self._execute_compare(context)

    def health_check(self) -> bool:
        """O plugin está pronto quando o diretório do store é gravável."""
        try:
            self._store.base_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return True

    # ------------------------------------------------------------------
    # Ações
    # ------------------------------------------------------------------

    def _execute_baseline(
        self,
        context: ScanContext,
        algorithm: str,
        recursive: bool,
        chunk_size: int,
    ) -> ScanResult:
        """Criar uma baseline e persistir no FimStore."""
        assert context.target is not None
        target = Path(str(context.target))
        try:
            baseline = create_baseline(
                target,
                algorithm=algorithm,
                recursive=recursive,
                allowed_root=self._effective_root(target, context),
                chunk_size=chunk_size,
            )
            baseline_id = self._store.save(baseline)
        except EDYShieldError as exc:
            raise PluginExecutionError(
                f"falha ao criar baseline: {exc}",
                plugin_name=self.name,
            ) from exc

        persisted = (
            baseline
            if baseline.baseline_id == baseline_id
            else replace(baseline, baseline_id=baseline_id)
        )
        self._notify_baseline(persisted)

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=f"Baseline criada: {len(baseline.entries)} arquivo(s) registrado(s).",
            stats={"entries": len(baseline.entries)},
            observations=(
                f"Baseline: {baseline_id}",
                f"Algoritmo: {baseline.algorithm}",
                f"Alvo: {baseline.root}",
            ),
        )

    def _execute_scan(
        self,
        context: ScanContext,
        recursive: bool,
        chunk_size: int,
        follow_symlinks: bool,
    ) -> ScanResult:
        """Carregar a baseline, re-varrer o alvo e comparar."""
        assert context.target is not None
        baseline_id = str(context.options["baseline_id"])
        baseline = self._load_baseline(baseline_id)

        target = Path(str(context.target))
        started = time.perf_counter()
        try:
            snapshot = scan_snapshot(
                target,
                algorithm=baseline.algorithm,
                recursive=recursive,
                allowed_root=self._effective_root(target, context),
                chunk_size=chunk_size,
                follow_symlinks=follow_symlinks,
            )
            diff = compare_baseline_snapshot(baseline, snapshot)
        except EDYShieldError as exc:
            raise PluginExecutionError(
                f"falha ao executar scan: {exc}",
                plugin_name=self.name,
            ) from exc

        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        self._notify_scan(
            baseline,
            snapshot,
            diff,
            f"scan-{uuid.uuid4()}",
            duration_ms,
        )

        findings, observations = self._diff_to_findings(diff, baseline, snapshot)
        stats = {
            "scanned": len(snapshot.entries),
            "added": len(diff.added),
            "modified": len(diff.modified),
            "removed": len(diff.removed),
            "unchanged": len(diff.unchanged),
            "ignored": len(diff.ignored),
        }
        summary = self._build_scan_summary(diff)

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=summary,
            findings=tuple(findings),
            stats=stats,
            observations=tuple(observations),
        )

    def _notify_baseline(self, baseline: Baseline) -> None:
        """Notify an optional durable telemetry sink without breaking FIM."""

        if self._baseline_sink is None:
            return
        try:
            self._baseline_sink(baseline)
        except Exception:
            _logger.exception("EDY SIEM baseline enqueue failed; local result was preserved")

    def _notify_scan(
        self,
        baseline: Baseline,
        snapshot: Snapshot,
        diff: FimDiff,
        scan_id: str,
        duration_ms: int,
    ) -> None:
        """Notify an optional durable telemetry sink without waiting for HTTP."""

        if self._scan_sink is None:
            return
        try:
            self._scan_sink(baseline, snapshot, diff, scan_id, duration_ms)
        except Exception:
            _logger.exception("EDY SIEM FIM enqueue failed; local result was preserved")

    def _execute_compare(self, context: ScanContext) -> ScanResult:
        """Comparar duas baselines persistidas (antes/depois)."""
        baseline_a = self._load_baseline(str(context.options["baseline_id"]))
        baseline_b = self._load_baseline(str(context.options["compare_id"]))
        snapshot_b = Snapshot.from_baseline(baseline_b)

        try:
            diff = compare_baseline_snapshot(baseline_a, snapshot_b)
        except EDYShieldError as exc:
            raise PluginExecutionError(
                f"falha ao comparar baselines: {exc}",
                plugin_name=self.name,
            ) from exc

        findings, observations = self._diff_to_findings(diff, baseline_a, snapshot_b)
        observations = [
            f"Baseline A: {baseline_a.baseline_id}",
            f"Baseline B: {baseline_b.baseline_id}",
            *observations,
        ]
        stats = {
            "scanned": len(snapshot_b.entries),
            "added": len(diff.added),
            "modified": len(diff.modified),
            "removed": len(diff.removed),
            "unchanged": len(diff.unchanged),
            "ignored": len(diff.ignored),
        }
        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=self._build_scan_summary(diff),
            findings=tuple(findings),
            stats=stats,
            observations=tuple(observations),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_baseline(self, baseline_id: str) -> Baseline:
        """Carregar uma baseline do store, traduzindo erros do domínio."""
        try:
            return self._store.load(baseline_id)
        except EDYShieldError as exc:
            raise PluginExecutionError(
                f"baseline inválida: {exc}",
                plugin_name=self.name,
            ) from exc

    @staticmethod
    def _diff_to_findings(
        diff: FimDiff,
        baseline: Baseline,
        snapshot: Snapshot,
    ) -> tuple[list[Evidence], list[str]]:
        """Converter um diff em evidências e observações (spec seção 5)."""
        baseline_map: dict[str, BaselineEntry] = {entry.path: entry for entry in baseline.entries}
        snapshot_map: dict[str, BaselineEntry] = {entry.path: entry for entry in snapshot.entries}

        findings: list[Evidence] = []
        for path in diff.added:
            entry = snapshot_map.get(path)
            findings.append(
                Evidence(
                    severity=Severity.LOW,
                    message=f"arquivo novo: {path}",
                    metadata={
                        "hexdigest": entry.hexdigest if entry else "",
                        "size_bytes": str(entry.size_bytes) if entry else "",
                    },
                )
            )
        for path in diff.modified:
            old = baseline_map.get(path)
            new = snapshot_map.get(path)
            findings.append(
                Evidence(
                    severity=Severity.MEDIUM,
                    message=f"arquivo modificado: {path}",
                    metadata={
                        "old_digest": old.hexdigest if old else "",
                        "new_digest": new.hexdigest if new else "",
                        "size_bytes": str(new.size_bytes) if new else "",
                    },
                )
            )
        for path in diff.removed:
            old = baseline_map.get(path)
            findings.append(
                Evidence(
                    severity=Severity.HIGH,
                    message=f"arquivo removido: {path}",
                    metadata={
                        "old_digest": old.hexdigest if old else "",
                        "size_bytes": str(old.size_bytes) if old else "",
                    },
                )
            )
        for path in diff.ignored:
            findings.append(
                Evidence(
                    severity=Severity.INFO,
                    message=f"symlink ignorado: {path}",
                    metadata={"target": "ignorado"},
                )
            )

        observations = [
            f"Baseline: {diff.baseline_id}",
            f"Algoritmo: {diff.algorithm}",
            f"Comparado em: {diff.scanned_at}",
        ]
        return findings, observations

    @staticmethod
    def _build_scan_summary(diff: FimDiff) -> str:
        """Resumo executivo do scan/compare."""
        if diff.changed == 0:
            return "Nenhuma mudança detectada — integridade preservada."
        return (
            f"{diff.changed} mudança(s) detectada(s): "
            f"{len(diff.added)} novo(s), {len(diff.modified)} modificado(s), "
            f"{len(diff.removed)} removido(s)."
        )

    @staticmethod
    def _effective_root(target: Path, context: ScanContext) -> Path | None:
        """Derivar a raiz permitida (padrão ARES-QA-028).

        Quando o chamador não define ``allowed_root``, a raiz é o próprio
        alvo (se diretório) ou o diretório pai (se arquivo) — permite
        processar qualquer caminho absoluto mantendo a contenção.
        """
        if context.allowed_root is not None:
            return context.allowed_root
        return target.resolve() if target.is_dir() else target.parent.resolve()
