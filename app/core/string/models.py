"""Modelos do String Analyzer (v2.1 — M2.1).

Tipos puros do Core, sem dependência de plugins (ADR-002):

* :class:`StringSeverity` — nível de severidade próprio do Core (o plugin
  mapeia para :class:`~app.plugins.contracts.Severity`).
* :class:`StringType` — classificação ampla exibida (URL, IP, HASH, TOKEN...).
* :class:`StringCategory` — categoria específica do achado.
* :class:`StringMatch` — um achado individual (tipo, valor, linha, severidade,
  categoria e confiança).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class StringSeverity(Enum):
    """Severidade de um achado (Core — independente de plugins)."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class StringType(Enum):
    """Classificação ampla do achado (campo ``type`` do resultado).

    Agrupa categorias em famílias legíveis para relatórios:
    URL, IP, HASH, EMAIL, TOKEN, COMMAND, CREDENTIAL, PATH, CERT, HEX,
    BASE64, JWT, LONG.
    """

    URL = "URL"
    IP = "IP"
    HASH = "HASH"
    EMAIL = "EMAIL"
    TOKEN = "TOKEN"
    COMMAND = "COMMAND"
    CREDENTIAL = "CREDENTIAL"
    PATH = "PATH"
    CERT = "CERT"
    HEX = "HEX"
    BASE64 = "BASE64"
    JWT = "JWT"
    LONG = "LONG"


class StringCategory(Enum):
    """Categoria específica detectada pelo engine."""

    URL = "url"
    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DOMAIN = "domain"
    EMAIL = "email"
    HASH_MD5 = "hash_md5"
    HASH_SHA1 = "hash_sha1"
    HASH_SHA256 = "hash_sha256"
    BASE64 = "base64"
    HEX = "hex"
    JWT = "jwt"
    API_KEY = "api_key"
    BEARER_TOKEN = "bearer_token"
    PATH_WINDOWS = "path_windows"
    PATH_POSIX = "path_posix"
    COMMAND_POWERSHELL = "command_powershell"
    COMMAND_BASH = "command_bash"
    COMMAND_CMD = "command_cmd"
    DOWNLOAD = "download"
    REMOTE_EXEC = "remote_exec"
    CERTUTIL = "certutil"
    BITSADMIN = "bitsadmin"
    REGSVR32 = "regsvr32"
    RUNDLL32 = "rundll32"
    MSHTA = "mshta"
    PEM_CERTIFICATE = "pem_certificate"
    CREDENTIAL = "credential"
    LONG_TOKEN = "long_token"


@dataclass(frozen=True, slots=True)
class StringMatch:
    """Um achado do String Analyzer.

    Attributes:
        category: Categoria específica.
        value: Texto detectado.
        start: Índice inicial no texto analisado (0-based).
        end: Índice final (exclusivo) no texto analisado.
        severity: Severidade da categoria.
        confidence: Confiança da detecção (0.0 a 1.0).
        type: Classificação ampla (ex.: URL, IP, HASH, TOKEN, COMMAND).
        line: Número da linha (1-based) onde o achado ocorreu, ou ``None``
            quando a análise não é linha a linha.
    """

    category: StringCategory
    value: str
    start: int
    end: int
    severity: StringSeverity
    confidence: float
    type: StringType
    line: int | None = None
