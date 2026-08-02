"""Modelos do Entropy Analyzer do EDY Shield (v2.1 — M2.2).

Tipos puros do Core, sem dependência de plugins (ADR-002):

* :class:`EntropyLevel` — classificação baixa, média e alta.
* :class:`EntropyUnit` — escopo de uma medição (texto completo, linha,
  bloco).
* :class:`EntropyMetric` — uma medição individual com justificativa.
* :class:`EntropyResult` — resultado agregado de uma análise.

O Core calcula a **entropia de Shannon** sobre bytes/unidades do conteúdo.
Quanto maior a entropia, maior a aleatoriedade — indicativo de dados
codificados, compactados, criptografados ou ofuscados (ADR-M2.2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EntropyLevel(Enum):
    """Classificação da aleatoriedade de uma medição.

    Ordenado do menor para o maior risco:
    ``LOW < MEDIUM < HIGH``.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EntropyUnit(Enum):
    """Escopo de uma medição de entropia."""

    TOTAL = "total"
    LINE = "line"
    BLOCK = "block"


@dataclass(frozen=True, slots=True)
class EntropyMetric:
    """Uma medição individual de entropia com justificativa.

    Attributes:
        label: Identificador legível da medição (ex.: ``"total"``,
            ``"linha 3"``, ``"bloco 5"``). Variável e independente do
            :attr:`unit`.
        unit: Escopo da medição (:attr:`EntropyUnit`).
        size: Número de unidades (caracteres ou bytes) analisadas.
        entropy: Valor da entropia de Shannon (bits por unidade).
        level: Classificação derivada dos limiares.
        justification: Por que a medição caiu naquela classificação.
    """

    label: str
    unit: EntropyUnit
    size: int
    entropy: float
    level: EntropyLevel
    justification: str


@dataclass(frozen=True, slots=True)
class EntropyResult:
    """Resultado agregado de uma análise de entropia.

    Attributes:
        target: Nome legível do alvo (``"<texto>"`` ou o nome do arquivo).
        total_entropy: Entropia do conteúdo como um todo (bits/unidade).
        total_size: Número total de unidades analisadas.
        level: Classificação global.
        score: Pontuação normalizada (0-100), derivada de
            :attr:`total_entropy`.
        metrics: Medições detalhadas (linhas/blocos/total), ordenadas.
        justification: Justificativa da classificação global.
    """

    target: str
    total_entropy: float
    total_size: int
    level: EntropyLevel
    score: int
    metrics: tuple[EntropyMetric, ...]
    justification: str
