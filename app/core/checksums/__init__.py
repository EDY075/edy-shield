"""Checksum Files — criação e verificação de arquivos de checksum (v1.2).

Fonte canônica: :mod:`app.core.checksums.checksum`.
"""

from app.core.checksums.checksum import (
    SUPPORTED_SUFFIXES,
    ChecksumEntry,
    ChecksumError,
    ChecksumReport,
    create_checksum_file,
    parse_checksum_file,
    verify_checksum_file,
)

__all__ = [
    "SUPPORTED_SUFFIXES",
    "ChecksumEntry",
    "ChecksumError",
    "ChecksumReport",
    "create_checksum_file",
    "parse_checksum_file",
    "verify_checksum_file",
]
