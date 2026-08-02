"""Modelos tipados do Alert Engine do EDY Shield (v2.1 -- M3-T01).

Definicoes fundamentais do motor de alertas, 100% stdlib (``dataclasses``,
``enum``, ``uuid``, ``hashlib``, ``datetime`` -- ADR-001/009).

A camada de Core nao conhece SQLite nem I/O de arquivos; toda a persistencia
e dispatch de canais fica em ``app/services/`` e ``app/core/alerts/channels.py``
respectivamente (estes ultimos usam apenas ``logging`` e ``pathlib`` da
stdlib).

Hierarquia de modelos:

* :class:`Severity` -- nivel de impacto do alerta (INFO..CRITICAL).
* :class:`AlertStatus` -- estado do ciclo de vida (NEW..SUPPRESSED).
* :class:`AlertAction` -- acao de ciclo de vida executavel.
* :class:`AlertRecord` -- instancia de um alerta (persistida pelo store).
* :class:`AlertRule` -- regra configuravel avaliada pelo engine.
* :class:`AlertEvent` -- evento bruto de entrada (pre-rule evaluation).
* :class:`AlertSource` -- constantes canonicas de origem (FIM, analyzers...).

Referencia: ``docs/M3_ALERT_ENGINE_ARCHITECTURE.md`` (secao 4.1).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "AlertAction",
    "AlertEvent",
    "AlertRecord",
    "AlertRule",
    "AlertSource",
    "AlertStatus",
    "Severity",
    "compute_fingerprint",
    "now_iso",
    "severity_rank",
]


class Severity(StrEnum):
    """Nivel de impacto de um alerta.

    Ordenado do menor para o maior impacto. ``StrEnum`` permite
    serializacao JSON direta (``json.dumps(Severity.HIGH)`` -> ``"HIGH"``)
    e comparacao lexicografica trivial com bancos SQLite (TEXT).
    """

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertStatus(StrEnum):
    """Estado do ciclo de vida de um alerta.

    Transicoes validas (gerenciadas pelo :class:`~app.services.alert_service.AlertService`):

    * ``NEW`` -> ``ACKNOWLEDGED`` (ack)
    * ``ACKNOWLEDGED`` -> ``RESOLVED`` (resolve)
    * ``NEW`` ou ``ACKNOWLEDGED`` -> ``SUPPRESSED`` (suppress)
    * ``SUPPRESSED`` ou ``RESOLVED`` -> ``NEW`` (reopen)
    """

    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"


class AlertAction(StrEnum):
    """Acao de ciclo de vida executavel sobre um alerta."""

    ACKNOWLEDGE = "acknowledge"
    RESOLVE = "resolve"
    SUPPRESS = "suppress"
    REOPEN = "reopen"


class AlertSource:
    """Constantes canonicas de origem de eventos de alerta.

    Atribuido a :attr:`AlertEvent.source` e :attr:`AlertRecord.source`.
    Sao strings simples (nao Enum) para permitir fontes customizadas de
    plugins de terceiros sem modificacao do Core (Open-Closed).
    """

    FIM = "fim"
    STRING_ANALYZER = "string_analyzer"
    ENTROPY_ANALYZER = "entropy_analyzer"
    LOG_ANALYZER = "log_analyzer"
    MANUAL = "manual"


def severity_rank(severity: Severity) -> int:
    """Retornar rank numerico de severidade (0=INFO, 4=CRITICAL).

    Usado para ordenacao descendente e comparacao de severidade no
    :class:`~app.core.alerts.engine.AlertEngine`.
    """
    ranks: dict[Severity, int] = {
        Severity.INFO: 0,
        Severity.LOW: 1,
        Severity.MEDIUM: 2,
        Severity.HIGH: 3,
        Severity.CRITICAL: 4,
    }
    return ranks[severity]


def now_iso() -> str:
    """Retornar timestamp UTC atual em formato ISO-8601 (timezone-aware)."""
    return datetime.now(UTC).isoformat()


def compute_fingerprint(source: str, rule_id: str, target: str) -> str:
    """Calcular fingerprint deterministico SHA-256 de um alerta.

    O fingerprint agrupa eventos identicos (mesma origem, mesma regra,
    mesmo alvo) em uma unica instancia de alerta, possibilitando a
    deduplicacao por janela temporal (ADR-010).

    Args:
        source: Origem canonica do evento (ex.: ``"fim"``).
        rule_id: Identificador da regra que disparou o alerta.
        target: Recurso afetado (caminho de arquivo, hostname, etc.).

    Returns:
        Hash SHA-256 hexadecimal de 64 caracteres.
    """
    payload = f"{source}|{rule_id}|{target}".encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(slots=True)
class AlertEvent:
    """Evento bruto de entrada para o AlertEngine.

    Representa um acontecimento observable (mudanca de arquivo, achado
    de scanner, linha de log suspeita) **antes** da avaliacao de regras.
    O :class:`~app.core.alerts.engine.AlertEngine` consome eventos e
    produz :class:`AlertRecord` quando uma regra corresponde.

    Attributes:
        source: Origem canonica (ex.: :attr:`AlertSource.FIM`).
        event_type: Tipo do evento (ex.: ``"file_modified"``,
            ``"string_match"``, ``"high_entropy"``).
        severity: Severidade sugerida pelo produtor do evento.
        target: Recurso afetado (arquivo, diretorio, host).
        data: Metadados livres do evento (passados para avaliacao de
            regras como ``condition_key``).
        timestamp: Momento do evento (ISO-8601 UTC); ``None`` usa agora.
    """

    source: str
    event_type: str
    severity: Severity
    target: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=now_iso)


@dataclass(slots=True)
class AlertRule:
    """Regra configuravel avaliada pelo AlertEngine.

    Uma rega mapeia eventos que satisfazem uma **condicao** sobre seus
    metadados (``data[condition_key]``) para uma severidade alvo e
    templates de titulo/descricao. Regras sao avaliadas em ordem de
    prioridade (definida pelo :class:`~app.core.alerts.rules.RuleRegistry`).

    Attributes:
        rule_id: Identificador unico da regra.
        name: Nome exibivel da regra.
        source: Origem a que a regra se aplica (``"*"`` = todas).
        condition_key: Chave em ``AlertEvent.data`` a testar.
        operator: Operador de comparacao (``"eq"``, ``"ne"``, ``"gt"``,
            ``"gte"``, ``"lt"``, ``"lte"``, ``"contains"``, ``"regex"``,
            ``"in"``).
        condition_value: Valor de comparacao (semantica depende do
            operador).
        target_severity: Severidade atribuida ao alerta quando a regra
            corresponde.
        title_template: Template de titulo (suporta ``{target}``,
            ``{source}``, ``{event_type}`` via ``str.format_map``).
        description_template: Template de descricao (mesma substituicao).
        enabled: Se ``False``, a regra e ignorada pelo engine.
        suppression_window_seconds: Janela de dedup/supressao em
            segundos (default 300 = 5 minutos). ADR-010.
        priority: Ordem de avaliacao (menor = avaliada primeiro).
    """

    rule_id: str
    name: str
    source: str
    condition_key: str
    operator: str
    condition_value: Any
    target_severity: Severity
    title_template: str
    description_template: str
    enabled: bool = True
    suppression_window_seconds: int = 300
    priority: int = 100


@dataclass(slots=True)
class AlertRecord:
    """Instancia de um alerta (saida do AlertEngine).

    Um :class:`AlertRecord` e produzido quando um :class:`AlertEvent`
    corresponde a uma :class:`AlertRule` e nao e deduplicado por
    fingerprint temporal. Persistido pelo
    :class:`~app.services.alert_store.AlertStore` em SQLite.

    Attributes:
        alert_id: Identificador unico (``ALT-<12 hex upper>``).
        fingerprint: Hash SHA-256 de ``(source, rule_id, target)`` --
            chave de deduplicacao (ADR-010).
        title: Titulo formatado a partir do template da regra.
        description: Descricao formatada a partir do template da regra.
        source: Origem canonica do evento.
        rule_id: Regra que disparou o alerta.
        severity: Severidade final do alerta.
        status: Estado do ciclo de vida (default :attr:`AlertStatus.NEW`).
        target: Recurso afetado.
        count: Quantidade de eventos deduplicados neste alerta.
        first_seen_at: Timestamp ISO-8601 da primeira ocorrencia.
        last_seen_at: Timestamp ISO-8601 da ultima ocorrencia.
        details: Metadados livres do evento original (para auditoria).
        acknowledged_at: Quando foi reconhecido (``None`` se nao).
        acknowledged_by: Quem reconheceu (``None`` se nao).
        resolved_at: Quando foi resolvido (``None`` se nao).
        resolved_by: Quem resolveu (``None`` se nao).
        resolution_note: Nota de resolucao (``None`` se nao).
    """

    alert_id: str = field(default_factory=lambda: f"ALT-{uuid.uuid4().hex[:12].upper()}")
    fingerprint: str = ""
    title: str = ""
    description: str = ""
    source: str = ""
    rule_id: str = "DEFAULT"
    severity: Severity = Severity.MEDIUM
    status: AlertStatus = AlertStatus.NEW
    target: str = ""
    count: int = 1
    first_seen_at: str = field(default_factory=now_iso)
    last_seen_at: str = field(default_factory=now_iso)
    details: dict[str, Any] = field(default_factory=dict)
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializar para dicionario (para persistencia JSON/SQLite).

        Converte enums para ``.value`` e mantem ``details`` como dict
        (serializado a parte pelo store via ``json.dumps``).
        """
        return {
            "alert_id": self.alert_id,
            "fingerprint": self.fingerprint,
            "title": self.title,
            "description": self.description,
            "source": self.source,
            "rule_id": self.rule_id,
            "severity": self.severity.value,
            "status": self.status.value,
            "target": self.target,
            "count": self.count,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "details": self.details,
            "acknowledged_at": self.acknowledged_at,
            "acknowledged_by": self.acknowledged_by,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
        }

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> AlertRecord:
        """Deserializar a partir de dicionario (linha do SQLite/JSON).

        Converte strings de severidade/status de volta para enums.
        ``details`` pode ser string JSON (do SQLite TEXT) ou dict.
        """
        import json

        raw_details = row["details"]
        if isinstance(raw_details, str):
            details: dict[str, Any] = json.loads(raw_details) if raw_details else {}
        else:
            details = dict(raw_details) if raw_details else {}

        severity_str = str(row["severity"])
        status_str = str(row["status"])
        return cls(
            alert_id=str(row["alert_id"]),
            fingerprint=str(row["fingerprint"]),
            title=str(row["title"]),
            description=str(row["description"]),
            source=str(row["source"]),
            rule_id=str(row["rule_id"]),
            severity=Severity(severity_str),
            status=AlertStatus(status_str),
            target=str(row["target"]),
            count=int(row["count"]),
            first_seen_at=str(row["first_seen_at"]),
            last_seen_at=str(row["last_seen_at"]),
            details=details,
            acknowledged_at=row["acknowledged_at"]
            if isinstance(row.get("acknowledged_at"), str)
            else None,
            acknowledged_by=row["acknowledged_by"]
            if isinstance(row.get("acknowledged_by"), str)
            else None,
            resolved_at=row["resolved_at"] if isinstance(row.get("resolved_at"), str) else None,
            resolved_by=row["resolved_by"] if isinstance(row.get("resolved_by"), str) else None,
            resolution_note=row["resolution_note"]
            if isinstance(row.get("resolution_note"), str)
            else None,
        )


# --- Helpers internos de avaliacao de templates -------------------------- #

_SAFE_FORMAT_KEYS: frozenset[str] = frozenset(
    {"target", "source", "event_type", "rule_id", "severity"}
)


def render_template(template: str, event: AlertEvent, rule: AlertRule) -> str:
    """Renderizar um template de titulo/descricao com valores do evento.

    Usa ``str.format_map`` com um ``SafeDict`` que preserva chaves nao
    encontradas como ``{chave}`` (evita ``KeyError`` em templates com
    placeholders opcionais). Apenas chaves explicitamente seguras sao
    substituidas (``target``, ``source``, ``event_type``, ``rule_id``,
    ``severity``) -- nao expoe metadados arbitrarios do evento para
    evitar injecao de template (defesa em profundidade).

    Args:
        template: String-template com placeholders ``{chave}``.
        event: Evento de origem.
        rule: Regra que correspondeu.

    Returns:
        Template renderizado.
    """
    safe_values: dict[str, str] = {
        "target": event.target,
        "source": event.source,
        "event_type": event.event_type,
        "rule_id": rule.rule_id,
        "severity": rule.target_severity.value,
    }
    return _safe_format(template, safe_values)


class _SafeDict(dict[str, str]):
    """Dict que retorna ``{key}`` para chaves ausentes (format safety)."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _safe_format(template: str, values: Mapping[str, str]) -> str:
    """Formatar string com valores seguros, preservando chaves ausentes."""
    # Validar que o template nao contem chaves perigosas (format spec injection)
    # Permitindo apenas chaves alfanumericas + underscore.
    if not re.fullmatch(r"[^{}]*(\{[a-zA-Z_][a-zA-Z0-9_]*\}[^{}]*)*", template):
        # Template com chaves invalidas -- retornar literal
        return template
    return template.format_map(_SafeDict(values))
