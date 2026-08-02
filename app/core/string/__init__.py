"""String Analyzer do EDY Shield (v2.1 — M2.1).

Módulo puro do Core (100% stdlib, ADR-001) que identifica indicadores
suspeitos em texto: URLs, IPs, domínios, emails, hashes, base64, hex, JWT,
chaves de API, tokens Bearer, comandos (PowerShell/Bash/CMD), downloads,
execuções remotas, certificados PEM e credenciais aparentes.

Camada: importa apenas o Core (models/patterns/analyzer/tokenizer) — nunca
plugins/services/UI (ADR-002).
"""

from app.core.string.analyzer import analyze_text
from app.core.string.models import (
    StringCategory,
    StringMatch,
    StringSeverity,
    StringType,
)
from app.core.string.patterns import PATTERNS, spec_for
from app.core.string.tokenizer import find_long_tokens, tokenize_lines, tokenize_words

__all__ = [
    "PATTERNS",
    "StringCategory",
    "StringMatch",
    "StringSeverity",
    "StringType",
    "analyze_text",
    "find_long_tokens",
    "spec_for",
    "tokenize_lines",
    "tokenize_words",
]
