# 🛡️ EDY Shield — Release Notes v2.0.0

> **Versão:** 2.0.0 (Sprint 5 — File Integrity Monitor)
> **Data:** 02/08/2026
> **Status:** ✅ RELEASE OFICIAL
> **Identidade visual:** v1.0 aprovada (Escudo Verificado + Monograma E+Hash)

---

## Resumo

A **Sprint 5** entrega o principal diferencial técnico da v2.0: o **File Integrity
Monitor (FIM)** — um módulo que cria uma **baseline criptográfica** de um diretório
e detecta arquivos **novos**, **modificados** e **removidos** em varreduras posteriores.

Tudo isso **100% stdlib**, reutilizando o Core existente (`compute_file`,
`resolve_safe_path`, Report Engine, PluginManager) e sem nenhuma nova dependência
(ADR-001).

---

## Destaques

### 🛡️ File Integrity Monitor

| Recurso | Descrição |
|---|---|
| **Baseline** | Fotografia criptográfica do alvo — path relativo POSIX, digest, tamanho, mtime e permissões |
| **Scan** | Compara o estado atual contra a baseline; detecta novo/modificado/removido/inalterado |
| **Compare** | Compara duas baselines persistidas (antes/depois) sem re-varrer o disco |
| **JSON determinístico** | Mesmas entradas → mesmo arquivo byte a byte (ordem canônica) |
| **Round-trip validado** | Baseline corrompida é rejeitada com `BaselineCorruptionError` — nunca retornada parcial |
| **Digest = fonte de verdade** | `mtime`/`size` são triagem; comparação por hash (ADR-FIM-002) |
| **Não segue symlinks** | ADR-FIM-003 — symlinks são registrados como ignorados |

### 🧩 Plugin oficial `file_integrity`

- Ações `baseline`, `scan` e `compare` via `PluginManager`;
- Evidências com severidade por mudança: novo = LOW, modificado = MEDIUM,
  removido = HIGH, symlink = INFO;
- Registrado no `build_default_manager` com `FimStore` injetável.

### 🖥️ CLI

```bash
edyshield fim baseline criar ./conf                # cria baseline.json + FimStore
edyshield fim scan ./conf --baseline ./baseline.json   # exit 0 sem mudanças, 1 com mudanças
edyshield fim scan ./conf --baseline fim_sha256_...    # por id do FimStore
```

### 📊 Relatório Markdown

- Novo formato `md` no Report Engine (`render(result, "md")`);
- Exportação via `GET /api/report/{id}?fmt=md`;
- Link **MD** na view Relatórios do Console SOC.

### 🎛️ Console SOC — view FIM

- Formulário: ação (baseline/scan), algoritmo, diretório alvo;
- Dropdown de baselines populado via `GET /api/fim/baselines`;
- Resultado com severidades e estatísticas (added/modified/removed/unchanged).

---

## Arquitetura (resumo)

```
ui (Console SOC + CLI)
  → services (PluginManager · HistoryStore · ReportEngine json|txt|html|md)
    → plugins (log_analyzer · hash_checker · file_integrity)
      → core/fim (models · scanner · baseline · store)   ← NOVO (100% stdlib)
      → core (algorithms · filesystem · crypto · exceptions)
```

---

## Qualidade

| Métrica | v1.2 | v2.0.0-dev |
|---|---|---|
| Testes | 248 passed | **361 passed, 2 skipped** |
| Cobertura | 90.29% | **91.92%** (gate ≥ 90%) |
| mypy strict | 0 issues (44 arquivos) | **0 issues (49 arquivos)** |
| ruff check | limpo | **limpo** |
| ruff format | 78 OK | **86 files OK** |
| Core deps | 0 | **0 (100% stdlib)** |

### Cobertura de destaque

- `app/ui/server.py`: 80% → **94%** (testes de endpoints reais)
- `app/core/fim/*`: ~93% (models, baseline, scanner, store)

---

## Segurança (ARES)

- ✅ Path traversal no `baseline_id` mitigado (charset seguro + regex)
- ✅ Baseline corrompida/temperada rejeitada no load
- ✅ Symlinks não seguidos (ADR-FIM-003)
- ✅ TOCTOU mitigado (reuso de `compute_file` + `O_NOFOLLOW`)
- ✅ 0 Critical / 0 High abertos
- ⚠️ Info ARES-QA-033: `baseline_id` com granularidade de segundos (colisão em
  mesmo segundo) — aceito, anotado para SQLite na v2.1

---

## Arquivos

### Novos

```
app/core/fim/{__init__,models,ids,scanner,baseline,store}.py
app/plugins/builtin/file_integrity_plugin.py
tests/unit/test_fim_core.py
tests/unit/test_fim_plugin.py
tests/unit/test_fim_report.py
tests/unit/test_opener.py
tests/unit/test_server.py
docs/RELEASE_NOTES_v2.0.md
```

### Modificados

```
app/core/exceptions/{domain,__init__}.py      → FimError + BaselineCorruptionError/NotFoundError
app/core/filesystem/opener.py                  → encoding/errors no modo texto
app/services/report_engine.py                  → to_markdown + render("md")
app/ui/server.py                               → plugin FIM + /api/fim/baselines + fmt=md
app/cli/hash_cmd.py                            → subcomando fim (baseline criar | scan)
app/ui/static/{index.html,app.js}              → view FIM + dropdown + export MD
app/__init__.py · pyproject.toml               → versão 2.0.0.dev0
README.md · CHANGELOG.md · docs/QA_REPORT.md   → documentação da Sprint 5
```

---

## Próximos passos (pós-v2.0)

- **Fase 3** — Screenshots oficiais (padronização visual)
- **Fase 4** — Kit de divulgação (banners, thumbnail, posts, artigo)
- **GitHub Pages público** — site oficial (`website/` já criado, workflow pronto)
- **Release v2.0** — tag oficial + GitHub Releases
- **v2.1** — String Analyzer, Entropy Analyzer, SQLite para baselines

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Release v2.0.0-dev · 02/08/2026 · jr (Tech Lead) + ARES (Security) + ORION (Design)
