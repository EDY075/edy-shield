# Changelog

Todas as mudanças notáveis do **EDY Shield** serão documentadas neste arquivo.

O formato segue [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/), e o versionamento
segue [Semantic Versioning](https://semver.org/lang/pt-BR/).

---

## [0.1.0] — 2026-08-01

### Sprint 2 — Fundação técnica (Core em camadas, CLI real, config & logging)

Primeira release da fundação técnica. Esta versão consolida a **Sprint 2**: o core foi
refatorado em camadas por responsabilidade, a CLI real (`edyshield`) foi implementada com
`argparse` (stdlib), a configuração passou a ser uma `dataclass` congelada carregada de
variáveis de ambiente `EDY_*`, o logging foi centralizado, a hierarquia de exceções de domínio
foi criada e a fronteira de segurança de paths migrou para o Core.

#### Added

- **Core em camadas por responsabilidade** (`app/core/{config,crypto,exceptions,filesystem,logging,report,validators,utils}`):
  - `app/core/crypto/hashing.py` — fonte canônica de `HashAlgorithm`, `normalize_algorithm`,
    `new_hasher` e `safe_compare` (whitelist de algoritmos + `hmac.compare_digest`).
  - `app/core/exceptions/domain.py` — hierarquia `EDYShieldError` → `HashError`,
    `ValidationError`, `FilesystemError`; `HashError` → `UnsupportedAlgorithmError` (ADR-005).
  - `app/core/filesystem/safe_path.py` — fronteira única de paths: `resolve_safe_path`,
    `validate_allowed_root`, `is_within_root`, `ensure_regular_file` (migrado de
    `app/services/file_utils`).
  - `app/core/validators/input.py` — `validate_chunk_size` e `validate_expected`.
  - `app/core/config/settings.py` — `Settings` (dataclass frozen + slots) e `load_settings()`
    com variáveis de ambiente `EDY_*` (Missão 3).
  - `app/core/logging/logger.py` — `setup_logging` (idempotente) e `get_logger`; logger raiz
    `edy_shield` com saída em `stderr` (Missão 3).
  - `app/core/report/` e `app/core/utils/` — estrutura reservada (sem código; roadmap v2.0).
- **CLI real com argparse (stdlib)** — `app/cli/hash_cmd.py` com subcomandos `hash` e `verify`,
  `--help`, `--version` e entrypoint `edyshield` instalável via `pip install -e .`
  (ARES-QA-021 resolvido). Exit codes: `0` sucesso, `1` erro de domínio/validação. Logging em
  `stderr`; resultado (digest/OK/FAIL) em `stdout`.
- **Configuração via ambiente** — `EDY_DEFAULT_HASH_ALGORITHM`, `EDY_LOG_LEVEL`,
  `EDY_ALLOWED_ROOT`, `EDY_CHUNK_SIZE`, `EDY_TEXT_ENCODING`.
- **Shims de compatibilidade** — `app/core/models/common.py` e `app/services/file_utils.py`
  re-exportam símbolos canônicos para preservar a API pública existente.
- **Testes novos** — `tests/unit/test_cli.py`, `test_config.py`, `test_logging.py`,
  `test_core_layers.py` (CLI, configuração, logging e camadas do core).

#### Changed

- **Refatoração em camadas (Missões 1–2)** — a lógica de hash/path/validação foi movida de
  `app/core/algorithms/hash_checker.py` para módulos especializados do Core; o `hash_checker`
  agora **delega** para `crypto`, `filesystem`, `validators` e `exceptions`.
- **`app/services/file_utils.py`** tornou-se um shim re-export da fronteira de paths (agora no
  Core).
- **CLI documentado como `argparse`** — decisão ADR-007 (zero deps runtime); Typer permanece
  como evolução futura opcional.
- **`app/core/models/common.py`** re-exporta erros da fonte canônica
  `app.core.exceptions.domain`.

#### Fixed

- **ARES-QA-021** — entrypoint `edyshield` agora existe e funciona via `pip install -e .`
  (era pendência bloqueante da v1.0).
- **Divergência de documentação** — `ARCHITECTURE.md` e `README.md` atualizados para refletir a
  estrutura real do Core em camadas e a CLI real.

#### Security

- **Fronteira única de paths no Core** (ARES-QA-001/005/007) — `resolve_safe_path` resolve
  symlinks, rejeita `..`/absolutos fora da raiz com `HashError` e mensagens sem vazamento de
  path; `ensure_regular_file` rejeita diretórios e arquivos especiais (FIFO/device/socket).
- **Sem fallback silencioso `str` → texto** (ARES-QA-002) — string com cara de path inexistente
  levanta `FileNotFoundError`.
- **Comparação em tempo constante** (ARES-QA-003) — `hmac.compare_digest` via `safe_compare`.
- **`DeprecationWarning` para MD5/SHA1** (ARES-QA-004) — algoritmo padrão é SHA-256.
- **Logging seguro** — política de nunca logar conteúdo de arquivo (apenas hashes e metadados)
  e nunca logar segredos.

#### Quality

- **Suíte de testes:** 101 passed, 2 skipped (symlink em Windows), 7 warnings esperados
  (DeprecationWarning MD5/SHA1).
- **Cobertura:** 99.34% (301 stmts, 2 sem cobertura em `app/cli/hash_cmd.py` — `return 1`
  final e guard `__main__`; gate 90%).
- **mypy strict:** 0 issues em 25 arquivos.
- **ruff check:** limpo; **ruff format:** 36 arquivos OK.
- **CI (GitHub Actions):** pytest → mypy app → ruff check → ruff format --check.

#### Pendências registradas para v1.1 (não bloqueantes desta release)

- TOCTOU hardening na camada de serviço (ARES-QA-008/R1): `os.open` + `O_NOFOLLOW` + `fstat`.
- Pinning/lockfile de dev deps (ARES-QA-022).
- Validação de root como diretório em `validate_allowed_root` (ARES-QA-020).
- Remoção da checagem `exists()` duplicada em `compute` (ARES-QA-019).
- Testes de integração E2E via CLI.
- Batch e checksum files (`.sha256sum`/`.md5sum`) — roadmap, não implementados.

---

## [1.1.0] — 2026-08-01

### Sprint 3 — Robustez e fechamento (stabilização da v1.1)

Release de **estabilização completa** da v1.1. Fecha todas as pendências de segurança e
robustez identificadas nas revisões ARES (ARES-QA-008, 019, 020, 022, 027, 029), materializa
os ADRs 001–005 e prepara a fundação para a v2.0 (plataforma de ferramentas com plugins).

#### Added

- **ADR-001..005 materializados** em `docs/adr/` — Core 100% stdlib, camadas unidirecionais,
  UI HTML → Streamlit (v2), CLI argparse (v1), erros de domínio customizados.
- **`docs/context/` — JR Memory Engine v1.0** — índice mestre (`JR_MEMORY.md`) + estado do
  projeto, task ledger, sessão, arquitetura e política de contexto incremental (economia de
  ~40% de tokens por sessão).

#### Changed

- **Exit codes da CLI** (ARES-QA-029) — contrato definitivo:
  - `0` = sucesso (hash calculado / verificação MATCH)
  - `1` = verificação MISMATCH (apenas `verify`)
  - `2` = erro de domínio / validação / exceção inesperada
  - `--help` / `--version` = `0` (SystemExit do argparse)
  - `ADR-007` atualizado com o novo contrato.
- **Dev deps pinadas** (ARES-QA-022) — `pytest==9.1.1`, `pytest-cov==7.1.0`, `mypy==2.3.0`,
  `ruff==0.16.1` em `pyproject.toml` e `requirements-dev.txt`.
- **`pyproject.toml`** — `EDY_SHIELD_COMPLETO.md` excluído do escopo do ruff (artefato de
  transferência de contexto, não código).

#### Fixed

- **ARES-QA-019** — removida a checagem `exists()` redundante em `compute()` (o
  `resolve_safe_path(strict=True)` já valida existência; elimina janela TOCTOU duplicada).
- **ARES-QA-020** — `validate_allowed_root()` agora valida `is_dir()` (root inexistente ou
  não-diretório gera erro claro em vez de falha obscura em runtime).
- **ARES-QA-027** — `THREAT_MODEL.md` e `SECURITY.md` atualizados para a semântica real da
  CLI: root default = diretório pai do arquivo alvo (não CWD global).
- **Bug de import** — `HashError` não estava importado no `hash_checker.py` após o TOCTOU
  hardening (mypy strict detectou; corrigido).
- **Testes de CLI** — atualizados para o novo contrato de exit codes (erros de domínio = 2;
  MISMATCH = 1).

#### Security

- **TOCTOU hardening** (ARES-QA-008) — leitura de arquivos agora usa `os.open` com
  `O_NOFOLLOW` (onde disponível) + `os.fstat` no file descriptor após abrir, confirmando que
  o arquivo ainda é regular antes de qualquer dado ser hasheado. Fecha a janela de race entre
  validação de path e leitura.

#### Quality

- **Suíte de testes:** 196 passed, 2 skipped (symlink em Windows), 7 warnings esperados.
- **Cobertura:** 92.90% (887 stmts, 63 sem cobertura; gate 90%).
- **mypy strict:** 0 issues em 38 arquivos.
- **ruff check:** limpo; **ruff format:** 57 arquivos OK.
- **CI (GitHub Actions):** pytest → mypy app → ruff check → ruff format --check — todos verdes.

---

## [1.2.0] — 2026-08-02

### Sprint 4 — Batch Hashing, Checksum Files, CLI integrada e testes E2E

Release de **estabilização funcional** da v1.2. Adiciona processamento em lote
de hashes, criação/verificação de arquivos de checksum (formatos BSD/GNU),
integração completa na CLI e suíte de testes E2E que executa o comando real
via subprocess. Mantém o Core 100% stdlib (ADR-001) e as camadas
unidirecionais (ADR-002).

#### Added

- **Batch Hashing** (`app/core/algorithms/batch.py`):
  - `hash_files(paths, algorithm)` — lista explícita de arquivos, reutilizando
    `compute_file` (nenhuma duplicação de lógica de hash).
  - `hash_directory(directory, algorithm, *, recursive=False)` — varredura
    determinística de diretórios (nível superior ou recursiva), ignorando
    diretórios e arquivos especiais.
  - `BatchResult = (HashResult | None, Exception | None)` — erro em um arquivo
    não interrompe o lote.
  - Validação de algoritmo na entrada (whitelist do Core) e `allowed_root`
    derivado do diretório pai (ARES-QA-028).
- **Checksum Files** (`app/core/checksums/`):
  - `create_checksum_file(directory, output, ...)` — gera arquivos de checksum
    (`.sha256`, `.sha1`, `.md5`), reutilizando `hash_directory`; exclui o
    próprio arquivo de checksum da varredura.
  - `parse_checksum_file(path)` — parser determinístico dos formatos BSD e
    GNU (`digest  file` / `digest *file`), ignora linhas vazias e comentários,
    rejeita linhas malformadas com `ChecksumError`.
  - `verify_checksum_file(path, ...)` — verifica cada entrada e reporta
    `ok` / `mismatch` / `missing` / `invalid`; detecção de algoritmo pelo
    comprimento do digest (64/40/32 hex).
  - Anti path traversal via `resolve_safe_path` (raiz padrão = diretório do
    checksum); comparação em tempo constante (`safe_compare`, ARES-QA-003).
- **Integração CLI** (`app/cli/hash_cmd.py`):
  - `edyshield hash --batch <dir> [--recursive]` — digests no stdout, erros e
    resumo no stderr; exit 0 sucesso total, 2 com erros.
  - `edyshield checksum create <dir> [--algorithm] [--output] [--recursive]`.
  - `edyshield checksum verify <file>` — exit 0 tudo ok, 1 mismatch, 2 erro.
  - Comandos `hash` e `verify` existentes **preservados** (mesmo comportamento
    e exit codes ARES-QA-029).
- **Testes E2E** (`tests/e2e/test_cli_e2e.py`) — executa a CLI real via
  subprocess (`python -m app.cli.hash_cmd`), validando stdout, stderr e exit
  code; cobre version, help, hash, verify (mismatch exit 1), batch
  (recursivo/não), checksum create/verify e erro de uso (exit 2).
- **`MANIFESTO.md`** — manifesto oficial do projeto (missão, visão,
  princípios, público e compromisso).

#### Changed

- **`app/core/algorithms/__init__.py`** — API pública ampliada com
  `hash_files`, `hash_directory` e `BatchResult` (os 8 símbolos originais
  permanecem estáveis).
- **`app/core/filesystem/opener.py`** — novo helper `open_regular_file`
  (TOCTOU hardening centralizado, ARES-QA-008), preparado para reuso futuro.
- **Versão** — `app/__init__.py` e `pyproject.toml` sincronizados em `1.2.0`.

#### Fixed

- **CLI `checksum verify`** — acesso a `args.algorithm` para subparsers que
  não possuem o atributo (resolvido com `getattr`).

#### Security

- **Path traversal em checksum files** — filenames lidos do arquivo de
  checksum são validados por `resolve_safe_path`; `..`/absolutos fora da raiz
  viram entradas `invalid` (nunca lidos).
- **Comparação em tempo constante** mantida para verificação de digests
  (`hmac.compare_digest`).
- **Core 100% stdlib** preservado (ADR-001) — zero novas dependências runtime.

#### Quality

- **Suíte de testes:** 248 passed, 2 skipped (symlink em Windows).
- **Cobertura:** 90.29% (1164 stmts; gate 90%).
- **mypy strict:** 0 issues em 42 arquivos.
- **ruff check:** limpo; **ruff format:** 71 arquivos OK.
- **CI (GitHub Actions):** pytest → mypy app → ruff check → ruff format
  --check — todos verdes nos runs #10, #11, #12.

---

## [Unreleased]

- Nenhuma mudança pendente documentada.

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Changelog · Keep a Changelog · SemVer
