"""Motores de cálculo do núcleo EDY Shield."""

from app.core.algorithms.batch import (
    BatchResult,
    hash_directory,
    hash_files,
)
from app.core.algorithms.hash_checker import (
    DEFAULT_CHUNK_SIZE,
    HashAlgorithm,
    compute,
    compute_bytes,
    compute_file,
    compute_text,
    supported_algorithms,
    verify_file,
)

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "BatchResult",
    "HashAlgorithm",
    "compute",
    "compute_bytes",
    "compute_file",
    "compute_text",
    "hash_directory",
    "hash_files",
    "supported_algorithms",
    "verify_file",
]
