"""Result models shared across the Hash Checker domain."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

#: Origin of the hashed data. ``"file"`` when the source is a file on disk,
#: ``"text"`` for strings and ``"bytes"`` for raw byte buffers.
type HashSource = Literal["file", "text", "bytes"]


@dataclass(frozen=True, slots=True)
class HashResult:
    """Immutable result of a hash computation.

    Attributes:
        algorithm: Name of the algorithm used (e.g. ``"SHA256"``).
        hexdigest: Hexadecimal digest, lowercase.
        source: Origin of the hashed data — ``"file"``, ``"text"`` or ``"bytes"``.
        path: Absolute path to the source file, or ``None`` when the source is
            not a file.
        size_bytes: Size of the hashed data in bytes, or ``None`` when unknown.
    """

    algorithm: str
    hexdigest: str
    source: HashSource
    path: Path | None = None
    size_bytes: int | None = None
