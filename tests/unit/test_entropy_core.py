"""Testes unitários do Entropy Analyzer do EDY Shield (v2.1 — M2.2).

Cobre: cálculo de entropia de Shannon, análise de texto (total/bloco/linha),
classificação por limiar configurável, tratamento de arquivos (incluindo
arquivos grandes), determinismo e arquivo vazio/Unicode.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.core.entropy import (
    DEFAULT_HIGH_THRESHOLD,
    DEFAULT_LOW_THRESHOLD,
    EntropyLevel,
    EntropyUnit,
    analyze_entropy,
    analyze_file_entropy,
    calculate_entropy,
)


class TestCalculateEntropy:
    """Cálculo puro da entropia de Shannon."""

    def test_empty_string_returns_zero(self) -> None:
        assert calculate_entropy("") == 0.0

    def test_repetitive_string_low(self) -> None:
        # Uma letra repetida -> entropia 0.
        assert calculate_entropy("aaa") == pytest.approx(0.0, abs=1e-6)

    def test_two_symbols_equiprobable(self) -> None:
        # Dois símbolos com mesma frequência -> log2(2) = 1.0.
        assert calculate_entropy("ab") == pytest.approx(1.0, abs=1e-6)

    def test_uniform_longer_alphabet(self) -> None:
        # 8 símbolos equiprováveis -> log2(8) = 3.0.
        assert calculate_entropy("abcdefgh") == pytest.approx(3.0, abs=1e-6)

    def test_uneven_probs_between_zero_and_max(self) -> None:
        ent = calculate_entropy("aaab")
        assert 0.0 < ent < 1.0  # entre repetitivo (0) e uniforme (1)

    def test_deterministic(self) -> None:
        sample = "abracadabra123" * 10
        assert calculate_entropy(sample) == calculate_entropy(sample)


class TestAnalyzeEntropy:
    def test_empty_text_total_zero(self) -> None:
        result = analyze_entropy("")
        assert result.total_entropy == 0.0
        assert result.total_size == 0
        assert result.level is EntropyLevel.LOW

    def test_total_metric_first(self) -> None:
        result = analyze_entropy("hello world example text")
        assert result.metrics[0].unit is EntropyUnit.TOTAL
        assert result.metrics[0].label == "total"

    def test_score_bounded_zero_to_hundred(self) -> None:
        for text in ("aaa", "abc", "random\x01\x02\x03\xff" * 5):
            result = analyze_entropy(text)
            assert 0 <= result.score <= 100

    def test_common_text_is_low(self) -> None:
        # Texto natural em linguagem tem entropia tipicamente < 4.5 bits.
        text = "the quick brown fox jumps over the lazy dog. " * 20
        result = analyze_entropy(text)
        assert result.total_entropy < DEFAULT_LOW_THRESHOLD
        assert result.level is EntropyLevel.LOW
        assert result.score < 60

    def test_random_content_is_high(self) -> None:
        # Conteúdo com alta variedade de símbolos -> entropia > 6 bits.
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{};:<>?,./~`|"
        text = (alphabet * 60)[: 4096 * 4]
        result = analyze_entropy(text)
        assert result.total_entropy >= DEFAULT_HIGH_THRESHOLD
        assert result.level is EntropyLevel.HIGH
        assert result.score >= 75

    def test_base64_encoded_medium_high(self) -> None:
        import base64 as b64
        import random

        blob = bytes(random.getrandbits(8) for _ in range(6000))
        encoded = b64.b64encode(blob).decode("ascii")
        result = analyze_entropy(encoded)
        assert result.level in (EntropyLevel.MEDIUM, EntropyLevel.HIGH)

    def test_hexadecimal_detected_in_blocks(self) -> None:
        hex_text = ("0123456789abcdef" * 32)[: 6 * 64]
        result = analyze_entropy(hex_text)
        # Pelo menos existe a métrica total e blocos.
        assert len(result.metrics) >= 2

    def test_line_metric_only_high_medium(self) -> None:
        # Linha natural (baixa) e linha de alta variedade (média/alta).
        text = (
            "linha tranquila e normal aqui que repete\n"
            + "ABCabcXYZxyz1234567890!@#$%^&*()_+-=[]{};:<>?,./`~" * 4
            + "\n"
        )
        result = analyze_entropy(text)
        line_metrics = [m for m in result.metrics if m.unit is EntropyUnit.LINE]
        assert line_metrics
        assert all(m.level in (EntropyLevel.MEDIUM, EntropyLevel.HIGH) for m in line_metrics)

    def test_threshold_low_to_high_changes_classification(self) -> None:
        # Entropia de texto em ~4.4 deve ser LOW com limiar alto e
        # pode virar MEDIUM/HIGH com limiares bem baixos.
        text = "abcd wxyz 1234 5678 " * 20
        ent = calculate_entropy(text)
        high_gate = analyze_entropy(text, threshold_low=0.0, threshold_high=0.1)
        low_gate = analyze_entropy(text, threshold_low=99.0, threshold_high=99.9)
        assert high_gate.level is EntropyLevel.HIGH
        assert low_gate.level is EntropyLevel.LOW
        # garante um valor entre os dois extremos usados de forma real.
        assert 0.1 < ent < 99.0

    def test_min_block_size_filter(self) -> None:
        text = "shorts" * 4  # 24 chars
        big = analyze_entropy(text, min_block_size=64)
        small = analyze_entropy(text, min_block_size=4)
        assert len(big.metrics) <= 1  # bloco grande demais -> sem bloco
        assert len(small.metrics) > 1  # blocos pequenos geram blocos


class TestAnalyzeFileEntropy:
    def test_empty_file(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.txt"
        p.write_text("", encoding="utf-8")
        result = analyze_file_entropy(p)
        assert result.total_entropy == 0.0
        assert result.total_size == 0
        assert result.level is EntropyLevel.LOW

    def test_text_file(self, tmp_path: Path) -> None:
        p = tmp_path / "doc.txt"
        content = "texto plano comum. " * 40
        p.write_text(content, encoding="utf-8")
        result = analyze_file_entropy(p)
        assert result.target == p.name
        assert result.total_size == len(content)

    def test_unicode_file(self, tmp_path: Path) -> None:
        p = tmp_path / "unicode.txt"
        content = "你好，世界！olá mundo 🚀 " * 30  # noqa: RUF001 - conteúdo unicode intencional
        p.write_text(content, encoding="utf-8")
        result = analyze_file_entropy(p)
        assert result.total_size == len(content)
        assert result.metrics[0].unit is EntropyUnit.TOTAL

    def test_binary_random_file(self, tmp_path: Path) -> None:
        import random

        p = tmp_path / "random.bin"
        p.write_bytes(bytes(random.getrandbits(8) for _ in range(100000)))
        result = analyze_file_entropy(p, encoding="latin1")
        assert result.score >= 75  # distribuição uniforme -> alta entropia

    def test_large_file_streamed(self, tmp_path: Path) -> None:
        # ~4 MiB com variação de caracteres — valida streaming sem OOM e
        # sem manter o conteúdo inteiro em uma única fatia de análise.
        import random

        p = tmp_path / "large.bin"
        block = bytes(random.getrandbits(8) for _ in range(65536))
        with p.open("wb") as fh:
            for _ in range(64):  # ~4 MiB total
                fh.write(block)
        result = analyze_file_entropy(p, encoding="latin1", min_block_size=8192)
        assert result.total_size >= 4 * 1024 * 1024 - 128
        assert result.total_entropy > 7.0  # dados aleatórios → alta entropia
        assert result.metrics[0].unit is EntropyUnit.TOTAL

    def test_deterministic(self, tmp_path: Path) -> None:
        p = tmp_path / "det.txt"
        p.write_text("deterministico " * 100, encoding="utf-8")
        a = analyze_file_entropy(p)
        b = analyze_file_entropy(p)
        assert a.total_entropy == b.total_entropy
        assert a.score == b.score
        assert [m.label for m in a.metrics] == [m.label for m in b.metrics]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises((FileNotFoundError, OSError)):
            analyze_file_entropy(tmp_path / "nope.txt")

    def test_directory_raises(self, tmp_path: Path) -> None:
        with pytest.raises((IsADirectoryError, OSError)):
            analyze_file_entropy(tmp_path)


def test_calculate_entropy_matches_math_formula() -> None:
    """Valida a fórmula Shannon contra a constante matemática esperada."""
    text = "abcd"
    per = 1 / 4
    expected = -(per * math.log2(per)) * 4
    assert calculate_entropy(text) == pytest.approx(expected, abs=1e-6)
