"""Pacote do Alert Engine do EDY Shield (v2.1 -- M3).

Exporta as classes publicas do Core de alertas para uso externo,
mantendo encapsulamento de implementacao (conforme ADR-009).
"""

from app.core.alerts.channels import (
    BaseAlertChannel,
    CompositeChannel,
    ConsoleChannel,
    FileChannel,
    NullChannel,
)
from app.core.alerts.deduplicator import DedupCache, try_dedup
from app.core.alerts.engine import AlertEngine, EngineResult
from app.core.alerts.models import (
    AlertAction,
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertSource,
    AlertStatus,
    Severity,
    compute_fingerprint,
    now_iso,
    severity_rank,
)
from app.core.alerts.rules import OPERATORS, RuleRegistry, default_rules

__all__ = [
    "ENGINE_OPERATORS",
    "OPERATORS",
    "AlertAction",
    "AlertEngine",
    "AlertEvent",
    "AlertRecord",
    "AlertRule",
    "AlertSource",
    "AlertStatus",
    "BaseAlertChannel",
    "CompositeChannel",
    "ConsoleChannel",
    "DedupCache",
    "EngineResult",
    "FileChannel",
    "NullChannel",
    "RuleRegistry",
    "Severity",
    "compute_fingerprint",
    "default_rules",
    "now_iso",
    "severity_rank",
    "try_dedup",
]
