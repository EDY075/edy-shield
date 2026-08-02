"""Unit tests for the EDY Shield Hash Checker core module."""

from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path

import pytest

from app.core.algorithms.hash_checker import (
    HashAlgorithm,
    compute,
    compute_bytes,
    compute_file,
    compute_text,
    supported_algorithms,
    verify_file,
)
from app.core.models.common import HashError, UnsupportedAlgorithmError
from app.core.models.hashes import HashResult

#: SHA-256 digest of the ASCII string "hello".
SHA256_HELLO = "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
#: SHA-1 digest of the ASCII string "hello".
SHA1_HELLO = "aaf4c61ddcc5e8a2dabede0f3b482cd9aea9434d"
#: MD5 digest of the ASCII string "hello".
MD5_HELLO = "5d41402abc4b2a76b9719d911017c592"


def test_sha256_of_known_text(plain_text: str) -> None:
    """SHA-256 of "hello" must match the well-known digest."""
    assert compute_text(plain_text, "sha256") == SHA256_HELLO


def test_sha1_of_known_text(plain_text: str) -> None:
    """SHA-1 of "hello" must match the well-known digest."""
    assert compute_text(plain_text, HashAlgorithm.SHA1) == SHA1_HELLO


def test_md5_of_known_text(plain_text: str) -> None:
    """MD5 of "hello" must match the well-known digest."""
    assert compute_text(plain_text, "MD5") == MD5_HELLO


def test_algorithm_string_is_case_and_separator_insensitive() -> None:
    """Algorithm strings are normalized (case, hyphens, underscores)."""
    assert compute_text("hello", "ShA-256") == SHA256_HELLO
    assert compute_text("hello", "sha_1") == SHA1_HELLO
    assert compute_text("hello", "mD5") == MD5_HELLO


def test_compute_text_respects_encoding() -> None:
    """Non-ASCII text hashed with an explicit encoding must match bytes."""
    text = "olá mundo — segurança"
    assert compute_text(text, "md5", encoding="utf-8") == compute_bytes(text.encode("utf-8"), "md5")


def test_compute_bytes_pure() -> None:
    """Raw bytes are hashed directly."""
    assert compute_bytes(b"hello", "sha256") == SHA256_HELLO


def test_compute_bytes_empty() -> None:
    """Empty bytes hash to the well-known empty digest."""
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert compute_bytes(b"", "sha256") == expected


def test_compute_file_with_tmp_fixture(tmp_path: Path) -> None:
    """File hashing matches the known digest for content "hello"."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert compute_file(sample, "sha256", allowed_root=tmp_path) == SHA256_HELLO


def test_compute_file_reads_in_small_chunks(tmp_path: Path) -> None:
    """Chunked reading must produce the same digest as a whole-file hash."""
    data = b"EDY Shield - chunked reading test. " * 500  # ~37 KB
    sample = tmp_path / "large.bin"
    sample.write_bytes(data)

    expected = sha256(data).hexdigest()
    assert compute_file(sample, "sha256", chunk_size=8, allowed_root=tmp_path) == expected
    assert compute_file(sample, "sha256", chunk_size=1, allowed_root=tmp_path) == expected


def test_compute_file_missing_raises_file_not_found(tmp_path: Path) -> None:
    """A missing file surfaces a natural FileNotFoundError."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        compute_file(missing, "sha256", allowed_root=tmp_path)


def test_compute_file_directory_raises(tmp_path: Path) -> None:
    """Hashing a directory must raise IsADirectoryError."""
    with pytest.raises(IsADirectoryError):
        compute_file(tmp_path, "sha256", allowed_root=tmp_path)


def test_compute_file_invalid_chunk_size(tmp_path: Path) -> None:
    """A non-positive chunk size must raise ValueError."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        compute_file(sample, "sha256", chunk_size=0, allowed_root=tmp_path)


def test_compute_with_bytes_source() -> None:
    """Dispatcher returns source="bytes" for raw bytes."""
    result = compute(b"hello", "sha256")
    assert isinstance(result, HashResult)
    assert result.hexdigest == SHA256_HELLO
    assert result.source == "bytes"
    assert result.size_bytes == 5
    assert result.path is None


def test_compute_with_text_source() -> None:
    """Dispatcher returns source="text" for a non-path-looking string."""
    result = compute("hello", "sha256")
    assert result.hexdigest == SHA256_HELLO
    assert result.source == "text"
    assert result.path is None
    assert result.size_bytes == 5


def test_compute_with_path_source(tmp_path: Path) -> None:
    """Dispatcher returns source="file" for a Path."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    result = compute(sample, "sha256", allowed_root=tmp_path)
    assert result.hexdigest == SHA256_HELLO
    assert result.source == "file"
    assert result.path is not None
    assert result.path.is_absolute()
    assert result.size_bytes == 5


def test_compute_with_str_path_source(tmp_path: Path) -> None:
    """Dispatcher detects an existing file given as a string path."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    result = compute(str(sample), "sha256", allowed_root=tmp_path)
    assert result.source == "file"
    assert result.hexdigest == SHA256_HELLO
    assert result.path == sample.resolve()


def test_hash_result_is_frozen() -> None:
    """HashResult is immutable (frozen dataclass)."""
    result = compute(b"hello", "sha256")
    with pytest.raises(FrozenInstanceError):
        result.hexdigest = "tampered"  # type: ignore[misc]


def test_verify_file_true(tmp_path: Path) -> None:
    """verify_file returns True for a matching digest."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert verify_file(sample, SHA256_HELLO, "sha256", allowed_root=tmp_path) is True


def test_verify_file_case_insensitive(tmp_path: Path) -> None:
    """Comparison is case-insensitive and ignores surrounding whitespace."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert (
        verify_file(
            sample,
            f"  {SHA256_HELLO.upper()}  ",
            "sha256",
            allowed_root=tmp_path,
        )
        is True
    )


def test_verify_file_false(tmp_path: Path) -> None:
    """verify_file returns False for a mismatching digest."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert verify_file(sample, "0" * 64, "sha256", allowed_root=tmp_path) is False


def test_unsupported_algorithm_raises() -> None:
    """Algorithms outside the whitelist are rejected."""
    with pytest.raises(UnsupportedAlgorithmError):
        compute_text("hello", "sha512")


def test_arbitrary_hashlib_name_rejected() -> None:
    """Even names supported by hashlib are rejected without whitelist entry."""
    with pytest.raises(UnsupportedAlgorithmError):
        compute_bytes(b"hello", "blake2b")


def test_unsupported_algorithm_is_hash_error() -> None:
    """UnsupportedAlgorithmError is a HashError (domain hierarchy)."""
    with pytest.raises(HashError):
        compute_text("hello", "md4")


def test_supported_algorithms() -> None:
    """supported_algorithms exposes exactly the whitelist."""
    algorithms = supported_algorithms()
    assert algorithms == ["SHA256", "SHA1", "MD5"]
    assert len(algorithms) == 3


# ---------------------------------------------------------------------------
# ARES-QA-001 — Path traversal / leitura arbitrária de arquivos
# ---------------------------------------------------------------------------


def test_compute_file_rejects_path_traversal(tmp_path: Path) -> None:
    """A path with ``..`` escaping the allowed root must raise HashError."""
    secret = tmp_path.parent / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")
    with pytest.raises(HashError):
        compute_file(
            tmp_path / ".." / secret.name,
            "sha256",
            allowed_root=tmp_path,
        )


def test_compute_rejects_absolute_path_outside_root(tmp_path: Path) -> None:
    """An absolute path outside the allowed root must raise HashError."""
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("data", encoding="utf-8")
    with pytest.raises(HashError):
        compute(outside, "sha256", allowed_root=tmp_path)


def test_compute_file_accepts_dotdot_that_stays_inside_root(tmp_path: Path) -> None:
    """``..`` that resolves back inside the root is legitimate."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    digest = compute_file(
        sub / ".." / "sample.txt",
        "sha256",
        allowed_root=tmp_path,
    )
    assert digest == SHA256_HELLO


def test_compute_rejects_symlink_escaping_root(tmp_path: Path) -> None:
    """A symlink inside the root pointing outside must raise HashError."""
    outside = tmp_path.parent / "outside_target.txt"
    outside.write_text("data", encoding="utf-8")
    link = tmp_path / "evil_link.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks not permitted on this platform/filesystem")
    with pytest.raises(HashError):
        compute_file(link, "sha256", allowed_root=tmp_path)


def test_compute_file_allows_path_inside_root(tmp_path: Path) -> None:
    """A plain file inside the allowed root hashes normally."""
    sample = tmp_path / "ok.txt"
    sample.write_text("hello", encoding="utf-8")
    assert compute_file(sample, "sha256", allowed_root=tmp_path) == SHA256_HELLO


# ---------------------------------------------------------------------------
# ARES-QA-002 — Fallback silencioso str → texto
# ---------------------------------------------------------------------------


def test_compute_str_missing_pathlike_raises_file_not_found(tmp_path: Path) -> None:
    """A str with path separators that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compute(str(tmp_path / "missing_file.txt"), "sha256", allowed_root=tmp_path)


def test_compute_str_missing_extension_raises_file_not_found() -> None:
    """A str ending in a file extension that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compute("backup_nao_existe.zip", "sha256")


def test_compute_path_missing_raises_file_not_found(tmp_path: Path) -> None:
    """A Path that does not exist raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        compute(tmp_path / "missing.txt", "sha256", allowed_root=tmp_path)


def test_compute_str_plain_text_remains_text() -> None:
    """A plain word with no path traits is still hashed as text."""
    result = compute("hello", "sha256")
    assert result.source == "text"
    assert result.hexdigest == SHA256_HELLO


# ---------------------------------------------------------------------------
# ARES-QA-003 — Comparação em tempo constante (hmac.compare_digest)
# ---------------------------------------------------------------------------


def test_verify_file_constant_time_match_and_mismatch(tmp_path: Path) -> None:
    """verify_file True/False paths rely on hmac.compare_digest semantics."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    assert verify_file(sample, SHA256_HELLO, "sha256", allowed_root=tmp_path) is True
    assert verify_file(sample, "0" * 64, "sha256", allowed_root=tmp_path) is False


# ---------------------------------------------------------------------------
# ARES-QA-004 — Algoritmos fracos emitem DeprecationWarning
# ---------------------------------------------------------------------------


def test_weak_algorithm_emits_deprecation_warning() -> None:
    """MD5/SHA-1 usage emits a DeprecationWarning at runtime."""
    with pytest.warns(DeprecationWarning):
        compute_text("hello", "md5")
    with pytest.warns(DeprecationWarning):
        compute_bytes(b"hello", HashAlgorithm.SHA1)


# ---------------------------------------------------------------------------
# ARES-QA-006 / 009 / 010 — Validação de tipo na fronteira
# ---------------------------------------------------------------------------


def test_algorithm_none_raises_unsupported() -> None:
    """A None algorithm is rejected with the domain error."""
    with pytest.raises(UnsupportedAlgorithmError):
        compute_text("hello", None)  # type: ignore[arg-type]


def test_algorithm_int_raises_unsupported() -> None:
    """A non-string, non-member algorithm is rejected with the domain error."""
    with pytest.raises(UnsupportedAlgorithmError):
        compute_bytes(b"hello", 12345)  # type: ignore[arg-type]


def test_compute_invalid_source_type_raises() -> None:
    """compute rejects non str/bytes/Path sources with a clear TypeError."""
    with pytest.raises(TypeError):
        compute(12345, "sha256")  # type: ignore[arg-type]


def test_verify_file_expected_none_raises(tmp_path: Path) -> None:
    """verify_file with expected=None raises a clear error."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises((TypeError, ValueError)):
        verify_file(sample, None, "sha256", allowed_root=tmp_path)  # type: ignore[arg-type]


def test_verify_file_expected_non_hex_raises(tmp_path: Path) -> None:
    """verify_file with a non-hex expected digest raises ValueError."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        verify_file(sample, "not-a-hex-value!", "sha256", allowed_root=tmp_path)


def test_verify_file_expected_wrong_length_raises(tmp_path: Path) -> None:
    """verify_file with a digest of the wrong length raises ValueError."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        verify_file(sample, "abcd1234", "sha256", allowed_root=tmp_path)


def test_compute_file_chunk_size_wrong_type_raises(tmp_path: Path) -> None:
    """chunk_size of the wrong type raises ValueError."""
    sample = tmp_path / "sample.txt"
    sample.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        compute_file(sample, "sha256", chunk_size="1024", allowed_root=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        compute_file(sample, "sha256", chunk_size=1024.5, allowed_root=tmp_path)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# ARES-QA-011 — Erros de encoding mapeados
# ---------------------------------------------------------------------------


def test_unknown_encoding_raises_value_error() -> None:
    """An unknown codec name raises a clear ValueError (not LookupError)."""
    with pytest.raises(ValueError):
        compute_text("hello", "sha256", encoding="no-such-encoding")


# ---------------------------------------------------------------------------
# ARES-QA-016 — Exceção estruturada com o algoritmo ofensivo
# ---------------------------------------------------------------------------


def test_unsupported_algorithm_error_carries_algorithm() -> None:
    """UnsupportedAlgorithmError exposes the offending algorithm."""
    with pytest.raises(UnsupportedAlgorithmError) as exc_info:
        compute_text("hello", "sha512")
    assert exc_info.value.algorithm == "sha512"


# ---------------------------------------------------------------------------
# Arquivo vazio e arquivos binários
# ---------------------------------------------------------------------------


def test_compute_file_empty_file(tmp_path: Path) -> None:
    """An empty file hashes to the well-known empty SHA-256 digest."""
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert compute_file(empty, "sha256", allowed_root=tmp_path) == expected


def test_compute_file_binary_bytes(tmp_path: Path) -> None:
    """Binary files hash identically to hashlib over the raw bytes."""
    data = bytes(range(256)) + b"\x00\x01\xff\xfe"
    sample = tmp_path / "binary.bin"
    sample.write_bytes(data)
    expected = sha256(data).hexdigest()
    assert compute_file(sample, "sha256", allowed_root=tmp_path) == expected


def test_compute_binary_file_path_source(tmp_path: Path) -> None:
    """compute() with a Path to a binary file reports source='file'."""
    data = b"\x00\x01\x02\xff\xfe\x00\x10"
    sample = tmp_path / "bin.dat"
    sample.write_bytes(data)
    result = compute(sample, "sha256", allowed_root=tmp_path)
    assert result.source == "file"
    assert result.size_bytes == len(data)
    assert result.hexdigest == sha256(data).hexdigest()


def test_verify_file_binary_file(tmp_path: Path) -> None:
    """verify_file validates binary content correctly (match and mismatch)."""
    data = b"\x00\x01\xff" * 1024
    sample = tmp_path / "bin.dat"
    sample.write_bytes(data)
    expected = sha256(data).hexdigest()
    assert verify_file(sample, expected, "sha256", allowed_root=tmp_path) is True
    assert verify_file(sample, "0" * 64, "sha256", allowed_root=tmp_path) is False
