# 🚀 EDY Shield — Release Notes v1.1.0

> **Data:** 01/08/2026
> **Versão:** 1.1.0
> **Status:** 🟢 Estável
> **Tag sugerida:** `v1.1.0`

---

## 📌 Visão Geral

Esta release fecha oficialmente a **Sprint 3** e estabiliza completamente a versão 1.1 do
EDY Shield. O foco foi **robustez, segurança e documentação** — nenhuma feature nova foi
adicionada.

---

## ✨ Destaques

### 1. Segurança reforçada
- **TOCTOU hardening** (`ARES-QA-008`): leitura de arquivos com `os.open` + `O_NOFOLLOW` +
  `os.fstat` no file descriptor — fecha a janela de race entre validação e leitura.
- **`validate_allowed_root` validado** (`ARES-QA-020`): root inexistente ou não-diretório agora
  gera erro claro.
- **`exists()` redundante removido** (`ARES-QA-019`): elimina janela TOCTOU duplicada.

### 2. CLI com contrato definitivo
- **Exit codes padronizados** (`ARES-QA-029`): `0` sucesso · `1` MISMATCH · `2` erro de
  domínio — documentado no ADR-007.

### 3. Documentação sincronizada
- **ADR-001..005 materializados** (8/8 ADRs completos em `docs/adr/`).
- **THREAT_MODEL.md + SECURITY.md** refletem a semântica real da CLI (root = parent do alvo).
- **JR Memory Engine v1.0** — `docs/context/` com índice mestre para economia de contexto.

### 4. Qualidade de desenvolvimento
- **Dev deps pinadas** (`ARES-QA-022`): pytest 9.1.1, pytest-cov 7.1.0, mypy 2.3.0, ruff 0.16.1.
- **Suíte completa verde**: 196 testes passando, cobertura 92.90%, mypy strict 0 issues.

---

## 🛠️ Correções incluídas

| ID | Descrição | Severidade |
|----|-----------|------------|
| ARES-QA-008 | TOCTOU hardening (os.open + O_NOFOLLOW + fstat) | 🔵 Medium |
| ARES-QA-019 | `exists()` redundante removido em `compute()` | 🔵 Low |
| ARES-QA-020 | `validate_allowed_root` valida `is_dir()` | 🔵 Low |
| ARES-QA-022 | Dev deps pinadas (lock determinístico) | 🔵 Low |
| ARES-QA-027 | Docs CLI semantics (THREAT_MODEL/SECURITY) | ⚪ Info |
| ARES-QA-029 | Exit codes 0/1/2 para verify | ⚪ Info |
| — | Bug de import `HashError` no TOCTOU (mypy) | 🔴 Fix urgente |
| — | Testes de CLI alinhados ao novo contrato | 🔵 Low |

---

## 🔄 Mudanças de API

### CLI (`edyshield`)
```
Antes:  edyshield verify <file> --expected <hash>
        → 0 = OK, 1 = FAIL ou erro

Depois: edyshield verify <file> --expected <hash>
        → 0 = MATCH
        → 1 = MISMATCH (hash calculado, diferente)
        → 2 = erro de domínio / validação / inesperado
```

### Core (`app.core`)
- **Sem breaking changes na API pública** (8 símbolos estáveis preservados).

---

## ✅ Quality Gates

| Gate | Resultado |
|------|-----------|
| pytest | ✅ 196 passed, 2 skipped |
| coverage | ✅ 92.90% (gate ≥ 90%) |
| mypy strict | ✅ 0 issues (38 arquivos) |
| ruff check | ✅ All checks passed |
| ruff format | ✅ 57 files already formatted |
| CI (GitHub Actions) | ✅ Todos os jobs verdes |

---

## 📁 Artefatos de Entrega

```
docs/adr/           → 8 ADRs completos (001 a 008)
docs/context/       → JR Memory Engine v1.0 (6 arquivos)
docs/QA_REPORT.md   → Revisões ARES atualizadas
docs/THREAT_MODEL.md → Modelo de ameaças atualizado
CHANGELOG.md        → Entrada v1.1.0
```

---

## ⚠️ Notas de Migração

- **Devs:** `pip install -e ".[dev]"` agora instala versões pinadas — lock determinístico.
- **Scripts que usam a CLI:** verificar dependência do exit code `1` para erros — agora erros
  retornam `2`; `1` é reservado para MISMATCH.

---

## 🔮 Próximos Passos (v1.2 / v2.0)

- Cobertura de integração E2E via CLI (expansão).
- Comparação de integridade com múltiplos arquivos (batch).
- Suporte a checksum file (`.sha256sum` / `.md5sum`).
- **v2.0**: File Integrity Monitor, String Analyzer, Dashboard Streamlit, arquitetura de
  plugins externos.

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Release v1.1.0 · 01/08/2026 · jr (Tech Lead) + ARES (Security)