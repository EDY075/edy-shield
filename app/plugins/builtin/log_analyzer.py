"""Log Analyzer — primeiro plugin oficial do EDY Shield (Sprint 3, Missão 7).

Analisa arquivos de log (``.log``/``.txt``) e detecta padrões de segurança
e operação comuns:

* ``FAILED LOGIN`` — tentativas de login falhas (severidade HIGH).
* ``SUCCESS LOGIN`` — logins bem-sucedidos (severidade LOW).
* ``ERROR`` — erros de aplicação (severidade MEDIUM).
* ``WARNING`` — avisos (severidade LOW).
* ``CRITICAL`` — falhas críticas (severidade CRITICAL).

Gera um :class:`ScanResult` com evidências por ocorrência, estatísticas
agregadas (quantidade por categoria, horário inicial/final) e observações.

Regras de arquitetura (Missão 7):

* Implementa a interface :class:`app.plugins.plugin_base.Plugin`.
* Reutiliza a fronteira de segurança do Core
  (:func:`app.core.filesystem.safe_path.resolve_safe_path`) para conter o
  arquivo na raiz permitida — nunca lê caminhos fora dela.
* Não contém lógica de UI; é consumido pelo PluginManager (Missão 9).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from app.core.filesystem.safe_path import resolve_safe_path
from app.plugins.contracts import Evidence, ScanContext, ScanResult, Severity
from app.plugins.plugin_base import Plugin
from app.plugins.plugin_errors import PluginExecutionError

#: Padrões de detecção por categoria (case-insensitive).
_PATTERNS: dict[str, tuple[Severity, re.Pattern[str]]] = {
    "failed_login": (Severity.HIGH, re.compile(r"FAILED LOGIN", re.IGNORECASE)),
    "success_login": (Severity.LOW, re.compile(r"SUCCESS LOGIN", re.IGNORECASE)),
    "error": (Severity.MEDIUM, re.compile(r"ERROR", re.IGNORECASE)),
    "warning": (Severity.LOW, re.compile(r"WARNING", re.IGNORECASE)),
    "critical": (Severity.CRITICAL, re.compile(r"CRITICAL", re.IGNORECASE)),
}

#: Regex de timestamp comum em logs: ``2026-08-01 10:15:30`` (no começo ou
#: entre colchetes/parênteses). Opcional — quando não há match, horário
#: inicial/final fica ``None``.
_TIMESTAMP_RE = re.compile(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})")

#: Extensões aceitas para leitura de logs.
_SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".log", ".txt"})


class LogAnalyzer(Plugin):
    """Analisa logs e gera um ScanResult com achados e estatísticas.

    Exemplo:

        analyzer = LogAnalyzer()
        result = analyzer.execute(ScanContext(target=Path("auth.log")))
    """

    name = "log_analyzer"
    version = "1.1.0"
    description = (
        "Analisa arquivos de log e detecta falhas de login, erros, avisos e eventos críticos."
    )
    author = "EDY Shield Contributors"

    def validate(self, context: ScanContext) -> None:
        """Validar o contexto antes da execução.

        Args:
            context: Contexto com ``target`` (caminho do log).

        Raises:
            PluginExecutionError: Se ``target`` não for informado, não for
                suportado (extensão) ou não existir dentro da raiz.
        """
        if context.target is None:
            raise PluginExecutionError(
                "Log Analyzer exige um arquivo de log como target.",
                plugin_name=self.name,
            )
        target = Path(context.target)
        if target.suffix.lower() not in _SUPPORTED_SUFFIXES:
            raise PluginExecutionError(
                f"Log Analyzer suporta apenas extensões "
                f"{sorted(_SUPPORTED_SUFFIXES)}; got {target.suffix!r}.",
                plugin_name=self.name,
            )
        try:
            resolve_safe_path(
                target, allowed_root=self._effective_root(target, context), strict=True
            )
        except Exception as exc:
            raise PluginExecutionError(
                f"Log Analyzer não pôde acessar o arquivo: {exc}",
                plugin_name=self.name,
            ) from exc

    def execute(self, context: ScanContext) -> ScanResult:
        """Executar a análise do log e retornar um ScanResult.

        Args:
            context: Contexto já validado.

        Returns:
            Resultado com evidências e estatísticas.
        """
        assert context.target is not None
        target = Path(context.target)
        resolved = resolve_safe_path(target, allowed_root=self._effective_root(target, context))

        findings: list[Evidence] = []
        stats: dict[str, int] = {
            "failed_login": 0,
            "success_login": 0,
            "error": 0,
            "warning": 0,
            "critical": 0,
        }
        timestamps: list[datetime] = []

        encoding = context.options.get("encoding", "utf-8")
        max_lines = int(context.options.get("max_lines", 0))  # 0 = ilimitado

        line_no = 0
        truncated = False
        with resolved.open("r", encoding=encoding, errors="replace") as handle:
            for line in handle:
                line_no += 1
                if max_lines > 0 and line_no > max_lines:
                    truncated = True
                    break

                stamp = _extract_timestamp(line)
                if stamp is not None:
                    timestamps.append(stamp)

                for category, (severity, pattern) in _PATTERNS.items():
                    if pattern.search(line):
                        stats[category] += 1
                        findings.append(
                            Evidence(
                                severity=severity,
                                message=_message_for(category),
                                source=f"linha {line_no}",
                                metadata={"line": str(line_no), "category": category},
                            )
                        )

        summary = _build_summary(stats, line_no, truncated)
        observations = _build_observations(timestamps, resolved, truncated, max_lines)

        return ScanResult(
            plugin_name=self.name,
            plugin_version=self.version,
            timestamp=datetime.now(UTC),
            summary=summary,
            findings=tuple(findings),
            stats=stats,
            observations=tuple(observations),
        )

    def health_check(self) -> bool:
        """O plugin está sempre pronto para executar (sem estado externo)."""
        return True

    @staticmethod
    def _effective_root(target: Path, context: ScanContext) -> Path | None:
        """Derivar a raiz permitida para a leitura do arquivo.

        Segue o padrão do Hash Checker (ARES-QA-028): quando o chamador não
        define ``allowed_root``, a raiz passa a ser o **diretório pai do
        arquivo alvo** — permite analisar qualquer caminho absoluto mantendo
        a contenção da fronteira (nada fora do diretório do arquivo é
        permitido).

        Args:
            target: Caminho fornecido pelo usuário.
            context: Contexto da varredura (pode conter ``allowed_root``).

        Returns:
            Raiz efetiva (``Path``) ou ``None`` quando o próprio contexto a
            define como ``None`` (usa cwd — comportamento padrão do Core).
        """
        if context.allowed_root is not None:
            return context.allowed_root
        return target.parent


def _extract_timestamp(line: str) -> datetime | None:
    """Extrair o primeiro timestamp ISO-like de uma linha de log.

    Args:
        line: Linha do arquivo de log.

    Returns:
        :class:`datetime` quando há match, ``None`` caso contrário.
    """
    match = _TIMESTAMP_RE.search(line)
    if match is None:
        return None
    try:
        return datetime.fromisoformat(match.group(1))
    except ValueError:
        return None


def _message_for(category: str) -> str:
    """Mensagem legível para uma categoria de achado."""
    return {
        "failed_login": "Tentativa de login falhou (possível força bruta).",
        "success_login": "Login bem-sucedido registrado.",
        "error": "Erro registrado no log.",
        "warning": "Aviso registrado no log.",
        "critical": "Evento crítico registrado no log.",
    }[category]


def _build_summary(stats: dict[str, int], total_lines: int, truncated: bool) -> str:
    """Construir o resumo executivo da análise."""
    total_events = sum(stats.values())
    if total_events == 0:
        return f"Nenhum evento de interesse detectado em {total_lines} linhas."
    suffix = " (análise truncada por limite de linhas)" if truncated else ""
    return (
        f"{total_events} evento(s) detectado(s) em {total_lines} linhas"
        f"{suffix}: {stats['failed_login']} falha(s) de login, "
        f"{stats['success_login']} login(s) com sucesso, "
        f"{stats['error']} erro(s), {stats['warning']} aviso(s), "
        f"{stats['critical']} crítico(s)."
    )


def _build_observations(
    timestamps: list[datetime],
    resolved: Path,
    truncated: bool,
    max_lines: int,
) -> list[str]:
    """Construir observações da execução (horário inicial/final etc.)."""
    observations: list[str] = [f"Arquivo analisado: {resolved.name}"]
    if timestamps:
        observations.append(
            "Janela de tempo: "
            f"{min(timestamps).isoformat(timespec='seconds')} → "
            f"{max(timestamps).isoformat(timespec='seconds')}"
        )
    if truncated:
        observations.append(
            f"Leitura limitada às primeiras {max_lines} linhas (config max_lines) — análise truncada."
        )
    return observations
