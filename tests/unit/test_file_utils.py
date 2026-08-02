"""Unit tests for EDY Shield path-security utilities (app.services.file_utils).

Cobre a fronteira de validação de caminhos: contenção na raiz permitida,
existência (strict), rejeição de diretórios/arquivos especiais e o helper
``is_within_root`` (ARES-QA-001, ARES-QA-005, ARES-QA-007).
"""

from pathlib import Path

import pytest

from app.core.models.common import HashError
from app.services.file_utils import (
    ensure_regular_file,
    is_within_root,
    resolve_safe_path,
    validate_allowed_root,
)


def test_resolve_safe_path_accepts_path_inside_root(tmp_path: Path) -> None:
    """A plain file inside the allowed root resolves and is accepted."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    resolved = resolve_safe_path(sample, allowed_root=tmp_path)
    assert resolved == sample.resolve()
    assert resolved.is_absolute()


def test_resolve_safe_path_accepts_str_path(tmp_path: Path) -> None:
    """resolve_safe_path accepts str paths as well as Path."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    resolved = resolve_safe_path(str(sample), allowed_root=tmp_path)
    assert resolved == sample.resolve()


def test_resolve_safe_path_rejects_dotdot_escaping_root(tmp_path: Path) -> None:
    """A path with ``..`` escaping the allowed root raises HashError."""
    with pytest.raises(HashError):
        resolve_safe_path(tmp_path / ".." / "secret.txt", allowed_root=tmp_path)


def test_resolve_safe_path_rejects_absolute_outside_root(tmp_path: Path) -> None:
    """An absolute path outside the allowed root raises HashError."""
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("data", encoding="utf-8")
    with pytest.raises(HashError):
        resolve_safe_path(outside, allowed_root=tmp_path)


def test_resolve_safe_path_default_root_is_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no allowed_root, the current working directory is the root."""
    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    resolved = resolve_safe_path("sample.txt")
    assert resolved == sample.resolve()


def test_resolve_safe_path_missing_file_raises(tmp_path: Path) -> None:
    """A missing file raises FileNotFoundError when strict=True (default)."""
    with pytest.raises(FileNotFoundError):
        resolve_safe_path(tmp_path / "missing.txt", allowed_root=tmp_path)


def test_resolve_safe_path_strict_false_allows_missing(tmp_path: Path) -> None:
    """strict=False returns the resolved path even for a missing file."""
    missing = tmp_path / "missing.txt"
    resolved = resolve_safe_path(missing, allowed_root=tmp_path, strict=False)
    assert resolved == missing.resolve()


def test_resolve_safe_path_rejects_symlink_escaping_root(tmp_path: Path) -> None:
    """A symlink inside the root pointing outside raises HashError."""
    outside = tmp_path.parent / "outside_target.txt"
    outside.write_text("data", encoding="utf-8")
    link = tmp_path / "evil_link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted on this platform/filesystem")
    with pytest.raises(HashError):
        resolve_safe_path(link, allowed_root=tmp_path)


def test_ensure_regular_file_accepts_regular_file(tmp_path: Path) -> None:
    """A regular file passes ensure_regular_file without error."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    ensure_regular_file(sample.resolve())


def test_ensure_regular_file_rejects_directory(tmp_path: Path) -> None:
    """ensure_regular_file raises IsADirectoryError for directories."""
    with pytest.raises(IsADirectoryError):
        ensure_regular_file(tmp_path.resolve())


def test_ensure_regular_file_rejects_non_regular_file(tmp_path: Path) -> None:
    """ensure_regular_file raises HashError for non-regular targets (ARES-QA-007)."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(HashError):
        ensure_regular_file(missing.resolve())


def test_validate_allowed_root_defaults_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """validate_allowed_root returns the cwd when root is None."""
    monkeypatch.chdir(tmp_path)
    assert validate_allowed_root(None) == Path.cwd().resolve()


def test_validate_allowed_root_resolves(tmp_path: Path) -> None:
    """validate_allowed_root resolves relative roots to absolute paths."""
    sub = tmp_path / "sub"
    sub.mkdir()
    assert validate_allowed_root(sub) == sub.resolve()


def test_validate_allowed_root_rejects_non_path() -> None:
    """validate_allowed_root raises TypeError for non-Path roots."""
    with pytest.raises(TypeError):
        validate_allowed_root(12345)  # type: ignore[arg-type]


def test_is_within_root_true_and_false(tmp_path: Path) -> None:
    """is_within_root distinguishes inside from outside paths."""
    inside = tmp_path / "sample.txt"
    outside = tmp_path.parent / "outside.txt"
    assert is_within_root(inside.resolve(), tmp_path.resolve()) is True
    assert is_within_root(outside.resolve(), tmp_path.resolve()) is False
