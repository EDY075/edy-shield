"""Geração de IDs de baseline do File Integrity Monitor (Sprint 5).

Módulo puro isolado para evitar ciclo de imports entre ``baseline`` e
``store`` (ambos precisam do mesmo gerador). Segue o formato da spec:

    fim_<algo>_<UTC %Y%m%dT%H%M%SZ>

Exemplo: ``fim_sha256_20260802T120000Z``
"""

from __future__ import annotations

from datetime import UTC, datetime


def build_baseline_id(algorithm: str, now: datetime | None = None) -> str:
    """Gerar o baseline_id no formato canônico.

    Args:
        algorithm: Nome do algoritmo (ex.: ``SHA256``). É normalizado para
            lowercase no id (``sha256``).
        now: Momento UTC a usar (injetável para testes); quando ``None``,
            usa :func:`datetime.now(UTC)`.

    Returns:
        Id no formato ``fim_<algo>_<UTC %Y%m%dT%H%M%SZ>``.
    """
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"fim_{algorithm.strip().lower()}_{stamp}"


def build_unique_baseline_id(algorithm: str, now: datetime | None = None) -> str:
    """Gerar um baseline_id único (com fração de microsegundos).

    Extensão do formato canônico usada quando duas baselines são criadas no
    mesmo segundo (ARES-QA-033): anexa a fração UTC ao id, garantindo
    unicidade sem quebrar a leitura de baselines no formato antigo.

    Args:
        algorithm: Nome do algoritmo (ex.: ``SHA256``).
        now: Momento UTC a usar (injetável para testes).

    Returns:
        Id no formato ``fim_<algo>_<UTC %Y%m%dT%H%M%SZ><micro>``.
    """
    stamp = (now or datetime.now(UTC)).astimezone(UTC)
    base = stamp.strftime("%Y%m%dT%H%M%SZ")
    micro = f"{stamp.microsecond:06d}"
    return f"fim_{algorithm.strip().lower()}_{base}{micro}"
