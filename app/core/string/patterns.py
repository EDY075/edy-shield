r"""Regex reutilizáveis do String Analyzer (v2.1 — M2.1).

Padrões compilados uma única vez (performance) e reutilizáveis por outros
módulos (ex.: IOC Scanner na M5). Cada categoria mapeia para
``(regex, severidade, confiança, tipo amplo)``.

Notas de design:

* **Engine de detecção, não validador**: o IPv4 captura ``\d{1,3}(\.\d{1,3}){3}``
  sem validar octetos 0-255 — validação estrita é responsabilidade do consumidor.
* **Sem pontuação final**: padrões evitam capturar ``.``/``)``/``,`` finais.
* **Confiança por categoria**: regex específicos (API_KEY, JWT, PEM, hashes)
  têm confiança alta (0.9); padrões genéricos (BASE64) têm confiança baixa (0.4).
* **Tipo amplo** (``StringType``): agrupa categorias para relatórios.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.string.models import StringCategory, StringSeverity, StringType

# ---------------------------------------------------------------------------
# Regex por categoria
# ---------------------------------------------------------------------------

_RE_URL = re.compile(r"\b(?:https?|ftp)://[^\s<>\"']+")
_RE_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RE_IPV6 = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b|"
    r"\b(?:[0-9a-fA-F]{1,4}:){1,7}::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}\b"
)
_RE_DOMAIN = re.compile(
    r"\b(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"(?:[a-zA-Z]{2,63})\b"
)
_RE_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,63}\b")
_RE_HASH_MD5 = re.compile(r"\b(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])\b")
_RE_HASH_SHA1 = re.compile(r"\b(?<![0-9a-fA-F])[0-9a-fA-F]{40}(?![0-9a-fA-F])\b")
_RE_HASH_SHA256 = re.compile(r"\b(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])\b")
_RE_BASE64 = re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b")
_RE_HEX = re.compile(r"\b(?<![0-9a-fA-F])[0-9a-fA-F]{16,}(?![0-9a-fA-F])\b")
_RE_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")
_RE_API_KEY = re.compile(
    r"\b(?:"
    r"AKIA[0-9A-Z]{16}"
    r"|gh[pousr]_[A-Za-z0-9]{36,}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|(?:sk|pk)_(?:test|live)_[0-9a-zA-Z]{16,}"
    r")\b"
)
_RE_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b")
_RE_PATH_WINDOWS = re.compile(r"\b[A-Za-z]:[\\/][^\s\"<>|?*]*")
_RE_PATH_POSIX = re.compile(
    r"\b/(?:bin|boot|dev|etc|home|lib|opt|proc|root|sbin|srv|tmp|usr|var)"
    r"(?:/[^\s\"<>]*)?"
)

# Comandos e técnicas (Blue Team / detecção de artefatos maliciosos)
_RE_POWERSHELL = re.compile(
    r"\b(?:powershell|pwsh)(?:\.[a-z]+)?\b.*?(?:"
    r"-enc(?:odedcommand)?\b|-exec(?:utionpolicy)?\s+bypass\b|"
    r"Invoke-Expression\b|\bIEX\s*\(|\bIEX\s+[A-Za-z]|"
    r"downloadstring\b|DownloadFile\b|frombase64string\b)",
    re.IGNORECASE,
)
_RE_BASH = re.compile(
    r"\b(?:bash|sh)\s+-c\b|\beval\s+\(|\$\s*\(|\b(?:wget|curl)\s+['\"]?https?://|/dev/tcp/",
    re.IGNORECASE,
)
_RE_CMD = re.compile(r"\bcmd(?:\.exe)?\s*/[cC]\b")
_RE_DOWNLOAD = re.compile(
    r"\b(?:curl(?:\.exe)?|wget)\s+(?:-[A-Za-z]+\s+)*['\"]?https?://"
    r"|\b(?:Invoke-WebRequest|iwr|Start-BitsTransfer|Invoke-DownloadString)\b",
    re.IGNORECASE,
)
_RE_REMOTE_EXEC = re.compile(
    r"\b(?:psexec|paexec)\b|\bwmic\s+process\s+call\s+create\b"
    r"|\bschtasks\s+/create\b|\bat\s+\\\\",
    re.IGNORECASE,
)
_RE_CERTUTIL = re.compile(r"\bcertutil\s+(?:-urlcache|-decode|-encode)\b", re.IGNORECASE)
_RE_BITSADMIN = re.compile(r"\bbitsadmin\s+/transfer\b", re.IGNORECASE)
_RE_REGSVR32 = re.compile(r"\bregsvr32\s+/(?:s|u|i)\b", re.IGNORECASE)
_RE_RUNDLL32 = re.compile(r"\brundll32(?:\.exe)?\b", re.IGNORECASE)
_RE_MSHTA = re.compile(r"\bmshta(?:\.exe)?\b", re.IGNORECASE)

# Certificados PEM
_RE_PEM = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?"
    r"(?:PRIVATE|PUBLIC|ENCRYPTED|CERTIFICATE) KEY-----|"
    r"-----BEGIN CERTIFICATE-----"
)

# Credenciais aparentes em texto
_RE_CREDENTIAL = re.compile(
    r"\b(?:password|passwd|pwd|senha)\s*[:=]\s*\S+"
    r"|\b(?:user(?:name)?|usuario)\s*[:=]\s*\S+\s+(?:password|pass|senha)\s*[:=]",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Especificação por categoria
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _PatternSpec:
    """Especificação de um padrão: regex + severidade + confiança + tipo."""

    regex: re.Pattern[str]
    severity: StringSeverity
    confidence: float
    type: StringType


#: Mapa categoria → especificação. Ordem de inserção = ordem de avaliação.
PATTERNS: dict[StringCategory, _PatternSpec] = {
    StringCategory.URL: _PatternSpec(_RE_URL, StringSeverity.LOW, 0.9, StringType.URL),
    StringCategory.IPV4: _PatternSpec(_RE_IPV4, StringSeverity.LOW, 0.9, StringType.IP),
    StringCategory.IPV6: _PatternSpec(_RE_IPV6, StringSeverity.LOW, 0.8, StringType.IP),
    StringCategory.DOMAIN: _PatternSpec(_RE_DOMAIN, StringSeverity.LOW, 0.7, StringType.URL),
    StringCategory.EMAIL: _PatternSpec(_RE_EMAIL, StringSeverity.MEDIUM, 0.9, StringType.EMAIL),
    StringCategory.HASH_MD5: _PatternSpec(
        _RE_HASH_MD5, StringSeverity.MEDIUM, 0.9, StringType.HASH
    ),
    StringCategory.HASH_SHA1: _PatternSpec(
        _RE_HASH_SHA1, StringSeverity.MEDIUM, 0.9, StringType.HASH
    ),
    StringCategory.HASH_SHA256: _PatternSpec(
        _RE_HASH_SHA256, StringSeverity.MEDIUM, 0.9, StringType.HASH
    ),
    StringCategory.BASE64: _PatternSpec(_RE_BASE64, StringSeverity.MEDIUM, 0.4, StringType.BASE64),
    StringCategory.HEX: _PatternSpec(_RE_HEX, StringSeverity.LOW, 0.6, StringType.HEX),
    StringCategory.JWT: _PatternSpec(_RE_JWT, StringSeverity.HIGH, 0.95, StringType.JWT),
    StringCategory.API_KEY: _PatternSpec(
        _RE_API_KEY, StringSeverity.CRITICAL, 0.95, StringType.TOKEN
    ),
    StringCategory.BEARER_TOKEN: _PatternSpec(
        _RE_BEARER, StringSeverity.HIGH, 0.85, StringType.TOKEN
    ),
    StringCategory.PATH_WINDOWS: _PatternSpec(
        _RE_PATH_WINDOWS, StringSeverity.LOW, 0.6, StringType.PATH
    ),
    StringCategory.PATH_POSIX: _PatternSpec(
        _RE_PATH_POSIX, StringSeverity.LOW, 0.6, StringType.PATH
    ),
    StringCategory.COMMAND_POWERSHELL: _PatternSpec(
        _RE_POWERSHELL, StringSeverity.HIGH, 0.8, StringType.COMMAND
    ),
    StringCategory.COMMAND_BASH: _PatternSpec(
        _RE_BASH, StringSeverity.HIGH, 0.8, StringType.COMMAND
    ),
    StringCategory.COMMAND_CMD: _PatternSpec(
        _RE_CMD, StringSeverity.MEDIUM, 0.8, StringType.COMMAND
    ),
    StringCategory.DOWNLOAD: _PatternSpec(
        _RE_DOWNLOAD, StringSeverity.HIGH, 0.85, StringType.COMMAND
    ),
    StringCategory.REMOTE_EXEC: _PatternSpec(
        _RE_REMOTE_EXEC, StringSeverity.HIGH, 0.85, StringType.COMMAND
    ),
    StringCategory.CERTUTIL: _PatternSpec(
        _RE_CERTUTIL, StringSeverity.HIGH, 0.9, StringType.COMMAND
    ),
    StringCategory.BITSADMIN: _PatternSpec(
        _RE_BITSADMIN, StringSeverity.HIGH, 0.9, StringType.COMMAND
    ),
    StringCategory.REGSVR32: _PatternSpec(
        _RE_REGSVR32, StringSeverity.HIGH, 0.9, StringType.COMMAND
    ),
    StringCategory.RUNDLL32: _PatternSpec(
        _RE_RUNDLL32, StringSeverity.MEDIUM, 0.8, StringType.COMMAND
    ),
    StringCategory.MSHTA: _PatternSpec(_RE_MSHTA, StringSeverity.HIGH, 0.9, StringType.COMMAND),
    StringCategory.PEM_CERTIFICATE: _PatternSpec(
        _RE_PEM, StringSeverity.MEDIUM, 0.95, StringType.CERT
    ),
    StringCategory.CREDENTIAL: _PatternSpec(
        _RE_CREDENTIAL, StringSeverity.CRITICAL, 0.7, StringType.CREDENTIAL
    ),
}


def spec_for(category: StringCategory) -> _PatternSpec:
    """Retornar a especificação (regex/severidade/confiança/tipo) de uma categoria."""
    return PATTERNS[category]
