"""Entropy Analyzer puro do EDY Shield (v2.1 — M2.2).

Calcula a **entropia de Shannon** (bits por unidade) de textos e arquivos
para sinalizar conteúdos com alta aleatoriedade — indícios de dados
codificados, compactados, criptografados ou ofuscados.

API pública (re-exportada via :mod:`app.core.entropy`):

* :func:`calculate_entropy` — entropia de um texto (bits por caractere).
* :func:`analyze_entropy` — análise completa: texto inteiro, por linha e
  por bloco, com classificação e justificativa.
* :func:`analyze_file_entropy` — análise de um arquivo com tratamento
  seguro para arquivos grandes (leitura em bloco, sem carregar tudo em
  memória).

Regras:

* **Core puro** — 100% stdlib, sem dependência de plugins (ADR-001/002).
* **Determinístico** — mesma entrada produz exatamente a mesma saída.
* **Limiares configuráveis** — ``threshold_low``/``threshold_high`` e
  ``min_block_size`` controlam a classificação por chamada.
* **Tratamento seguro de arquivos grandes** — o arquivo é lido em blocos;
  nenhuma leitura inteira é mantida em memória (mitiga DoS por OOM).
"""

from __future__ import annotations

import math
from collections import Counter
from pathlib import Path

from app.core.entropy.models import (
    EntropyLevel,
    EntropyMetric,
    EntropyResult,
    EntropyUnit,
)
from app.core.filesystem.safe_path import ensure_regular_file, resolve_safe_path

#: Abaixo deste valor considera-se entropia **baixa** (texto plano/repetitivo).
DEFAULT_LOW_THRESHOLD = 4.5
#: Acima deste valor considera-se entropia **alta** (aleatório/codificado).
DEFAULT_HIGH_THRESHOLD = 6.0
#: Tamanho mínimo padrão de um bloco para a análise por bloco.
DEFAULT_MIN_BLOCK_SIZE = 64
#: Tamanho padrão de leitura por bloco de arquivo (caracteres).
DEFAULT_CHUNK_SIZE = 65536
#: Entropia máxima de referência (8 bits por byte/unidade) para a pontuação.
_MAX_REFERENCE_ENTROPY = 8.0


def calculate_entropy(content: str) -> float:
    """Calcular a entropia de Shannon do conteúdo (bits por caractere).

    Formula: ``-sum(p * log2(p))`` sobre a frequência dos caracteres.
    Conteúdo com caracteres igualmente distribuídos se aproxima de
    ``log2(alphabet)``; conteúdo repetitivo se aproxima de 0.

    Args:
        content: Texto a medir.

    Returns:
        Entropia em bits por caractere; ``0.0`` para conteúdo vazio.
    """
    if not content:
        return 0.0
    total = len(content)
    entropy = 0.0
    for count in Counter(content).values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy


def _classify(entropy: float, low: float, high: float) -> EntropyLevel:
    """Classificar um valor de entropia conforme os limiares."""
    if entropy >= high:
        return EntropyLevel.HIGH
    if entropy >= low:
        return EntropyLevel.MEDIUM
    return EntropyLevel.LOW


def _justify(level: EntropyLevel, entropy: float) -> str:
    """Gerar a justificativa textual de uma classificação."""
    if level is EntropyLevel.HIGH:
        return (
            f"Alta entropia ({entropy:.2f} bits/unidade): conteúdo "
            "aleatório ou codificado — provável dado compactado, "
            "criptografado ou ofuscado."
        )
    if level is EntropyLevel.MEDIUM:
        return (
            f"Entropia média ({entropy:.2f} bits/unidade): pode conter "
            "trechos codificados, mas não predomina uniformidade aleatória."
        )
    return (
        f"Baixa entropia ({entropy:.2f} bits/unidade): texto natural ou "
        "conteúdo repetitivo, padrão previsível."
    )


def _to_score(entropy: float) -> int:
    """Normalizar a entropia para uma pontuação 0-100.

    Escala saturada a partir de :data:`_MAX_REFERENCE_ENTROPY` (8 bits),
    mantendo a pontuação finita e interpretável.
    """
    normalized = min(entropy / _MAX_REFERENCE_ENTROPY, 1.0)
    return round(normalized * 100)


def analyze_entropy(
    text: str,
    *,
    threshold_low: float = DEFAULT_LOW_THRESHOLD,
    threshold_high: float = DEFAULT_HIGH_THRESHOLD,
    min_block_size: int = DEFAULT_MIN_BLOCK_SIZE,
) -> EntropyResult:
    """Analisar texto: inteiro, por bloco e por linha.

    Args:
        text: Texto a analisar.
        threshold_low: Limiar da classificação ``MEDIUM`` (inclusivo).
        threshold_high: Limiar da classificação ``HIGH`` (inclusivo).
        min_block_size: Tamanho mínimo de cada bloco para análise por bloco.

    Returns:
        :class:`EntropyResult` determinístico, com a métrica ``total``
        primeiro, seguidas das métricas por bloco e por linha (somente
        linhas de entropia média/alta, para reduzir ruído).
    """
    metrics: list[EntropyMetric] = []

    total_entropy = calculate_entropy(text)
    total_level = _classify(total_entropy, threshold_low, threshold_high)
    metrics.append(
        EntropyMetric(
            label="total",
            unit=EntropyUnit.TOTAL,
            size=len(text),
            entropy=total_entropy,
            level=total_level,
            justification=_justify(total_level, total_entropy),
        )
    )

    _add_block_metrics(metrics, text, min_block_size, threshold_low, threshold_high)
    _add_line_metrics(metrics, text, threshold_low, threshold_high)

    return EntropyResult(
        target="<texto>",
        total_entropy=total_entropy,
        total_size=len(text),
        level=total_level,
        score=_to_score(total_entropy),
        metrics=tuple(metrics),
        justification=_justify(total_level, total_entropy),
    )


def _add_block_metrics(
    metrics: list[EntropyMetric],
    text: str,
    min_block_size: int,
    low: float,
    high: float,
) -> None:
    """Analisar o texto em blocos fixos (janelas de tamanho constante)."""
    if min_block_size <= 0 or len(text) < min_block_size:
        return
    for idx in range(0, len(text), min_block_size):
        block = text[idx : idx + min_block_size]
        if len(block) < min_block_size:
            continue
        ent = calculate_entropy(block)
        level = _classify(ent, low, high)
        metrics.append(
            EntropyMetric(
                label=f"bloco {idx // min_block_size + 1}",
                unit=EntropyUnit.BLOCK,
                size=len(block),
                entropy=ent,
                level=level,
                justification=_justify(level, ent),
            )
        )


def _add_line_metrics(
    metrics: list[EntropyMetric],
    text: str,
    low: float,
    high: float,
) -> None:
    """Analisar cada linha, emitindo métrica só para média/alta."""
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line:
            continue
        ent = calculate_entropy(line)
        level = _classify(ent, low, high)
        if level is EntropyLevel.LOW:
            continue
        metrics.append(
            EntropyMetric(
                label=f"linha {line_no}",
                unit=EntropyUnit.LINE,
                size=len(line),
                entropy=ent,
                level=level,
                justification=_justify(level, ent),
            )
        )


def analyze_file_entropy(
    path: str | Path,
    *,
    encoding: str = "utf-8",
    threshold_low: float = DEFAULT_LOW_THRESHOLD,
    threshold_high: float = DEFAULT_HIGH_THRESHOLD,
    min_block_size: int = DEFAULT_MIN_BLOCK_SIZE,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> EntropyResult:
    """Analisar a entropia de um arquivo de forma segura para arquivos grandes.

    O arquivo é lido **em blocos** (``chunk_size`` caracteres), acumulando
    as frequências sem manter o conteúdo inteiro na memória. A entropia
    total é calculada sobre as frequências acumuladas; bloco por bloco é
    medido por streaming sobre o buffer em memória.

    A travessia respeita a fronteira de arquivos do Core
    (:func:`resolve_safe_path`) — mitigando fuga da raiz permitida
    (ARES-QA-001, ARES-QA-028).

    Args:
        path: Caminho do arquivo.
        encoding: Codificação do arquivo (padrão UTF-8).
        threshold_low: Limiar da classificação ``MEDIUM``.
        threshold_high: Limiar da classificação ``HIGH``.
        min_block_size: Tamanho mínimo de cada bloco de streaming.
        chunk_size: Tamanho do bloco de leitura (caracteres).

    Returns:
        :class:`EntropyResult` com o ``total`` e métricas por bloco.

    Raises:
        FileNotFoundError: Se o arquivo não existir.
        IsADirectoryError: Se o caminho for um diretório.
        app.core.exceptions.HashError: Se o arquivo escapar da raiz
            permitida ou não for regular.
    """
    # A raiz permitida é o diretório do próprio arquivo (padrão
    # ARES-QA-028), garantindo que o caminho resolvido esteja sempre
    # dentro da fronteira sem exigir que o arquivo viva sob o cwd.
    resolved = resolve_safe_path(path, allowed_root=Path(path).resolve().parent, strict=True)
    ensure_regular_file(resolved)

    total_entropy, total_size = _stream_entropy(resolved, encoding=encoding, chunk_size=chunk_size)
    level = _classify(total_entropy, threshold_low, threshold_high)

    metrics: list[EntropyMetric] = [
        EntropyMetric(
            label="total",
            unit=EntropyUnit.TOTAL,
            size=total_size,
            entropy=total_entropy,
            level=level,
            justification=_justify(level, total_entropy),
        )
    ]
    metrics.extend(
        _stream_block_metrics(
            resolved,
            encoding=encoding,
            chunk_size=chunk_size,
            min_block_size=min_block_size,
            threshold_low=threshold_low,
            threshold_high=threshold_high,
        )
    )

    return EntropyResult(
        target=resolved.name,
        total_entropy=total_entropy,
        total_size=total_size,
        level=level,
        score=_to_score(total_entropy),
        metrics=tuple(metrics),
        justification=_justify(level, total_entropy),
    )


def _stream_entropy(path: Path, *, encoding: str, chunk_size: int) -> tuple[float, int]:
    """Calcular a entropia total lendo o arquivo em blocos (memória constante)."""
    counter: Counter[str] = Counter()
    total = 0
    # newline="" desabilita a tradução universal de newlines do modo texto
    # (Windows traduz \r\n/\\r por padrão → corrompe a contagem de bytes em
    # dados binários/latin1). Consistente em todos os SO.
    with path.open("r", encoding=encoding, errors="replace", newline="") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            counter.update(chunk)
            total += len(chunk)
    if total == 0:
        return 0.0, 0
    entropy = 0.0
    for count in counter.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy, total


def _stream_block_metrics(
    path: Path,
    *,
    encoding: str,
    chunk_size: int,
    min_block_size: int,
    threshold_low: float,
    threshold_high: float,
) -> list[EntropyMetric]:
    """Medir entropia por bloco via streaming sobre o buffer em memória."""
    metrics: list[EntropyMetric] = []
    if min_block_size <= 0:
        return metrics
    block_idx = 1
    buffer = ""
    with path.open("r", encoding=encoding, errors="replace", newline="") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            buffer += chunk
            while len(buffer) >= min_block_size:
                block = buffer[:min_block_size]
                buffer = buffer[min_block_size:]
                ent = calculate_entropy(block)
                level = _classify(ent, threshold_low, threshold_high)
                metrics.append(
                    EntropyMetric(
                        label=f"bloco {block_idx}",
                        unit=EntropyUnit.BLOCK,
                        size=len(block),
                        entropy=ent,
                        level=level,
                        justification=_justify(level, ent),
                    )
                )
                block_idx += 1
    if len(buffer) >= min_block_size:
        ent = calculate_entropy(buffer)
        level = _classify(ent, threshold_low, threshold_high)
        metrics.append(
            EntropyMetric(
                label=f"bloco {block_idx}",
                unit=EntropyUnit.BLOCK,
                size=len(buffer),
                entropy=ent,
                level=level,
                justification=_justify(level, ent),
            )
        )
    return metrics
