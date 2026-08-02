"""String Analyzer como plugin oficial do EDY Shield (v2.1 — M2.1).

Envolve a API pública do Core (:mod:`app.core.string`) como um
:class:`Plugin`, consumível via PluginManager — a mesma via dos demais
módulos. Nenhuma lógica de negócio fica na interface.

Detecta em arquivos de texto/scripts/logs: URLs, IPs, domínios, emails,
hashes, base64, hex, JWT, chaves de API, tokens Bearer, comandos
(PowerShell/Bash/CMD), downloads, execuções remotas, certificados PEM e
credenciais aparentes.

Mapeamento mudança → evidência: cada :class:`StringMatch` do Core vira um
:class:`Evidence` com ``severity`` traduzida (LOW/MEDIUM/HIGH/CRITICAL) e
``source`` = número da linha.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from app.core.filesystem.safe_path import resolve_safe_path
from app.core.string import StringCategory, analyze_text
from app.core.string.models import StringSeverity
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError

#: Categorias configuráveis via options (default: todas).
_CATEGORY_ALIASES: dict[str, StringCategory] = {
    category.value: category for category in StringCategory
}


class StringAnalyzerPlugin(Plugin):
    """Plugin que analisa strings e identifica indicadores suspeitos.

    Exemplo:

        plugin = StringAnalyzerPlugin()
        result = plugin.execute(ScanContext(target=Path("script.sh")))
    """

    name = "string_analyzer"
    version = "2.0.0"
    description = (
        "Analisa strings de arquivos de texto/scripts/logs e detecta URLs, IPs, "
        "hashes, chaves de API, tokens, comandos suspeitos e credenciais aparentes."
    )
    author = "EDY Shield Contributors"

    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Raises:
            PluginExecutionError: Se o target estiver ausente, não for arquivo
                legível ou contiver categorias inválidas.
        """
        if context.target is None:
            raise PluginExecutionError(
                "String Analyzer exige um arquivo como target.",
                plugin_name=self.name,
            )
        categories = context.options.get("categories")
        if categories is not None:
            invalid = [cat for cat in categories if str(cat).lower() not in _CATEGORY_ALIASES]
            if invalid:
                raise PluginExecutionError(
                    f"categorias inválidas: {invalid}. Válidas: {sorted(_CATEGORY_ALIASES)}.",
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
                f"String Analyzer não pôde acessar o arquivo: {exc}",
                plugin_name=self.name,
            ) from exc

    def execute(self, context: ScanContext) -> ScanResult:
        """Executar a análise e retornar um ScanResult com achados.

        Args:
            context: Contexto já validado.

        Returns:
            Resultado com evidências (tipo, categoria, linha) e estatísticas.
        """
        assert context.target is not None
        target = Path(str(context.target))
        resolved = resolve_safe_path(target, allowed_root=self._effective_root(target, context))

        encoding = str(context.options.get("encoding", "utf-8"))
        min_token_length = int(context.options.get("min_token_length", 256))
        categories = self._resolve_categories(context.options.get("categories"))

        try:
            text = resolved.read_text(encoding=encoding, errors="replace")
        except OSError as exc:
            raise PluginExecutionError(
                f"falha ao ler o arquivo: {exc}",
                plugin_name=self.name,
            ) from exc

        matches = analyze_text(text, categories=categories, min_token_length=min_token_length)

        findings = [
            Evidence(
                severity=self._to_severity(match.severity),
                message=f"{match.type.value}: {match.value}",
                source=f"linha {match.line}" if match.line is not None else None,
                metadata={
                    "category": match.category.value,
                    "type": match.type.value,
                    "severity": match.severity.value,
                    "confidence": f"{match.confidence:.2f}",
                },
            )
            for match in matches
        ]

        stats: dict[str, int] = {"total": len(matches)}
        for match in matches:
            stats[match.type.value] = stats.get(match.type.value, 0) + 1

        summary = (
            f"{len(matches)} achado(s) em {resolved.name}: "
            + ", ".join(f"{key}={value}" for key, value in stats.items() if key != "total")
            if matches
            else f"Nenhum achado em {resolved.name}."
        )

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=summary,
            findings=tuple(findings),
            stats=stats,
            observations=(f"Arquivo analisado: {resolved.name}",),
        )

    def health_check(self) -> bool:
        """O plugin está sempre pronto para executar (sem estado externo)."""
        return True

    @staticmethod
    def _resolve_categories(raw: object) -> list[StringCategory] | None:
        """Converter categorias das options em membros; None = todas.

        Recebe ``object`` porque ``ScanContext.options`` é ``dict[str, Any]``;
        é feito cast conservador a ``Iterable[object]`` antes de iterar
        (mantém mypy --strict sem alterar a assinatura do contrato).
        """
        if raw is None:
            return None
        if not isinstance(raw, (list, tuple)):
            return None
        return [_CATEGORY_ALIASES[str(cat).lower()] for cat in cast(Iterable[str], raw)]

    @staticmethod
    def _to_severity(severity: StringSeverity) -> Severity:
        """Traduzir a severidade do Core para a do plugin framework."""
        return Severity(severity.value)

    @staticmethod
    def _effective_root(target: Path, context: ScanContext) -> Path | None:
        """Derivar a raiz permitida (padrão ARES-QA-028)."""
        if context.allowed_root is not None:
            return context.allowed_root
        return target.resolve().parent
