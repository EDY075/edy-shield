# 🚀 EDY Shield v1.2.0 — Release Notes

> **Defenda. Verifique. Confie.** 🛡️
> Sprint 4 · 02/08/2026 · Batch Hashing + Checksum Files + CLI integrada + Testes E2E

---

## 📦 O que há de novo

### 1. Batch Hashing

Calcule hashes de vários arquivos em uma única execução, sem duplicar lógica.

```bash
# Diretório inteiro (nível superior)
edyshield hash --batch ./backup

# Diretório com subdiretórios
edyshield hash --batch ./projeto --recursive

# Saída (stdout): digest + 2 espaços + caminho
# a94f8b1c...  backup/config.ini
# 2cf24dba...  backup/dados.txt
```

- Reutiliza `compute_file()` do Core — zero duplicação.
- Erro em um arquivo **não interrompe** o lote.
- Ordenação determinística por caminho.
- Ignora diretórios durante a varredura.
- Respeita a fronteira de paths (`allowed_root`).

### 2. Checksum Files

Crie e verifique arquivos de checksum compatíveis com os formatos conhecidos.

```bash
# Criar arquivo de checksum
edyshield checksum create ./backup
# → gera ./backup/SHA256SUMS

# Criar com algoritmo específico e recursivo
edyshield checksum create ./backup --algorithm MD5 --recursive --output ./md5sums.md5

# Verificar
edyshield checksum verify ./backup/SHA256SUMS
# ok       config.ini
# ok       dados.txt
```

- Formatos suportados: `.sha256`, `.sha256sum`, `.sha1`, `.md5`, `.md5sum`.
- Parser BSD (`digest  file`) e GNU (`digest *file`).
- Suporta linhas vazias e comentários (`#`).
- Rejeita linhas malformadas e **bloqueia path traversal**.
- Detecção automática do algoritmo pelo comprimento do digest.
- Saída identifica: `ok` / `mismatch` / `missing` / `invalid`.

### 3. Comandos da CLI

| Comando | Descrição | Exit codes |
|---------|-----------|------------|
| `edyshield hash --batch <dir> [--recursive]` | Batch de diretório | 0 / 2 |
| `edyshield checksum create <dir>` | Cria arquivo de checksum | 0 / 2 |
| `edyshield checksum verify <file>` | Verifica checksum | 0 / 1 / 2 |

Exit codes (ARES-QA-029): `0` sucesso total · `1` mismatch · `2` erro de uso/domínio/leitura.

- Resultados (digests) no **stdout**; erros e resumo no **stderr**.
- Comandos `hash` e `verify` existentes **100% preservados**.

### 4. Testes E2E

A CLI agora é testada **exatamente como o usuário executa no terminal** —
via subprocess com validação de stdout, stderr e exit code.

---

## 🛠️ APIs novas (Core)

| Símbolo | Pacote | Descrição |
|---------|--------|-----------|
| `hash_files(paths, algorithm)` | `app.core.algorithms.batch` | Lista de arquivos |
| `hash_directory(dir, algorithm, *, recursive)` | `app.core.algorithms.batch` | Diretório (opcional recursivo) |
| `create_checksum_file(...)` | `app.core.checksums` | Gera arquivo de checksum |
| `parse_checksum_file(path)` | `app.core.checksums` | Parse determinístico |
| `verify_checksum_file(path, ...)` | `app.core.checksums` | Verifica com report |

---

## ✅ Qualidade

| Métrica | v1.1.0 | v1.2.0 |
|---------|--------|--------|
| Testes | 196 passed | **248 passed, 2 skipped** |
| Cobertura | 92.90% | **90.29%** (gate 90%) |
| mypy strict | 0 issues | **0 issues (42 arquivos)** |
| ruff | limpo | **limpo (71 arquivos)** |
| CI | verde | **verde (runs #10, #11, #12)** |

> A cobertura caiu ligeiramente porque a nova CLI de integração (subprocess)
> adiciona linhas de lógica de apresentação; o gate de 90% é mantido e os
> novos módulos do Core têm cobertura unitária dedicada.

---

## 🔒 Segurança

- **Core 100% stdlib** (ADR-001) — zero dependências externas adicionadas.
- **Anti path traversal** em checksum files via `resolve_safe_path`.
- **Comparação em tempo constante** (`hmac.compare_digest`) para verificação.
- Fronteira única de paths preservada (`allowed_root` derivado, ARES-QA-028).

---

## 📁 Arquivos principais alterados/criados

| Arquivo | Ação |
|---------|------|
| `app/core/algorithms/batch.py` | 🆕 Batch Hashing |
| `app/core/checksums/checksum.py` | 🆕 Checksum Files |
| `app/core/checksums/__init__.py` | 🆕 API pública |
| `app/cli/hash_cmd.py` | ✏️ Integração CLI |
| `app/core/filesystem/opener.py` | 🆕 Helper TOCTOU |
| `tests/unit/test_batch.py` | 🆕 11 testes |
| `tests/unit/test_checksums.py` | 🆕 17 testes |
| `tests/unit/test_cli_v12.py` | 🆕 11 testes |
| `tests/e2e/test_cli_e2e.py` | 🆕 13 testes E2E |
| `MANIFESTO.md` | 🆕 Manifesto oficial |
| `CHANGELOG.md` | ✏️ Seção 1.2.0 |

---

## 🗺️ Próximos passos (v2.0)

- **File Integrity Monitor (FIM)** — principal diferencial técnico (baseline
  + detecção de mudanças). Especificação em `docs/FIM_ARCHITECTURE.md`.
- String Analyzer / Entropy.
- Report Markdown.
- Decorator de registro de plugins.

---

## 🏷️ Status

**v1.2.0 — Release Ready** ✅

---

*EDY Shield — Defenda. Verifique. Confie.* 🛡️