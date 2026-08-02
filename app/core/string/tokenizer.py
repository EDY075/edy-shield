"""Tokenização de texto do String Analyzer (v2.1 — M2.1).

Helpers puros de tokenização, 100% stdlib, usados pelo analyzer para:

* processar o texto **linha a linha** (preservando o número da linha);
* identificar **tokens longos** (possível ofuscação/obfuscação).
"""

from __future__ import annotations

from collections.abc import Iterator


def tokenize_lines(text: str) -> Iterator[str]:
    """Iterar sobre as linhas do texto (preservando separadores de fim de linha).

    Usa ``splitlines()`` — trata ``\\n``, ``\\r\\n``, ``\\r`` e outras quebras
    Unicode sem retornar os separadores.

    Args:
        text: Texto a tokenizar.

    Yields:
        Cada linha do texto.
    """
    yield from text.splitlines()


def tokenize_words(text: str) -> Iterator[str]:
    """Iterar sobre os tokens (separados por whitespace) do texto.

    Args:
        text: Texto a tokenizar.

    Yields:
        Cada token não-vazio.
    """
    for token in text.split():
        if token:
            yield token


def find_long_tokens(
    text: str, min_length: int, *, _line: int | None = None
) -> Iterator[tuple[str, int, int]]:
    """Yield ``(token, start, end)`` para tokens com ``len >= min_length``.

    Útil para detectar strings muito longas (possível dado codificado).

    Args:
        text: Texto a analisar.
        min_length: Comprimento mínimo do token para ser reportado.
        line: Número da linha (1-based) para preencher nos matches.

    Yields:
        Tuplas ``(token, start, end)`` com posições no ``text``.
    """
    if min_length <= 0:
        return
    start = 0
    for token in tokenize_words(text):
        length = len(token)
        if length >= min_length:
            yield token, start, start + length
        start += length + 1  # +1 pelo whitespace que separa os tokens
