# 📦 EDY SHIELD — RELEASE SUMMARY v1.1.0

> **Status:** ✅ RELEASE READY
> **Data:** 01/08/2026
> **Tag:** `v1.1.0`
> **Branch sugerida:** `main`

---

## 1. Visão Geral da Release

| Campo | Valor |
|-------|-------|
| **Versão** | 1.1.0 |
| **Nome de código** | Sprint 3 — Estabilização |
| **Tipo** | Minor (sem breaking changes de API pública) |
| **Pacote** | `edy-shield` (PyPI-ready) |
| **Python** | ≥ 3.12 |
| **Core deps runtime** | 0 (100% stdlib — ADR-001) |

## 2. O que há de novo nesta release

### Segurança (foco principal)
- 🔒 **TOCTOU hardening** (ARES-QA-008): `os.open` + `O_NOFOLLOW` + `os.fstat` no file descriptor — fecha janela de race entre validação e leitura
- 🔒 **`validate_allowed_root` validado** (ARES-QA-020): root inexistente/não-diretório gera erro claro
- 🔒 **`exists()` redundante removido** (ARES-QA-019): elimina janela TOCTOU duplicada

### CLI
- 🔢 **Exit codes padronizados** (ARES-QA-029): `0` sucesso · `1` MISMATCH · `2` erro de domínio

### Documentação
- 📚 **ADR-001..005 materializados** — 8/8 ADRs completos
- 📚 **THREAT_MODEL.md + SECURITY.md** sincronizados com a semântica real da CLI
- 🧠 **JR Memory Engine v1.0** — `docs/context/` (economia ~40% de contexto)

### Qualidade
- 📌 **Dev deps pinadas** (ARES-QA-022): pytest 9.1.1, pytest-cov 7.1.0, mypy 2.3.0, ruff 0.16.1

## 3. Correções incluídas

| ID | Descrição | Sev |
|----|-----------|-----|
| ARES-QA-008 | TOCTOU hardening | 🔵 Medium |
| ARES-QA-019 | exists() redundante removido | 🔵 Low |
| ARES-QA-020 | validate_allowed_root valida is_dir() | 🔵 Low |
| ARES-QA-022 | Dev deps pinadas | 🔵 Low |
| ARES-QA-027 | Docs CLI semantics | ⚪ Info |
| ARES-QA-029 | Exit codes 0/1/2 | ⚪ Info |
| — | Bug import HashError (mypy) | 🔴 Fix |
| — | UI mostrava v0.1.0 (release fix) | ⚪ Info |

## 4. Quality Gates — Resultado Final

| Gate | Resultado |
|------|-----------|
| ✅ pytest | **196 passed, 2 skipped** |
| ✅ coverage | **92.90%** (gate ≥ 90%) |
| ✅ mypy strict | **0 issues** (38 arquivos) |
| ✅ ruff check | All checks passed |
| ✅ ruff format | 57 files already formatted |
| ✅ CI (GitHub Actions) | pipeline verde |
| ✅ CLI version | `edyshield 1.1.0` |

## 5. Arquivos alterados nesta release

```
Código:
  app/__init__.py                    → __version__ = "1.1.0"
  pyproject.toml                     → version = "1.1.0" + ruff exclude + dev deps pinadas
  app/core/algorithms/hash_checker.py → TOCTOU hardening + import HashError
  app/core/filesystem/safe_path.py   → validate_allowed_root is_dir()
  app/cli/hash_cmd.py                → exit codes 0/1/2
  app/ui/static/index.html           → versão 1.1.0
  app/ui/static/app.js               → fallback 1.1.0
  tests/unit/test_cli.py             → 6 testes alinhados (exit 2)

Documentação:
  CHANGELOG.md                       → entrada [1.1.0]
  docs/RELEASE_NOTES_v1.1.md         → novo
  docs/QA_REPORT.md                  → §11 Fechamento Sprint 3
  docs/ARCHITECTURE.md               → tabela ADRs atualizada
  docs/API_STABILITY.md              → versão 1.1.0
  docs/THREAT_MODEL.md               → versão 1.1.0 + root semantics
  docs/SECURITY.md                   → root semantics + QA-020
  docs/adr/ADR-001..005.md           → novos
  docs/adr/ADR-007.md                → exit codes + versão
  docs/context/*                     → JR Memory Engine (6 arquivos)
```

## 6. Assets da Release

| Asset | Status |
|-------|--------|
| Source tarball | a gerar no GitHub |
| Wheel (pyproject.toml) | build via `python -m build` |
| CHANGELOG | ✅ pronto |
| Release Notes | ✅ pronto |
| RELEASE_SUMMARY (este) | ✅ pronto |

## 7. Notas de Migração

- **Scripts CLI:** erros agora retornam exit `2` (não mais `1`); `1` é reservado para MISMATCH do `verify`.
- **Devs:** `pip install -e ".[dev]"` instala versões pinadas.
- **API pública do Core:** 8 símbolos estáveis preservados — sem breaking changes.

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Release v1.1.0 · 01/08/2026 · jr (Tech Lead) + ARES (Security)
