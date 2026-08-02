"""File Integrity Monitor — Core FIM (Sprint 5 — FIM v2.0).

Módulo puro do Core (100% stdlib, ADR-001) que implementa:

* :mod:`app.core.fim.models` — modelos de domínio (Baseline, Snapshot, diff).
* :mod:`app.core.fim.baseline` — ``create_baseline``/``load_baseline``/
  ``save_baseline`` (APIs públicas).
* :mod:`app.core.fim.scanner` — ``scan_snapshot``/``compare_baseline_snapshot``.
* :mod:`app.core.fim.store` — :class:`FimStore` (persistência JSON).

Camada: importa **apenas** o Core existente (algorithms, crypto, filesystem,
exceptions, validators) — nunca services/plugins/ui (ADR-002).
"""

from app.core.fim.baseline import create_baseline, load_baseline, save_baseline
from app.core.fim.models import Baseline, BaselineEntry, ChangeType, FimDiff, Snapshot
from app.core.fim.scanner import compare_baseline_snapshot, scan_snapshot
from app.core.fim.store import DEFAULT_FIM_DIR, FimStore

__all__ = [
    "DEFAULT_FIM_DIR",
    "Baseline",
    "BaselineEntry",
    "ChangeType",
    "FimDiff",
    "FimStore",
    "Snapshot",
    "compare_baseline_snapshot",
    "create_baseline",
    "load_baseline",
    "save_baseline",
    "scan_snapshot",
]
