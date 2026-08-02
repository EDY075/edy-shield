"""Abertura segura de arquivos regulares no EDY Shield (Sprint 4, v1.2).

Helper reutilizável que combina validação de caminho com TOCTOU hardening
em uma única operação atômica:

    1. ``resolve_safe_path`` — valida contenção na raiz e existência.
    2. ``ensure_regular_file`` — rejeita diretórios e arquivos especiais.
    3. ``os.open`` com ``O_NOFOLLOW`` (onde disponível) + ``os.fstat`` — fecha
       a janela de race entre validação e leitura.

Usado por ``hash_checker._compute_file_impl`` (leitura binária) e pelo
Log Analyzer (leitura texto). Centraliza o TOCTOU hardening (ARES-QA-008)
para todo o projeto — novos módulos nunca devem usar ``path.open()``
diretamente; usem ``open_regular_file``.

Padrão de segurança (ARCHITECTURE.md §6): o file descriptor é fechado
em caso de qualquer erro no bloco ``try`` (inclusive ``BaseException``),
evitando vazamentos de fd.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import IO, Literal, overload

from app.core.exceptions import HashError
from app.core.filesystem.safe_path import ensure_regular_file, resolve_safe_path

_O_BINARY = getattr(os, "O_BINARY", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


@overload
def open_regular_file(
    path: Path | str,
    *,
    allowed_root: Path | None = None,
    binary: Literal[False],
    encoding: str | None = None,
    errors: str | None = None,
) -> IO[str]: ...


@overload
def open_regular_file(
    path: Path | str,
    *,
    allowed_root: Path | None = None,
    binary: Literal[True] = True,
    encoding: str | None = None,
    errors: str | None = None,
) -> IO[bytes]: ...


def open_regular_file(
    path: Path | str,
    *,
    allowed_root: Path | None = None,
    binary: bool = True,
    encoding: str | None = None,
    errors: str | None = None,
) -> IO[bytes] | IO[str]:
    """Abrir um arquivo regular de forma segura (com TOCTOU hardening).

    Combina validação de path (:func:`resolve_safe_path`) e abertura com
    ``O_NOFOLLOW`` (mitigando TOCTOU) em um único helper reutilizável,
    removendo duplicação entre o hash_checker e o log_analyzer.

    Args:
        path: Caminho do arquivo (``Path`` ou ``str``).
        allowed_root: Raiz permitida, ou ``None`` para cwd.
        binary: Se ``True`` (padrão), retorna um arquivo binário (``rb``).
            Se ``False``, abre como texto (``r``) — use ``encoding`` e
            ``errors`` para controle de decodificação.
        encoding: Encoding do modo texto (ignorado em ``binary=True``);
            ``None`` usa o encoding padrão da plataforma.
        errors: Política de erros de decodificação do modo texto (ex.:
            ``"replace"``); ``None`` usa o padrão da plataforma.

    Returns:
        Um objeto file-like (`TextIO` ou `BinaryIO`).

    Raises:
        HashError: Se o path escapa a raiz ou é um não-regular.
        IsADirectoryError: Se o path aponta para um diretório.
        FileNotFoundError: Se o path não existe.
        OSError: Em erros inesperados de sistema.
    """
    target = resolve_safe_path(path, allowed_root=allowed_root, strict=True)
    ensure_regular_file(target)

    flags = os.O_RDONLY | _O_BINARY | _O_NOFOLLOW
    fd = os.open(target, flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise HashError(f"Cannot hash non-regular file: {target.name}")

        if binary:
            return os.fdopen(fd, "rb")
        return os.fdopen(fd, "r", encoding=encoding, errors=errors)
    except BaseException:
        os.close(fd)
        raise
