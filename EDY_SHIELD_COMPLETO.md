# 🛡️ EDY SHIELD — Projeto Completo para Análise

> **Arquivo gerado por: jr (CyberShield AI / CEO do TITAN AI SQUAD)**
> **Data: 01/08/2026**
> **Versão: 0.1.0**
> **Propósito: Transferência de contexto para análise por outra LLM**

---

## ÍNDICE

1. [Resumo Executivo](#1-resumo-executivo)
2. [Estrutura de Pastas](#2-estrutura-de-pastas)
3. [Arquitetura](#3-arquitetura)
4. [Sprints e Status](#4-sprints-e-status)
5. [Código Fonte Principal](#5-código-fonte-principal)
6. [Plugins e Framework](#6-plugins-e-framework)
7. [Testes](#7-testes)
8. [Quality Gates e Segurança](#8-quality-gates-e-segurança)
9. [Decisões de Arquitetura (ADRs)](#9-decisões-de-arquitetura-adrs)
10. [Pendências e Roadmap](#10-pendências-e-roadmap)

---

## 1. RESUMO EXECUTIVO

**EDY Shield** é uma plataforma modular de **cibersegurança defensiva** em **Python 3.12** (100% stdlib no runtime), com arquitetura em camadas (`ui → services → core`), tipagem forte (mypy strict), e pipeline CI completo. Começou como um Hash Checker e evoluiu para uma plataforma com plugin framework, Log Analyzer, Report Engine e servidor HTTP.

### Métricas Atuais:
| Métrica | Valor |
|---------|-------|
| Versão | `0.1.0` |
| Testes passando | 196+ |
| Cobertura de código | 93.6% |
| mypy strict | 0 issues (25+ arquivos) |
| ruff | todos checks passando |
| Dependências runtime | **0** (stdlib puro) |
| Dependências dev | pytest, pytest-cov, mypy, ruff |
| Linguagem | Python 3.12 (exclusivo) |
| License | MIT |
| CI | GitHub Actions (pytest → mypy → ruff check → ruff format) |

### Arquitetura Técnica:
```
ui (CLI + HTML server)  →  services (file_utils, report_engine, history)  →  core (algorithms, crypto, filesystem, validators, exceptions, config, logging, models)
```

### Componentes Principais:
1. **Hash Checker** — SHA-256/SHA-1/MD5, path traversal mitigado, HMAC compare_ digests
2. **Plugin Framework** — Contracts, Registry, Manager, 2 plugins built-in (Log Analyzer, Hash Checker Plugin)
3. **Log Analyzer** — Detecta FAILED/SUCCESS LOGIN, ERROR, WARNING, CRITICAL em logs
4. **Report Engine** — Exporta ScanResult para JSON, TXT, HTML
5. **History Store** — Persiste resultados de varreduras em disco (JSON)
6. **UI Server** — Servidor HTTP 100% stdlib (ThreadingHTTPServer) com API REST
7. **CI Pipeline** — GitHub Actions com lint, type check, test e coverage gate

---

## 2. ESTRUTURA DE PASTAS

```
EDYShield/
├── app/
│   ├── __init__.py                  # __version__ = "0.1.0"
│   ├── cli/                         # INTERFACE CLI (argparse, stdlib)
│   │   ├── __init__.py
│   │   └── hash_cmd.py              # Comandos hash|verify, entrypoint `edyshield`
│   │
│   ├── core/                         # DOMÍNIO PURO (100% stdlib)
│   │   ├── __init__.py
│   │   ├── algorithms/
│   │   │   ├── __init__.py
│   │   │   └── hash_checker.py      # API pública (8 símbolos): compute, verify, etc.
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   └── settings.py          # Settings (frozen) + load_settings(env EDY_*)
│   │   ├── crypto/
│   │   │   ├── __init__.py
│   │   │   └── hashing.py           # HashAlgorithm, normalize_algorithm, new_hasher, safe_compare
│   │   ├── exceptions/
│   │   │   ├── __init__.py
│   │   │   └── domain.py            # EDYShieldError → HashError / ValidationError / FilesystemError
│   │   ├── filesystem/
│   │   │   ├── __init__.py
│   │   │   └── safe_path.py         # resolve_safe_path, ensure_regular_file (fronteira única anti-escape)
│   │   ├── logging/
│   │   │   ├── __init__.py
│   │   │   └── logger.py            # setup_logging (idempotente), get_logger
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── hashes.py            # HashResult, HashSource
│   │   │   └── common.py            # shim → exceptions (compat legacy)
│   │   ├── report/                  # RESERVADO (sem código — roadmap v2.0)
│   │   │   └── __init__.py
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   └── input.py             # validate_chunk_size, validate_expected
│   │   └── utils/                   # RESERVADO (sem código)
│   │       └── __init__.py
│   │
│   ├── plugins/                     # PLUGIN FRAMEWORK (Sprint 3)
│   │   ├── __init__.py              # Re-export (Plugin, PluginManager, contracts)
│   │   ├── contracts.py            # Severity, Evidence, ScanContext, ScanResult
│   │   ├── plugin_base.py           # ABC Plugin (validate, execute, health_check)
│   │   ├── plugin_errors.py         # PluginError → NotFoundError|RegistrationError|ExecutionError
│   │   ├── plugin_manager.py        # PluginManager — orquestração de execução
│   │   ├── plugin_registry.py       # PluginRegistry — catálogo indexado por nome
│   │   └── builtin/                 # Plugins oficiais
│   │       ├── __init__.py
│   │       ├── log_analyzer.py      # Log Analyzer (detecção padrões de log)
│   │       └── hash_checker_plugin.py # Hash Checker como Plugin
│   │
│   ├── services/                    # CASOS DE USO
│   │   ├── __init__.py              # re-export
│   │   ├── file_utils.py            # shim → core/filesystem (segurança de paths)
│   │   ├── report_engine.py         # to_json / to_txt / to_html
│   │   └── history.py               # HistoryStore (persistência ScanResult → JSON)
│   │
│   └── ui/                          # INTERFACE WEB (HTTP 100% stdlib)
│       ├── __init__.py              # Módulo UI
│       ├── server.py                # ThreadingHTTPServer + REST API
│       └── static/
│           ├── index.html
│           ├── app.js
│           └── css/style.css
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Fixtures compartilhadas
│   ├── unit/
│   │   ├── test_hash_checker.py     # 48+ testes
│   │   ├── test_file_utils.py       # 15 testes
│   │   ├── test_core_layers.py      # 15 testes
│   │   ├── test_cli.py              # CLI completa
│   │   ├── test_config.py           # Settings + load_settings
│   │   ├── test_logging.py          # setup_logging/get_logger
│   │   ├── test_plugin_framework.py # Plugin, Registry, Manager
│   │   ├── test_log_analyzer.py     # Log Analyzer plugin
│   │   ├── test_report_engine.py    # JSON/TXT/HTML
│   │   └── test_history_and_hash_plugin.py
│   └── integration/
│       └── test_ui_api.py           # UI + PluginManager via servidor
│
├── docs/
│   ├── ARCHITECTURE.md              # Este documento (v1.0.0)
│   ├── API_STABILITY.md            # Contrato da API pública
│   ├── THREAT_MODEL.md              # Modelo de ameaças formal
│   ├── QA_REPORT.md                 # 17 achados (ARES-QA-001..029)
│   └── adr/
│       ├── ADR-006.md               # Core em camadas
│       ├── ADR-007.md               # CLI argparse
│       └── ADR-008.md               # Config Settings + env EDY_*
│
├── .github/workflows/ci.yml         # CI GitHub Actions
├── pyproject.toml                    # Build PED 621 (setuptools)
├── requirements-dev.txt              # pytest, pytest-cov, mypy, ruff
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE                           # MIT
├── README.md                         # Completo com badges e roadmap
└── EDY_SHIELD_COMPLETO.md            # ← ESTE ARQUIVO
```

---

## 3. ARQUITETURA

### 3.1 Arquitetura em Camadas

```mermaid
flowchart LR
    subgraph UI
        CLI[CLI argparse — edyshield] --- WEB[UI HTML + API REST Interna]
    end
    
    subgraph Services
        File[file_utils — shim de paths]
        Engine[report_engine — JSON/TXT/HTML]
        History[history — persistência]
    end
    
    subgraph Core
        ALG[algorithms — API pública Hash Checker]
        CRYPTO[crypto — whitelist + safe_compare]
        FS[filesystem — safe_path validation]
        VALID[validators — input]
        EXC[exceptions — domain]
        CONF[config — Settings + env EDY_*]
        LOG[logging — centralizado]
        MOD[models — HashResult, HashSource]
    end
    
    subgraph Plugins
        PM[PluginManager]
        REG[PluginRegistry]
        LA[LogAnalyzer plugin]
        HC[HashChecker plugin]
    end
    
    UI --> Services
    Services --> Core
    UI --> Plugins --> Core
    
    Core --> STD[Python Stdlib]
```

### 3.2 Regras Arquiteturais:
- **Direção única:** `ui → services → core` — nunca inversa
- **Core puro:** 100% stdlib, zero dependências de terceiros
- **Plugins como citizen:** Expostos via PluginManager, mesma interface que Core
- **Pathexpand única:** `resolve_safe_path()` no `core/filesystem/safe_path.py`
- **Erros de domínio:** Hierarquia `EDYShieldError` → `HashError/ValidationError/FilesystemError` → `PluginError`

---

## 4. SPRINTS E STATUS

### Sprint 1 (v0.1.0 base) — ✅ COMPLETA
- Módulo Hash Checker (hash_checker.py)
- Cli básico (texto/binary → hash)
- HTML dark estático
- 24 testes unitários
- Cobertura 95%+
- 17 achados ARES-QA
- 2 achados HIGH (path traversal + fallback silent)
- Fix em Sprint 2

### Sprint 2 (v0.1.0 foundation) — ✅ COMPLETA
- Core em camadas por responsabilidade
- CLI real (argparse com subcomandos)
- Config Settings (frozen + EDY_*)
- Logging centralizado
- Path safety no Core
- **105 testes passando, 99.04% coverage, mypy strict 0 issues**
- Exit code entries resolvidos
- CI GitHub Actions completo

### Sprint 3 (v1.0 full platform) — ✅ COMPLETA
- **Plugin Framework** (contracts, registry, manager, errors)
- **Log Analyzer** (first official plugin → 254 loc)
- **Report Engine** (JSON/TXT/HTML encoding)
- **History Store** (persistência em disco)
- **UI Server** (HTTP server + REST API com ThreadingHTTPServer)
- **Hash Checker como Plugin** 
- **196+ testes passando, 93.6% cobertura restante**

### Sprint 4 (v1.1 robustness) — 🔴 PENDENTE
- ADR-001..005 documentados
- ARES-QA-027: THREAT_MODEL/SECURITY atualizados
- ARES-QA-029: Exit codes do verify (0/1/2) 
- Pinagem de dev deps (lockfile)

### Sprint 5 (v2.0) — 🔴 PENDENTE
- File Integrity Monitor
- String Analyzer / Entropy detector
- Dashboard Streamlit / UI rica
- Relatórios exportáveis (Markdown)
- Plugins externos (documentação)

---

## 5. CÓDIGO FONTE PRINCIPAL

### 5.1 Core — Hash Checker (`app/core/algorithms/hash_checker.py`)

```python
from pathlib import Path
from app.core.crypto import HashAlgorithm, new_hasher, normalize_algorithm, safe_compare
from app.core.filesystem import ensure_regular_file, resolve_safe_path
from app.core.models.hashes import HashResult
from app.core.validators import validate_chunk_size, validate_expected

DEFAULT_CHUNK_SIZE: int = 65536

__all__ = [
    "DEFAULT_CHUNK_SIZE", "HashAlgorithm", "compute", "compute_bytes",
    "compute_file", "compute_text", "supported_algorithms", "verify_file",
]

def compute_bytes(data: bytes, algorithm: HashAlgorithm | str) -> str:
    """Compute hex digest of raw bytes (whitelist + hashlib.new with validate)."""
    member = normalize_algorithm(algorithm)
    hasher = new_hasher(member)
    hasher.update(data)
    return hasher.hexdigest()

def compute_text(text: str, algorithm: HashAlgorithm | str, encoding: str = "utf-8") -> str:
    """Encode text before hash."""
    member = normalize_algorithm(algorithm)
    digest, _ = _compute_text_with_size(text, member, encoding)
    return digest

def compute_file(path: Path | str, algorithm: HashAlgorithm | str, chunk_size: int = DEFAULT_CHUNK_SIZE, *, allowed_root: Path | None = None) -> str:
    """Hash file in chunks — never loads full file"""
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)
    digest, _ = _compute_file_impl(path, member, chunk_size, allowed_root)
    return digest

def compute(source: Path | str | bytes, algorithm: HashAlgorithm | str, *, encoding: str = "utf-8", chunk_size: int = DEFAULT_CHUNK_SIZE, allowed_root: Path | None = None) -> HashResult:
    """Dispatcher: bytes → compute_bytes, Path → file hash, str → text/path (heuristic _looks_like_path())"""
    member = normalize_algorithm(algorithm)

    if isinstance(source, bytes):
        hexdigest = compute_bytes(source, member)
        return HashResult(algorithm=member.name, hexdigest=hexdigest, source="bytes", size_bytes=len(source))

    if isinstance(source, Path):
        path = source
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path.name}")
    elif isinstance(source, str):
        if _looks_like_path(source):  # contains / or \ or has file extension
            path = Path(source)
            if not path.exists():
                raise FileNotFoundError(f"File not found: {path.name}")
        else:
            hexdigest, size_bytes = _compute_text_with_size(source, member, encoding)
            return HashResult(algorithm=member.name, hexdigest=hexdigest, source="text", size_bytes=size_bytes)
    else:
        raise TypeError(f"source must be str, bytes or Path, got {type(source).__name__}.")

    validate_chunk_size(chunk_size)
    hexdigest, size_bytes = _compute_file_impl(path, member, chunk_size, allowed_root)
    return HashResult(algorithm=member.name, hexdigest=hexdigest, source="file", path=path.resolve(), size_bytes=size_bytes)

def verify_file(path: Path | str, expected: str, algorithm: HashAlgorithm | str, *, chunk_size: int = DEFAULT_CHUNK_SIZE, allowed_root: Path | None = None) -> bool:
    """Verify file matches expected hash (case-insensitive, constant-time via hmac.compare_digest)."""
    member = normalize_algorithm(algorithm)
    validate_chunk_size(chunk_size)
    expected_digest = validate_expected(expected, member)
    actual = compute_file(path, member, chunk_size=chunk_size, allowed_root=allowed_root)
    return safe_compare(actual, expected_digest)

def supported_algorithms() -> list[str]:
    """List supported algorithm names."""
    return [member.name for member in HashAlgorithm]  # ["SHA256", "SHA1", "MD5"]
```

### 5.2 Core — Crypto (`app/core/crypto/hashing.py`)

```python
import hashlib, hmac, warnings
from enum import Enum
from app.core.exceptions import UnsupportedAlgorithmError

class HashAlgorithm(Enum):
    """Whitelist algorithm"""
    SHA256 = "SHA256"
    SHA1   = "SHA1"
    MD5    = "MD5"

_WEAK_ALGORITHMS: frozenset[str] = frozenset({"SHA1", "MD5"})

class _Hasher(Protocol):
    def update(self, data: bytes, /) -> None: ...
    def hexdigest(self) -> str: ...

def new_hasher(member: HashAlgorithm) -> _Hasher:
    """Create hashlib for validated algorithm. Emits DeprecationWarning for weak algos (ARES-QA-004)."""
    if member.name in _WEAK_ALGORITHMS:
        warnings.warn(f"{member.name} is cryptographically broken for collision resistance; use SHA256.",
                     DeprecationWarning, stacklevel=2)
    return hashlib.new(member.name.lower())

def safe_compare(actual: str, expected: str) -> bool:
    """Constant-time comparison via hmac.compare_digest (ARES-QA-003)."""
    return hmac.compare_digest(actual, expected)

def normalize_algorithm(algorithm: HashAlgorithm | str) -> HashAlgorithm:
    """Normalize to whitelisted HashAlgorithm; rejects everything else."""
    if isinstance(algorithm, HashAlgorithm):
        return algorithm
    if not isinstance(algorithm, str):
        raise UnsupportedAlgorithmError(f"algorithm must be HashAlgorithm or str, got {type(algorithm).__name__}",
                                        algorithm=repr(algorithm))
    normalized = algorithm.strip().upper().replace("-", "").replace("_", "")
    try:
        algo = HashAlgorithm[normalized]
    except KeyError:
        supported = ", ".join(m.name for m in HashAlgorithm)
        raise UnsupportedAlgorithmError(f"Unsupported hash algorithm: {algorithm!r}. Supported: {supported}.",
                                        algorithm=algorithm) from None
    return algo
```

### 5.3 Segurança de Paths (`app/core/filesystem/safe_path.py`)

```python
from pathlib import Path
from app.core.exceptions import HashError

def validate_allowed_root(root: Path | None) -> Path:
    """Validate external root values. If None, use current working directory."""
    if root is not None and not isinstance(root, Path):
        raise TypeError(f"allowed_root must be a Path or None, got {type(root).__name__}.")
    return (root if root is not None else Path.cwd()).resolve()

def is_within_root(resolved: Path, root: Path) -> bool:
    """Test if path is inside root (or equals it). Returns False when outside."""
    try:
        resolved.relative_to(root)
        return True
    except ValueError:
        return False

def resolve_safe_path(path: Path | str, *, allowed_root: Path | None = None, strict: bool = True) -> Path:
    """Resolve and validate path containment. Blocks .. traversal, absolutes outside root, symlink escape."""
    root = validate_allowed_root(allowed_root) if allowed_root is not None else Path.cwd()
    resolved = Path(path).resolve()
    
    if not is_within_root(resolved, root):
        raise HashError("access denied: path outside allowed directory")
    
    if strict and not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved.name}")
    
    return resolved

def ensure_regular_file(target: Path) -> None:
    """Reject directory and non-regular special files (FIFO/device/socket) — ARES-QA-007."""
    if target.is_dir():
        raise IsADirectoryError(f"Cannot hash a directory: {target.name}")
    if not target.is_file():
        raise HashError(f"Cannot hash non-regular file: {target.name}")
```

### 5.4 CLI (`app/cli/hash_cmd.py`)

**Entryptoint:** `edyshield` via `pyproject.toml → app.cli.hash_cmd:main`

```python
import argparse, sys
from app import __version__
from app.core.algorithms import compute, verify_file
from app.core.config import Settings, load_settings
from app.core.exceptions import EDYShieldError
from app.core.logging import get_logger, setup_logging

logger = get_logger("cli.hash_cmd")

def main(argv: list[str] | None = None) -> int:
    try:
        settings = load_settings()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    setup_logging(settings)
    
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    
    algorithm = args.algorithm or settings.default_hash_algorithm
    root = _resolve_root(args.source, Path(args.root) if args.root else settings.allowed_root)
    
    try:
        if args.command == "hash":
            return _cmd_hash(args.source, algorithm, root, settings)
        if args.command == "check":
            return _cmd_check(args.source, args.expected, algorithm, root, settings)
    except EDYShieldError as exc:
        logger.error("%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (FileNotFoundError, IsADirectoryError, ValueError, TypeError) as exc:
        logger.error("%s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1
    
    return 1
```

---

## 6. PLUGINS E FRAMEWORK

### 6.1 Contratos (Contracts)

```python
class Severity(Enum):
    INFO, LOW, MEDIUM, HIGH, CRITICAL

@dataclass(frozen=True, slots=True)
class Evidence:
    severity: Severity
    message: str
    source: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True, slots=True)
class ScanContext:
    target: str | Path | None = None
    options: dict[str, Any] = field(default_factory=dict)
    allowed_root: Path | None = None

@dataclass(frozen=True, slots=True)
class ScanResult:
    plugin_name: str
    plugin_version: str
    timestamp: datetime
    summary: str
    findings: tuple[Evidence, ...] = ()
    stats: dict[str, int] = field(default_factory=dict)
    observations: tuple[str, ...] = ()
    
    def max_severity(self) -> Severity: ...
    def as_dict(self) -> dict: ...
    @classmethod def from_dict(cls, data: dict) -> ScanResult: ...
```

### 6.2 Plugin Interface

```python
class Plugin(ABC):
    """Base class for all plugins"""
    name: str
    version: str
    description: str
    author: str
    
    @abstractmethod
    def validate(self, context: ScanContext) -> None: ...
    
    @abstractmethod
    def execute(self, context: ScanContext) -> ScanResult: ...
    
    @abstractmethod
    def health_check(self) -> bool: ...
```

### 6.3 Plugin Manager

```python
class PluginManager:
    """Ponto único de execução: validate → health_check → execute → fallback errors"""
    
    def register(self, plugin: Plugin) -> None
    def run(self, plugin_name: str, context: ScanContext) -> ScanResult
    def run_all(self, context: ScanContext) -> list[ScanResult]
```

### 6.4 Log Analyzer Plugin (`app/plugins/builtin/log_analyzer.py`)

5 patterns detectados:
- `FAILED LOGIN` — HIGH (Force Brute?)
- `SUCCESS LOGIN` — LOW
- `ERROR` — MEDIUM
- `WARNING` — LOW
- `CRITICAL` — CRITICAL

Features:
- Extracts timestamps (ISO 8601) for time-window detection
- Accumulates stats per category
- Supports encoding, max_lines, fs safe path (parent → offspring containment)
- Reuses Core's `resolve_safe_path()` for path validation

### 6.5 Report Engine (`app/services/report_engine.py`)

```python
def to_json(result: ScanResult, *, pretty: bool = True) -> str:
    """Serialization to JSON with UTC timestamps."""

def to_txt(result: ScanResult) -> str:
    """Human-readable '═' formatted text."""
    # Header → Summary → ### Stats → ### Findings → Observations

def to_html(result: ScanResult) -> str:
    """Dark-theme standalone HTML with escape.(html.escape) for anti-injection."""

def render(result: ScanResult, fmt: str) -> str:
    """Dispatcher: fmt = json | txt | html → raise on unknown."""
```

### 6.6 History Store (`app/services/history.py`)

```python
class HistoryStore:
    """JSON persistence in <base_dir>/<scan_id>.json"""
    def __init__(self, base_dir: Path) -> None: ...
    def save(self, result: ScanResult) -> str: ...
    def list(self) -> list[dict[str, object]]: ...
    def get(self, scan_id: str) -> ScanResult | None: ...
    def clear(self) -> int: ...
```

### 6.7 Hash Checker as Plugin (`app/plugins/builtin/hash_checker_plugin.py`)

- Wraps Core `compute()` + `verify_file()` as Plugin interface
- Validation via PluginManager, like any other plugin
- Comparison mark: Evidence(severity=INFO if match else HIGH) — named "Verificação de integridade: MATCH/MISMATCH"

### 6.8 UI Server (`app/ui/server.py`)

Pure stdlib ThreadingHTTPServer with REST API:

| Endpoint | Method | Description |
|----------|--------|-------------|
| GET `/` | Dashboard | index.html |
| GET `/css/style.css` | Static | Stylesheet |
| GET `/app.js` | Static | JS logic |
| GET `/api/plugins` | API | List registered plugins + version |
| POST `/api/scan` | API | Run plugin (JSON body: plugin, target, options) → returns scan ID + result |
| GET `/api/history` | API | List saved scans |
| GET `/api/history/{id}` | API | Get ScanResult by ID |
| GET `/api/report/{id}?fmt=json|txt|html` | Export | Generate report from saved scan |

---

## 7. TESTES

### 7.1 Estrutura
```
tests/
├── conftest.py                                          # Shared fixtures
├── unit/
│   ├── test_hash_checker.py                             # 48+ tests
│   ├── test_file_utils.py                                # 15 tests
│   ├── test_core_layers.py                               # 15 tests
│   ├── test_cli.py                                       # CLI tests
│   ├── test_config.py                                    # Settings + env
│   ├── test_logging.py                                   # Logger
│   ├── test_plugin_framework.py                          # Plugin, Manager, Registry
│   ├── test_log_analyzer.py                              # Plugin tests
│   ├── test_report_engine.py                             # JSON/TXT/HTML
│   └── test_history_and_hash_plugin.py                   # History + Hash plugin
└── integration/
    └── test_ui_api.py                                # Server + HTTP API tests
```

### 7.2 Cobertura
- Target: 90% (pytest-cov)
- Actual: 93.6% (196+ tests passed)
- mypy strict: 0 issues

### 7.3 CI Pipeline (.github/workflows/ci.yml)

```yaml
name: ci
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: python-version: "3.12"
      - run: pip install -e ".[dev]"
      - run: pytest                          # pytest with coverage
      - run: mypy app                        # strict mode
      - run: ruff check .                    # lint
      - run: ruff format --check .           # format
```

---

## 8. QUALITY GATES & SEGURANÇA

### 8.1 Quality Gate Status (GENERAL)

| Gate | Status | Note |
|------|--------|------|
| QG-NOVA | ✅ Pass | Fontes verificadas (MLA), dados < 12 meses |
| QG-ATLAS | ✅ Pass | ADRs 006–008 documentados, arquitetura em camadas, riscos mapeados |
| QG-ARES | ✅ Pass | 0 Critical, 0 High, 0 Medium (Sprint 3 finalizado) |
| QG-VULCAN | ✅ Pass | mypy strict 0, ruff clean, coverage 93.6% (gate 90%) |
| QG-ORION | ✅ Pass | Dark theme consistente, registrables, sem vazamento de layout |
| QG-PROOF | ✅ Pass | 100% UTF-8 sem BOM, zero U+FFFD, zero mojibake, acentos corretos |
| QG-LUMINA | N/A | No animated UI in this version |

### 8.2 Segurança Específica

| Ameaça | Controle | Status |
|--------|---------|--------|
| **Path traversal** (ARES-QA-001) | `resolve_safe_path()` + containment | ✅ Bloqueado |
| **SYMLINK escape outside root** | `Path.resolve()` pre ≥ relative_to | ✅ Coberto |
| **Arquivo especial (FIFO/device) DoS** | `ensure_regular_file()` | ✅ Pre-rejeição |
| **MD5/SHA1 colisão** | `DeprecationWarning` + SHA256 padrão | ✅ Semi-mitigado |
| **Timing attack (CWE-208)** | `hmac.compare_symetric` | ✅ |
| **Injeção de algoritmo** | Whitelist + `normalize_algorithm` | ✅ |
| **Fallback str → text** | `_looks_like_path()` + `FileNotFoundError` | ✅ |
| **Vazamento de info em errors** | `target.name` (nunca absoluto) | ✅ |
| **Supply chain (runtime)** | Zero runtime deps (stdlib) | ✅ |
| **Supply chain (dev)** | não pinado | ⚠️ AMBULANTE |

### 8.3 Checklist de QA (quality report)

- Path traversal mitigado → ✅
- hmac.compare_digest em todo lugar → ✅
- SHA-256 como padrão (nunca MD5/SHA1 em default) → ✅
- Erros sanitizados (sem path absoluto) → ✅
- Testes de segurança (20+ negative tests) → ✅
- CI com coverage gate ativado → ✅

---

## 9. DECISÕES DE ARQUITETURA (ADRs)

### ADRs documentados:

| ADR | Decisão | Status |
|-----|---------|--------|
| ADR-001 | Core 100% stdlib (req) — segurança-first | ⚠️ Sem documento (apenas referência) |
| ADR-002 | Camadas unidirecionais | ⚠️ Sem documento |
| ADR-003 | HTML v1 vs Streamlit v2 | ⚠️ Sem documento |
| ADR-004 | CLI argparse v1 vs Typer v2 (evolução) → consolidado em ADR-007 | ⚠️ Sem documento |
| ADR-005 | Erros de domínio customizados | ⚠️ Sem documento |
| **ADR-006** | **Core em camadas** ← dataset, crypto, validators, filesystem, etc. | ✅ DOCUMENTADO |
| **ADR-007** | **CLI argparse (stdlib) + exit codes 0/1** | ✅ DOCUMENTADO |
| **ADR-008** | **Settings frozen + env EDY_* (sem arquivo de config)** | ✅ DOCUMENTADO |

### Pendência:
- ADR-001..005: referenciados no código porém sem documentos individuais no `docs/adr/`. Criar em Sprint 4.

---

## 10. PENDÊNCIAS & ROADMAP

### 🔴 Sprint 4 — Fixes necessários

| ID | Description | Severity | Status |
|----|-------------|----------|--------|
| ARES-QA-027 | Docs (THREAT_MODEL/SECURITY) citam "default root = cwd" mas CLI usa parent-of-file | ⚪ Info | Pendente |
| ARES-QA-029 | Exit codes ambíguos no verify (FAIL e erro ambos retornam 1) → mudar para 0/1/2 | ⚪ Info | Pendente |
| ADR-001..005 | Criar documentos oficiais | ⚪ Info | Pendente |
| ARES-QA-019/020 | Redundância TOCTOU + root 'is_dir()' validation | 🟡 Low | Pendente |
| ARES-QA-022 | Pinagem de dev deps (dev dependencies sem pinning) | 🟡 Low | Pendente |
| ~git init | Inicializar (ainda não iniciado) | ⚪ Info | Pendente |

### Roadmap Sprint 4+:

1. **Sprint 4 (v1.1):** TODOs acima + TOCTOU hardening para service layer + pin de dev
2. **Sprint 5 (v1.2):** Batch checksum (.sha256sum format), export Streamlit dashboard
3. **Sprint 6 (v2.0):** File Integrity Monitor, String Assessor, plugin externo
4. **Sprint 7 (v3.0):** Console + API REST com autenticação + agent mode (service)

---


## TRANSIÇÃO DE CONTEXTO PARA OUTRA LLM

### Como usar este documento:

1. **Leia 완전: prosseguir por seções (1–10).**
2. **Execute testes rapido:** `pytest tests -q --cov=app --cov-report=term-missing`
3. **Métricas na interface:** `mypy app` → 100% strict 0 issues → perfect
4. **Decisões críticas:** Nunca quebre `resolve_safe_path()` — batch (API pública impossível matar)
5. **Não introduza dependências no Core** — a regra super-rpincipal é ADR-001
6. **Todo novo código deve passar CI completo + QG-ARES** (security review)

### Ambiência:

- **Python ≥ 3.12** obrigatório (uso de features 3.12 como `type` in `dataclass`, `Literal`, `@override` opcional)
- Nunca instale com `pip install [sem be -e .]`
- Dev env: `pip install -e ".[dev]"`
- Para CLI tests: `edyshield --help`
- Para UI: `python -c "from app.ui.server import build_default_manager; print(build_default_manager().list_plugins())"`

---

> **EDY SHIELD — Defenda. Verifique. Confie.** 🛡️
> Documento gerado por jr (CyberShield AI, CEO do TITAN AI SQUAD) 
> Para: Análise de outra LLM | 01/08/2026