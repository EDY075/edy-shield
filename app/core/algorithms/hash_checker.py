"""Core Hash Checker module for EDY Shield.

Computes cryptographic hashes (SHA-256, SHA-1, MD5) from raw bytes, text or
files using only the Python standard library (``hashlib``).

Since Sprint 2 (Missão 2) this module **delegates** to the layered core:

    * :mod:`app.core.crypto` — algorithm whitelist (``HashAlgorithm``),
      ``normalize_algorithm``, ``new_hasher`` and constant-time
      ``safe_compare``.
    * :mod:`app.core.filesystem` — path validation frontier
      (``resolve_safe_path`` + ``ensure_regular_file``).
    * :mod:`app.core.validators` — input validation (``validate_chunk_size``,
      ``validate_expected``).
    * :mod:`app.core.exceptions` — domain error hierarchy (``HashError``,
      ``UnsupportedAlgorithmError``).

Security notes (ARCHITECTURE.md §6 — segurança-first):

    * SHA-256 is the recommended default algorithm. SHA-1 and MD5 are
      provided for legacy compatibility and must be used **only for
      non-critical integrity checks** — both are considered
      cryptographically broken for collision resistance. The core emits a
      :class:`DeprecationWarning` at runtime whenever they are used
      (ARES-QA-004).

    * Algorithm names are validated against an explicit whitelist
      (:class:`HashAlgorithm`) *before* being forwarded to ``hashlib.new``.
      Arbitrary algorithm names coming from callers are never accepted.

    * File paths are validated at the boundary by
      :mod:`app.core.filesystem` (``resolve_safe_path`` +
      ``ensure_regular_file``): paths are resolved and must stay inside an
      allowed root directory (default: the process current working
      directory). Absolute paths outside the root, ``..`` traversal that
      escapes it, and symlinks resolving outside are rejected with
      :class:`~app.core.exceptions.HashError` (ARES-QA-001). Callers that
      legitimately need to hash files elsewhere must pass ``allowed_root``
      explicitly.

    * Strings that look like paths (contain a path separator or end with a
      file extension) are never hashed silently as text. If the referenced
      file does not exist, a :class:`FileNotFoundError` is raised instead of
      hashing the path string (ARES-QA-002).

   **TOCTOU hardening** (v1.1, ARES-QA-008): files are opened using
      ``os.open`` with ``O_NOFOLLOW`` (where available) and the file
      descriptor is verified with ``os.fstat`` to confirm it is a regular
      file **after** opening, closing the race window between
      ``resolve_safe_path`` / ``ensure_regular_file`` and the actual read.
"""

import os
import stat
from pathlib import Path

from app.core.crypto import HashAlgorithm, new_hasher, normalize_algorithm, safe_compare
from app.core.exceptions import HashError
from app.core.filesystem import ensure_regular_file, resolve_safe_path
from app.core.models.hashes import HashResult
from app.core.validators import validate_chunk_size, validate_expected

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "HashAlgorithm",
    "compute",
    "compute_bytes",
    "compute_file",
    "compute_text",
    "supported_algorithms",
    "verify_file",
]

DEFAULT_CHUNK_SIZE: int = 65536


def _looks_like_path(value: str) -> bool:
    """Return ``True`` when a string is more likely a path than plain text.

    Strings containing path separators (``/`` or ``\\``) or ending with a file
    extension are treated as paths. Plain words (no separators, no suffix) are
    treated as text (ARES-QA-002).
    """
    if "/" in value or "\\" in value:
        return True
    return bool(Path(value).suffix)


def _compute_text_with_size(
    text: str,
    member: HashAlgorithm,
    encoding: str,
) -> tuple[str, int]:
    """Encode ``text`` once and return ``(hexdigest, size_bytes)`` (ARES-QA-014).

    Args:
        text: Text to hash.
        member: Normalized algorithm member.
        encoding: Text encoding.

    Returns:
        A tuple of the hex digest and the encoded byte length.

    Raises:
        ValueError: If ``encoding`` is unknown (``LookupError`` translated,
            ARES-QA-011).
        UnicodeEncodeError: If ``text`` cannot be encoded with ``encoding``.
    """
    try:
        encoded = text.encode(encoding)
    except LookupError as exc:
        raise ValueError(f"Unknown text encoding: {encoding!r}.") from exc
    return compute_bytes(encoded, member), len(encoded)


def _compute_file_impl(
    path: Path | str,
    member: HashAlgorithm,
    chunk_size: int,
    allowed_root: Path | None,
) -> tuple[str, int]:
    """Hash a file in chunks and return ``(hexdigest, size_bytes)``.

    Path validation (root containment, existence, regular-file check) is
    delegated to :func:`app.core.filesystem.resolve_safe_path` and
    :func:`app.core.filesystem.ensure_regular_file` — the single validation
    frontier of the application.

    The byte count is accumulated while reading so ``size_bytes`` always
    matches the hashed content (ARES-QA-012). Special files (FIFO, devices,
    sockets) are rejected up front to avoid blocking the process
    (ARES-QA-007).

    Note (ARES-QA-008): in v1.1, the file is opened with ``os.open`` and
    ``O_NOFOLLOW`` (where available) to close the race window between path
    validation and the read. After opening, ``os.fstat`` on the file
    descriptor confirms the file is still a regular file before any data
    is hashed. This mitigates TOCTOU (check → open → read) races.

    Args:
        path: Path to the file (``Path`` or ``str``).
        member: Normalized algorithm member.
        chunk_size: Bytes read per iteration (already validated).
        allowed_root: Root directory restriction, or ``None`` for cwd.

    Returns:
        A tuple of the hex digest and the number of bytes read.

    Raises:
        HashError: If the path escapes ``allowed_root`` or is a non-regular
            file.
        IsADirectoryError: If the path points to a directory.
        FileNotFoundError: If the path does not exist.
    """
    target = resolve_safe_path(path, allowed_root=allowed_root, strict=True)
    ensure_regular_file(target)

    hasher = new_hasher(member)
    size_bytes = 0

    # TOCTOU hardening (ARES-QA-008): open with O_NOFOLLOW (reject symlink
    # swaps) and fstat after open to confirm we still have a regular file.
    # Multi-platform feature detection (no `platform` branching):
    # - O_BINARY only exists on Windows (forces binary mode on open);
    #   on POSIX it is a no-op and absent, so it defaults to 0.
    # - O_NOFOLLOW is well-supported on Linux/macOS but may not be defined
    #   on Windows; fall back to 0 (regular open; TOCTOU risk accepted).
    _O_BINARY = getattr(os, "O_BINARY", 0)
    _O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(target, os.O_RDONLY | _O_BINARY | _O_NOFOLLOW)
    try:
        # fstat on the open fd — the file we opened is the one we hash.
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise HashError(f"Cannot hash non-regular file: {target.name}")

        with os.fdopen(fd, "rb") as file_obj:
            while chunk := file_obj.read(chunk_size):
                hasher.update(chunk)
                size_bytes += len(chunk)
    except BaseException:
        os.close(fd)
        raise

    return hasher.hexdigest(), size_bytes


def compute_bytes(data: bytes, algorithm: HashAlgorithm | str) -> str:
    """Compute the hex digest of raw bytes.

    Args:
        data: Raw bytes to hash.
        algorithm: Hash algorithm to use.

    Returns:
        Hexadecimal digest, lowercase.

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not in the whitelist.
    """
    member = normalize_algorithm(algorithm)
    hasher = new_hasher(member)
    hasher.update(data)
    return hasher.hexdigest()


def compute_text(
    text: str,
    algorithm: HashAlgorithm | str,
    encoding: str = "utf-8",
) -> str:
    """Compute the hex digest of a string.

    The string is encoded with ``encoding`` before hashing.

    Args:
        text: Text to hash.
        algorithm: Hash algorithm to use.
        encoding: Text encoding (default ``"utf-8"``).

    Returns:
        Hexadecimal digest, lowercase.

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not in the whitelist.
        ValueError: If ``encoding`` is not a known codec (ARES-QA-011).
        UnicodeEncodeError: If ``text`` cannot be encoded with ``encoding``.
    """
    member = normalize_algorithm(algorithm)
    digest, _ = _compute_text_with_size(text, member, encoding)
    return digest


def compute_file(
    path: Path | str,
    algorithm: HashAlgorithm | str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    *,
    allowed_root: Path | None = None,
) -> str:
    """Compute the hex digest of a file, reading it in chunks.

    Files are read in ``chunk_size`` blocks so that large files are never
    loaded entirely into memory (mitigation against local DoS — see
    ARCHITECTURE.md §6).

    Args:
        path: Path to the file (``Path`` or ``str``).
        algorithm: Hash algorithm to use.
        chunk_size: Number of bytes read per iteration (must be a positive
            integer).
        allowed_root: Root directory restriction. When ``None``, the current
            working directory is used; paths resolving outside it raise
            :class:`HashError` (ARES-QA-001).

    Returns:
        Hexadecimal digest, lowercase.

    Raises:
        UnsupportedAlgorithmError: If the algorithm is not in the whitelist.
        ValueError: If ``chunk_size`` is not a positive integer.
        HashError: If the path escapes ``allowed_root`` or is a non-regular
            file.
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If ``path`` points to a directory.
    """
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)
    digest, _ = _compute_file_impl(path, member, chunk_size, allowed_root)
    return digest


def compute(
    source: Path | str | bytes,
    algorithm: HashAlgorithm | str,
    *,
    encoding: str = "utf-8",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    allowed_root: Path | None = None,
) -> HashResult:
    """Compute a hash and return the structured :class:`HashResult`.

    Dispatches the source to the appropriate computation:

    - ``bytes`` → raw byte hashing (``source="bytes"``);
    - ``Path``  → file hashing (``source="file"``);
    - ``str``   → treated as a file path if it *looks like* one (contains a
      path separator or ends with a file extension), otherwise hashed as text
      (``source="text"``). A path-like string that does not exist raises
      :class:`FileNotFoundError` — it is **never** hashed silently as text
      (ARES-QA-002).

    Args:
        source: File path, text string or raw bytes.
        algorithm: Hash algorithm to use.
        encoding: Text encoding for ``str`` sources hashed as text.
        chunk_size: Chunk size used for file sources (positive integer).
        allowed_root: Root directory restriction for file sources. When
            ``None``, the current working directory is used (ARES-QA-001).

    Returns:
        A frozen :class:`HashResult` with algorithm, digest and source metadata.

    Raises:
        TypeError: If ``source`` is not ``str``, ``bytes`` or ``Path``.
        FileNotFoundError: If a path-like source does not exist.
        IsADirectoryError: If a file source points to a directory.
        HashError: If a file source escapes ``allowed_root`` or is a
            non-regular file.
        UnsupportedAlgorithmError: If the algorithm is not supported.
        ValueError: If ``chunk_size`` is not a positive integer.
    """
    member = normalize_algorithm(algorithm)

    if isinstance(source, bytes):
        hexdigest = compute_bytes(source, member)
        return HashResult(
            algorithm=member.name,
            hexdigest=hexdigest,
            source="bytes",
            size_bytes=len(source),
        )

    if isinstance(source, Path):
        path = source
    elif isinstance(source, str):
        if _looks_like_path(source):
            path = Path(source)
        else:
            hexdigest, size_bytes = _compute_text_with_size(source, member, encoding)
            return HashResult(
                algorithm=member.name,
                hexdigest=hexdigest,
                source="text",
                size_bytes=size_bytes,
            )
    else:
        raise TypeError(f"source must be str, bytes or Path, got {type(source).__name__}.")

    validate_chunk_size(chunk_size)
    hexdigest, size_bytes = _compute_file_impl(path, member, chunk_size, allowed_root)
    return HashResult(
        algorithm=member.name,
        hexdigest=hexdigest,
        source="file",
        path=path.resolve(),
        size_bytes=size_bytes,
    )


def verify_file(
    path: Path | str,
    expected: str,
    algorithm: HashAlgorithm | str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    allowed_root: Path | None = None,
) -> bool:
    """Verify that a file matches an expected hash (case-insensitive).

    The freshly computed digest is compared against ``expected`` ignoring case
    and surrounding whitespace, using :func:`hmac.compare_digest` for a
    constant-time comparison (ARES-QA-003).

    Args:
        path: Path to the file (``Path`` or ``str``).
        expected: Expected hexadecimal digest (any case).
        algorithm: Hash algorithm to use.
        chunk_size: Chunk size used to read the file (positive integer).
        allowed_root: Root directory restriction. When ``None``, the current
            working directory is used (ARES-QA-001).

    Returns:
        ``True`` if the digests match, ``False`` otherwise.

    Raises:
        TypeError: If ``expected`` is not a ``str``.
        ValueError: If ``expected`` is not a valid hex digest of the correct
            length, or ``chunk_size`` is not a positive integer.
        UnsupportedAlgorithmError: If the algorithm is not in the whitelist.
        HashError: If the path escapes ``allowed_root`` or is a non-regular
            file.
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If ``path`` points to a directory.
    """
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)
    expected_digest = validate_expected(expected, member)
    actual = compute_file(path, member, chunk_size=chunk_size, allowed_root=allowed_root)
    return safe_compare(actual, expected_digest)


def supported_algorithms() -> list[str]:
    """List the names of supported hash algorithms.

    Returns:
        Algorithm names, e.g. ``["SHA256", "SHA1", "MD5"]``.
    """
    return [member.name for member in HashAlgorithm]
