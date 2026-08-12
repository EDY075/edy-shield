"""Entropy Analyzer como plugin oficial do EDY Shield (v2.1 — M2.2).

Envolve a API pública do Core (:mod:`app.core.entropy`) como um
:class:`Plugin`, consumível via PluginManager — a mesma via dos demais
módulos. Nenhuma lógica de negócio fica na interface.

Mede a entropia de Shannon de arquivos/textos e sinaliza conteúdos com
alta aleatoriedade (dados codificados, compactados, criptografados ou
ofuscados). Cada métrica relevante do Core (total, blocos) vira uma
:class:`Evidence` com ``severity`` mapeada (LOW/MEDIUM/HIGH) e ``source``
legível.

Mapeamento severidade do Core -> framework:
    EntropyLevel.LOW    -> Severity.LOW
    EntropyLevel.MEDIUM -> Severity.MEDIUM
    EntropyLevel.HIGH   -> Severity.HIGH
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.entropy import (
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MIN_BLOCK_SIZE,
    EntropyLevel,
    analyze_file_entropy,
)
from app.core.filesystem.safe_path import resolve_safe_path
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError


class EntropyAnalyzerPlugin(Plugin):
    """Plugin que analisa a entropia de arquivos e detecta aleatoriedade alta.

    Exemplo:

        plugin = EntropyAnalyzerPlugin()
        result = plugin.execute(ScanContext(target=Path("dados.bin.txt")))
    """

    name = "entropy_analyzer"
    version = "2.3.0"
    description = (
        "Mede a entropia de Shannon de arquivos de texto e sinaliza "
        "conteúdos de alta aleatoriedade (dados codificados, compactados, "
        "criptografados ou ofuscados)."
    )
    author = "EDY Shield Contributors"

    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Raises:
            PluginExecutionError: Se o target estiver ausente, não for
                arquivo legível ou as opções forem inválidas.
        """
        if context.target is None:
            raise PluginExecutionError(
                "Entropy Analyzer exige um arquivo como target.",
                plugin_name=self.name,
            )

        target = Path(str(context.target))
        try:
            resolve_safe_path(
                target,
                allowed_root=self._effective_root(target, context),
                strict=True,
            )
        except Exception as exc:
            raise PluginExecutionError(
                f"Entropy Analyzer não pôde acessar o arquivo: {exc}",
                plugin_name=self.name,
            ) from exc

    def execute(self, context: ScanContext) -> ScanResult:
        """Executar a análise e retornar um ScanResult com achados.

        Args:
            context: Contexto já validado.

        Returns:
            Resultado com evidências (nível, entropia) e estatísticas.
        """
        assert context.target is not None
        target = Path(str(context.target))
        resolved = resolve_safe_path(target, allowed_root=self._effective_root(target, context))

        encoding = str(context.options.get("encoding", "utf-8"))
        low = float(context.options.get("threshold_low", DEFAULT_LOW_THRESHOLD))
        high = float(context.options.get("threshold_high", DEFAULT_HIGH_THRESHOLD))
        min_block = int(context.options.get("min_block_size", DEFAULT_MIN_BLOCK_SIZE))

        result = analyze_file_entropy(
            resolved,
            encoding=encoding,
            threshold_low=low,
            threshold_high=high,
            min_block_size=min_block,
        )

        # Evidência principal (total) sempre presente.
        findings = [
            Evidence(
                severity=self._to_severity(result.level),
                message=result.justification,
                source="total",
                metadata={
                    "entropy": f"{result.total_entropy:.2f}",
                    "level": result.level.value,
                    "size": str(result.total_size),
                    "score": str(result.score),
                },
            )
        ]
        # Métricas por bloco (evidências secundárias), apenas não-total.
        for metric in result.metrics:
            if metric.unit.value == "total":
                continue
            findings.append(
                Evidence(
                    severity=self._to_severity(metric.level),
                    message=metric.justification,
                    source=metric.label,
                    metadata={
                        "entropy": f"{metric.entropy:.2f}",
                        "level": metric.level.value,
                        "size": str(metric.size),
                        "unit": metric.unit.value,
                    },
                )
            )

        stats: dict[str, int] = {
            "total_metrics": len(result.metrics),
            "score": result.score,
            "blocs_high": sum(
                1
                for m in result.metrics
                if m.unit.value == "block" and m.level is EntropyLevel.HIGH
            ),
        }

        summary = (
            f"Entropia {result.total_entropy:.2f} bits/unidade "
            f"({result.level.value}, score {result.score}/100) em "
            f"{result.target}."
        )

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=summary,
            findings=tuple(findings),
            stats=stats,
            observations=(f"Medida total: {result.total_entropy:.2f} bits/unidade.",),
        )

    def health_check(self) -> bool:
        """O plugin está sempre pronto para executar (sem estado externo)."""
        return True

    @staticmethod
    def _to_severity(level: EntropyLevel) -> Severity:
        """Traduzir o nível do Core para a severidade do plugin framework."""
        mapping: dict[EntropyLevel, Severity] = {
            EntropyLevel.LOW: Severity.LOW,
            EntropyLevel.MEDIUM: Severity.MEDIUM,
            EntropyLevel.HIGH: Severity.HIGH,
        }
        return mapping[level]

    @staticmethod
    def _effective_root(target: Path, context: ScanContext) -> Path | None:
        """Derivar a raiz permitida (padrão ARES-QA-028)."""
        if context.allowed_root is not None:
            return context.allowed_root
        return target.resolve().parent
