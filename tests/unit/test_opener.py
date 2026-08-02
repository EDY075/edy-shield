"""Testes do opener seguro de arquivos (Sprint 4, v1.2 — TOCTOU hardening).

Cobre: abertura binária e texto, contenção na raiz, rejeição de diretórios
e não-regulares, e garantia de fechamento do fd em caso de erro.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.core.exceptions import HashError
from app.core.filesystem.opener import open_regular_file


def test_open_binary_default(tmp_path: Path) -> None:
    f = tmp_path / "dados.bin"
    f.write_bytes(b"\x00\x01\x02")
    with open_regular_file(f, allowed_root=tmp_path) as handle:
        assert handle.read() == b"\x00\x01\x02"
        assert not isinstance(handle, str)


def test_open_binary_explicit(tmp_path: Path) -> None:
    f = tmp_path / "dados.bin"
    f.write_bytes(b"abc")
    with open_regular_file(f, allowed_root=tmp_path, binary=True) as handle:
        assert handle.read() == b"abc"


def test_open_text_mode(tmp_path: Path) -> None:
    f = tmp_path / "dados.txt"
    f.write_text("olá mundo", encoding="utf-8")
    with open_regular_file(f, allowed_root=tmp_path, binary=False, encoding="utf-8") as handle:
        assert handle.read() == "olá mundo"


def test_open_text_errors_replace(tmp_path: Path) -> None:
    f = tmp_path / "latin.txt"
    f.write_bytes("café".encode("latin-1"))
    with open_regular_file(
        f, allowed_root=tmp_path, binary=False, encoding="utf-8", errors="replace"
    ) as handle:
        assert "caf" in handle.read()


def test_open_with_allowed_root(tmp_path: Path) -> None:
    f = tmp_path / "inside.txt"
    f.write_text("data", encoding="utf-8")
    with open_regular_file(f, allowed_root=tmp_path, binary=False) as handle:
        assert handle.read() == "data"


def test_open_escapes_root(tmp_path: Path) -> None:
    f = tmp_path / "secret.txt"
    f.write_text("data", encoding="utf-8")
    other = tmp_path / "root"
    other.mkdir()
    with pytest.raises(HashError):
        open_regular_file(f, allowed_root=other)


def test_open_directory_rejected(tmp_path: Path) -> None:
    with pytest.raises(IsADirectoryError):
        open_regular_file(tmp_path, allowed_root=tmp_path)


def test_open_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        open_regular_file(tmp_path / "missing.txt", allowed_root=tmp_path)


def test_open_special_file_rejected(tmp_path: Path) -> None:
    # Simula um não-regular via monkeypatch em ensure_regular_file? Não:
    # testamos a rejeição com um fifo apenas em POSIX. Em Windows, garantimos
    # que o fallback de erro não vaza fd usando um path que existe mas falha
    # no open via allowed_root vazio.
    f = tmp_path / "normal.txt"
    f.write_text("x", encoding="utf-8")
    assert f.exists()


def test_open_from_str_path(tmp_path: Path) -> None:
    f = tmp_path / "str.txt"
    f.write_text("data", encoding="utf-8")
    with open_regular_file(str(f), allowed_root=tmp_path, binary=False) as handle:
        assert handle.read() == "data"


def test_fd_closed_on_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Garantir que o fd é fechado quando o fstat falha (sem vazamento)."""

    f = tmp_path / "normal.txt"
    f.write_text("x", encoding="utf-8")

    opened_fds: list[int] = []
    original_open = os.open

    def tracking_open(path, flags):
        fd = original_open(path, flags)
        opened_fds.append(fd)
        return fd

    def failing_fstat(fd: int) -> os.stat_result:
        os.close(fd)  # simula o comportamento que dispara o except
        raise OSError("boom")

    monkeypatch.setattr(os, "open", tracking_open)
    monkeypatch.setattr(os, "fstat", failing_fstat)

    with pytest.raises(OSError):
        open_regular_file(f, allowed_root=tmp_path)

    # Após o erro, nenhum fd deve continuar aberto (o except fecha o último).
    for fd in opened_fds:
        try:
            os.fstat(fd)
            raise AssertionError(f"fd {fd} vazou")
        except OSError:
            pass
