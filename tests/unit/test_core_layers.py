"""Layer/architecture tests for the EDY Shield core refactor (Sprint 2 — Missão 2).

Verifies the new core layers (``exceptions``, ``crypto``, ``filesystem``,
``validators``), the compat shims (``models.common``, ``services.file_utils``)
and the public API surface of ``app.core.algorithms``.
"""

import pytest

from app.core.algorithms import (
    DEFAULT_CHUNK_SIZE,
    compute,
    compute_bytes,
    compute_file,
    compute_text,
    supported_algorithms,
    verify_file,
)
from app.core.algorithms import (
    HashAlgorithm as AlgorithmsHashAlgorithm,
)
from app.core.algorithms import __all__ as algorithms_all
from app.core.crypto import HashAlgorithm as CryptoHashAlgorithm
from app.core.crypto import safe_compare
from app.core.exceptions import (
    EDYShieldError,
    FilesystemError,
    HashError,
    UnsupportedAlgorithmError,
    ValidationError,
)
from app.core.models.common import (
    HashError as CommonHashError,
)
from app.core.models.common import (
    UnsupportedAlgorithmError as CommonUnsupportedAlgorithmError,
)
from app.core.validators import validate_chunk_size, validate_expected
from app.services.file_utils import resolve_safe_path, validate_allowed_root

# ---------------------------------------------------------------------------
# Hierarquia de exceções (app.core.exceptions)
# ---------------------------------------------------------------------------


def test_exception_hierarchy() -> None:
    """The domain error hierarchy has EDYShieldError as its root."""
    assert issubclass(HashError, EDYShieldError)
    assert issubclass(UnsupportedAlgorithmError, HashError)
    assert issubclass(UnsupportedAlgorithmError, EDYShieldError)
    assert issubclass(ValidationError, EDYShieldError)
    assert issubclass(FilesystemError, EDYShieldError)


def test_edyshield_error_exposes_message() -> None:
    """EDYShieldError keeps the message attribute contract."""
    error = EDYShieldError("boom")
    assert error.message == "boom"
    assert isinstance(error, Exception)


def test_unsupported_algorithm_error_exposes_algorithm() -> None:
    """UnsupportedAlgorithmError keeps the algorithm attribute contract."""
    error = UnsupportedAlgorithmError("unsupported", algorithm="md4")
    assert error.algorithm == "md4"
    assert error.message == "unsupported"


# ---------------------------------------------------------------------------
# Compat shims: models.common e services.file_utils
# ---------------------------------------------------------------------------


def test_models_common_shim_still_exports() -> None:
    """models.common re-exports the canonical exceptions (compat)."""
    assert CommonHashError is HashError
    assert CommonUnsupportedAlgorithmError is UnsupportedAlgorithmError


def test_services_file_utils_shim_still_exports() -> None:
    """services.file_utils still exports the path-validation frontier (compat)."""
    assert callable(resolve_safe_path)
    assert callable(validate_allowed_root)


# ---------------------------------------------------------------------------
# Camada crypto
# ---------------------------------------------------------------------------


def test_safe_compare_true_and_false() -> None:
    """safe_compare returns True on match and False on mismatch."""
    assert safe_compare("abc", "abc") is True
    assert safe_compare("abc", "abd") is False


def test_hash_algorithm_is_shared_identity() -> None:
    """HashAlgorithm is the same object across algorithms and crypto layers."""
    assert AlgorithmsHashAlgorithm is CryptoHashAlgorithm


# ---------------------------------------------------------------------------
# Camada validators
# ---------------------------------------------------------------------------


def test_validate_chunk_size_accepts_positive() -> None:
    """A positive integer chunk size passes validation."""
    validate_chunk_size(1)
    validate_chunk_size(65536)


def test_validate_chunk_size_rejects_invalid() -> None:
    """Zero, negative and bool chunk sizes are rejected (ARES-QA-010)."""
    with pytest.raises(ValueError):
        validate_chunk_size(0)
    with pytest.raises(ValueError):
        validate_chunk_size(-1)
    with pytest.raises(ValueError):
        validate_chunk_size(True)  # type: ignore[arg-type]


def test_validate_expected_accepts_valid_hex() -> None:
    """A valid hex digest is normalized to lowercase."""
    assert validate_expected("A" * 64, CryptoHashAlgorithm.SHA256) == "a" * 64
    assert validate_expected(f"  {('b' * 40).upper()}  ", CryptoHashAlgorithm.SHA1) == "b" * 40


def test_validate_expected_rejects_non_str() -> None:
    """A non-str expected value raises TypeError (ARES-QA-009)."""
    with pytest.raises(TypeError):
        validate_expected(None, CryptoHashAlgorithm.SHA256)  # type: ignore[arg-type]


def test_validate_expected_rejects_non_hex() -> None:
    """A non-hex expected digest raises ValueError."""
    with pytest.raises(ValueError):
        validate_expected("not-a-hex-value!", CryptoHashAlgorithm.SHA256)


def test_validate_expected_rejects_wrong_length() -> None:
    """A digest of the wrong length for the algorithm raises ValueError."""
    with pytest.raises(ValueError):
        validate_expected("abcd1234", CryptoHashAlgorithm.SHA256)
    with pytest.raises(ValueError):
        validate_expected("a" * 64, CryptoHashAlgorithm.MD5)


# ---------------------------------------------------------------------------
# API pública de app.core.algorithms
# ---------------------------------------------------------------------------


def test_algorithms_public_api_symbols() -> None:
    """app.core.algorithms exports the 8 stable symbols + batch helpers."""
    assert set(algorithms_all) == {
        "BatchResult",
        "DEFAULT_CHUNK_SIZE",
        "HashAlgorithm",
        "compute",
        "compute_bytes",
        "compute_file",
        "compute_text",
        "hash_directory",
        "hash_files",
        "supported_algorithms",
        "verify_file",
    }


def test_algorithms_public_api_callable() -> None:
    """Every public API symbol is reachable and callable."""
    assert DEFAULT_CHUNK_SIZE > 0
    assert callable(compute)
    assert callable(compute_bytes)
    assert callable(compute_file)
    assert callable(compute_text)
    assert callable(supported_algorithms)
    assert callable(verify_file)
    assert supported_algorithms() == ["SHA256", "SHA1", "MD5"]
