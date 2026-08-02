"""Contratos do plugin framework do EDY Shield (Sprint 3, Missão 6).

Modelos compartilhados usados por **todos** os plugins e pelo
:class:`PluginManager`:

* :class:`Severity` — nível de severidade de um achado.
* :class:`Evidence` — um achado individual da varredura.
* :class:`ScanContext` — entrada fornecida ao plugin para uma execução.
* :class:`ScanResult` — resultado padronizado retornado por qualquer plugin.

Seguem o mesmo estilo do Core (ADR-002): dataclasses ``frozen=True,
slots=True``, tipagem estrita e sem dependências de UI/services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class Severity(Enum):
    """Nível de severidade de um achado de varredura.

    Ordenado do menor para o maior impacto (INFO < LOW < MEDIUM < HIGH <
    CRITICAL) — a ordenação é usada para calcular a severidade máxima de um
    :class:`ScanResult`.
    """

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class Evidence:
    """Um achado individual produzido por um plugin.

    Attributes:
        severity: Nível de severidade do achado.
        message: Descrição legível do achado.
        source: Local de origem (ex.: ``"linha 42"``) ou ``None``.
        metadata: Dados adicionais livres (ex.: o texto que disparou o
            achado), sem hierarquia imposta pelo framework.
    """

    severity: Severity
    message: str
    source: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ScanContext:
    """Entrada fornecida a um plugin para executar uma varredura.

    Attributes:
        target: Caminho ou conteúdo alvo da varredura (``None`` quando o
            plugin usa apenas ``options``).
        options: Opções específicas do plugin (ex.: encoding, limites).
        allowed_root: Raiz permitida para operações de arquivo; ``None``
            usa o diretório de trabalho atual (padrão do Core).
    """

    target: str | Path | None = None
    options: dict[str, Any] = field(default_factory=dict)
    allowed_root: Path | None = None


@dataclass(frozen=True, slots=True)
class ScanResult:
    """Resultado padronizado retornado por um plugin após a execução.

    Attributes:
        plugin_name: Nome do plugin que produziu o resultado.
        plugin_version: Versão do plugin.
        timestamp: Momento da execução (timezone-aware, UTC).
        summary: Resumo executivo da varredura.
        findings: Evidências/achados da varredura (ordenados).
        stats: Estatísticas agregadas (ex.: contagem por severidade).
        observations: Observações livres da execução (avisos, limites
            atingidos, contexto).
    """

    plugin_name: str
    plugin_version: str
    timestamp: datetime
    summary: str
    findings: tuple[Evidence, ...] = ()
    stats: dict[str, int] = field(default_factory=dict)
    observations: tuple[str, ...] = ()

    def max_severity(self) -> Severity:
        """Retornar a maior severidade entre os achados.

        Returns:
            A severidade mais alta presente em ``findings``, ou
            :attr:`Severity.INFO` quando não há achados.
        """
        if not self.findings:
            return Severity.INFO
        return max(
            (finding.severity for finding in self.findings),
            key=lambda s: _SEVERITY_RANK[s],
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanResult:
        """Reconstruir um ScanResult a partir de ``as_dict()``.

        Permite persistir e carregar resultados (ex.: histórico da UI —
        Missão 9).

        Args:
            data: Dicionário produzido por :meth:`as_dict`.

        Returns:
            Uma nova instância de :class:`ScanResult`.
        """
        return cls(
            plugin_name=data["plugin_name"],
            plugin_version=data["plugin_version"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            summary=data["summary"],
            findings=tuple(
                Evidence(
                    severity=Severity(finding["severity"]),
                    message=finding["message"],
                    source=finding.get("source"),
                    metadata=dict(finding.get("metadata") or {}),
                )
                for finding in data.get("findings", [])
            ),
            stats=dict(data.get("stats") or {}),
            observations=tuple(data.get("observations") or []),
        )

    def as_dict(self) -> dict[str, Any]:
        """Serializar o resultado para estruturas nativas (JSON-friendly).

        Returns:
            Dicionário com todos os campos, com ``timestamp`` em ISO 8601
            (UTC) e ``findings``/``observations`` como listas.
        """
        return {
            "plugin_name": self.plugin_name,
            "plugin_version": self.plugin_version,
            "timestamp": self.timestamp.astimezone(UTC).isoformat(),
            "summary": self.summary,
            "max_severity": self.max_severity().value,
            "findings": [
                {
                    "severity": finding.severity.value,
                    "message": finding.message,
                    "source": finding.source,
                    "metadata": dict(finding.metadata),
                }
                for finding in self.findings
            ],
            "stats": dict(self.stats),
            "observations": list(self.observations),
        }


#: Ordem canônica de severidade (usada em ordenações e no ``max``).
_SEVERITY_RANK: dict[Severity, int] = {
    Severity.INFO: 0,
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}
