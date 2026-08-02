"""Entropy Analyzer do EDY Shield (v2.1 — M2.2).

Módulo puro do Core (100% stdlib, ADR-001) que mede a **entropia de
Shannon** de textos e arquivos para sinalizar conteúdos com alta
aleatoriedade — indícios de dados codificados, compactados,
criptografados ou ofuscados.

Camada: importa apenas o Core (models/analyzer/filesystem) — nunca
plugins/services/UI (ADR-002).
"""

from app.core.entropy.analyzer import (
    DEFAULT_CHUNK_SIZE,
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MIN_BLOCK_SIZE,
    analyze_entropy,
    analyze_file_entropy,
    calculate_entropy,
)
from app.core.entropy.models import (
    EntropyLevel,
    EntropyMetric,
    EntropyResult,
    EntropyUnit,
)

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_HIGH_THRESHOLD",
    "DEFAULT_LOW_THRESHOLD",
    "DEFAULT_MIN_BLOCK_SIZE",
    "EntropyLevel",
    "EntropyMetric",
    "EntropyResult",
    "EntropyUnit",
    "analyze_entropy",
    "analyze_file_entropy",
    "calculate_entropy",
]
