"""Analyzer de strings do EDY Shield (v2.1 — M2.1).

Aplica os padrões (:mod:`app.core.string.patterns`) sobre texto, linha a
linha, e retorna achados estruturados (:class:`StringMatch`).

Uso:

    from app.core.string import analyze_text

    matches = analyze_text(open("artefato.txt").read())
    for m in matches:
        print(m.line, m.type.value, m.category.value, m.severity.value, m.value)

Regras:

* **Core puro** — 100% stdlib, sem dependência de plugins (ADR-001/002).
* **Linha a linha** — preenche ``line`` (1-based) e posições ``start``/``end``
  relativas à linha.
* **Determinístico** — matches deduplicados por ``(category, line, start, end)``
  e ordenados por ``(line, start, end, category)``.
* **Confiança** — cada categoria tem confiança própria (``patterns.spec_for``).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.core.string.models import (
    StringCategory,
    StringMatch,
    StringSeverity,
    StringType,
)
from app.core.string.patterns import spec_for
from app.core.string.tokenizer import find_long_tokens, tokenize_lines

#: Confiança padrão de tokens longos (heurística de ofuscação).
_LONG_TOKEN_CONFIDENCE = 0.5


def analyze_text(
    text: str,
    categories: Sequence[StringCategory] | None = None,
    min_token_length: int = 256,
) -> list[StringMatch]:
    """Analisar texto e retornar achados ordenados (determinístico).

    Args:
        text: Texto a analisar.
        categories: Categorias a considerar; ``None`` usa todas (incluindo
            :attr:`StringCategory.LONG_TOKEN`).
        min_token_length: Comprimento mínimo para classificar um token como
            ``LONG_TOKEN`` (possível ofuscação).

    Returns:
        Lista de :class:`StringMatch` deduplicada e ordenada por
        ``(line, start, end, category)``.
    """
    selected = _select_categories(categories)

    matches: list[StringMatch] = []
    for line_no, line in enumerate(tokenize_lines(text), start=1):
        for category in selected:
            if category is StringCategory.LONG_TOKEN:
                continue
            spec = spec_for(category)
            for match in spec.regex.finditer(line):
                matches.append(
                    StringMatch(
                        category=category,
                        value=match.group(),
                        start=match.start(),
                        end=match.end(),
                        severity=spec.severity,
                        confidence=spec.confidence,
                        type=spec.type,
                        line=line_no,
                    )
                )

        if StringCategory.LONG_TOKEN in selected and min_token_length > 0:
            for token, start, end in find_long_tokens(line, min_token_length):
                matches.append(
                    StringMatch(
                        category=StringCategory.LONG_TOKEN,
                        value=token,
                        start=start,
                        end=end,
                        severity=StringSeverity.LOW,
                        confidence=_LONG_TOKEN_CONFIDENCE,
                        type=StringType.LONG,
                        line=line_no,
                    )
                )

    return _dedup_and_sort(matches)


def _select_categories(
    categories: Sequence[StringCategory] | None,
) -> tuple[StringCategory, ...]:
    """Resolver a lista de categorias a avaliar (None = todas)."""
    if categories is None:
        return tuple(StringCategory)
    return tuple(categories)


def _dedup_and_sort(matches: Iterable[StringMatch]) -> list[StringMatch]:
    """Deduplicar por (category, line, start, end) e ordenar deterministicamente."""
    seen: set[tuple[object, ...]] = set()
    unique: list[StringMatch] = []
    for match in matches:
        key = (match.category, match.line, match.start, match.end)
        if key in seen:
            continue
        seen.add(key)
        unique.append(match)
    unique.sort(key=lambda m: (m.line or 0, m.start, m.end, m.category.value))
    return unique
