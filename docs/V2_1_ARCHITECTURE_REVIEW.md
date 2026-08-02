# 🏗️ EDY SHIELD — Revisão Técnica da v2.1 (Ordem das Milestones)

> **Autor:** jr (Software Architect) + ATLAS — TITAN AI SQUAD
> **Versão:** 1.0 (revisão) · **Status:** APROVADA pelo PO (EDY) · **Data:** 02/08/2026
> **Base:** `docs/V2_1_ARCHITECTURE.md` (planejamento original) — esta revisão **reorganiza** as milestones
> **Decisão central:** SQLite History passa a ser a **fundação (M1)** — antes de String/Entropy.

---

## 1. Ordem Recomendada (milestones reorganizadas)

| Fase | Escopo | Antes | **Depois (revisado)** | Esforço |
|------|--------|-------|----------------------|---------|
| **M1** | **SQLite History** (HistoryStore + FimStore + migração) | M2 | **M1** | ~3-5d |
| **M2** | **String + Entropy Analyzer** (core, plugins, CLI, view) | M1 | **M2** | ~3-5d |
| **M3** | **Alert Engine** (regras, canais, CLI, view) | M3 | M3 | ~2-3d |
| **M4** | **Dashboard + CLI melhorias** (KPIs, `--json`, filtros) | M4 | M4 | ~3-6d |
| **M5** | **Plugins extras** (IOC, PII) | M4 | **M5 (pós-RC)** | ~2-4d |
| **RC** | Hardening + docs | RC | RC | ~1d |
| | **Total** | | | **~12-18d (2-3 sem.)** |

**Mudança chave:** M1 ↔ M2 invertidos. **SQLite passa a ser a primeira entrega.**

---

## 2. Justificativa

### 2.1 SQLite é a única dependência transversal

| Módulo | Depende de SQLite? | Depende de String/Entropy? |
|--------|:---:|:---:|
| SQLite History | — | ❌ |
| String Analyzer | ❌ (para existir) | — |
| Entropy Analyzer | ❌ (para existir) | ❌ |
| Alert Engine | ✅ **Sim** (persistir AlertRecords) | ⚠️ Não, mas ganha valor |
| Dashboard | ✅ **Sim** (agregação/KPIs) | ⚠️ Não, mas ganha conteúdo |

SQLite é a **fundação transversal**: três módulos (Alertas, Dashboard e a persistência de
qualquer plugin novo) dependem dela. String/Entropy são **folhas independentes** da árvore.

### 2.2 Elimina retrabalho (princípio: fundação antes de folhas)

```
Ordem original:  String/Entropy (M1) → SQLite (M2)
  → resultados de M1 persistem em JSON → migrados para SQLite em M2 → RETRABALHO

Ordem revisada:  SQLite (M1) → String/Entropy (M2)
  → plugins novos já nascem persistindo no backend definitivo → ZERO retrabalho
```

Quanto mais módulos antes do SQLite, maior o volume de dados a migrar. Inverter a ordem
faz os plugins novos (String/Entropy) já persistirem em SQLite desde o primeiro dia.

### 2.3 Desbloqueia Alertas e Dashboard de forma limpa

- **Alert Engine (M3):** persiste `AlertRecord` em SQLite desde o início — sem adapter temporário JSON.
- **Dashboard (M4):** agregação (KPIs, `COUNT`, `GROUP BY severity`) é natural em SQLite;
  em JSON exigiria ler N arquivos e agregar em memória.

### 2.4 M1 não é "invisível" — entrega valor concreto

- Resolve **ARES-QA-033** (colisão de `baseline_id` por segundo — bug real do FIM);
- Habilita `edyshield history` (listar scans) — funcionalidade nova;
- Histórico mais robusto (transacional, consultável, sem arquivos dispersos).

---

## 3. Dependências entre Módulos

```text
M1 SQLite (fundação)
   │
   ├──► M2 String/Entropy (plugins; persistência já em SQLite)
   │
   ├──► M3 Alert Engine (persiste AlertRecord; consome ScanResult de QUALQUER plugin)
   │
   └──► M4 Dashboard (agregação SQLite) + CLI (--json, filters)
            │
            └──► M5 Plugins extras (IOC reusa String; PII reusa String)

RC = Hardening + docs (depende de todos)
```

| Dependência | Tipo | Justificativa |
|-------------|------|---------------|
| Alertas → SQLite | **Forte** | `AlertRecord` persistido em SQLite |
| Dashboard → SQLite | **Forte** | Agregação/KPIs via queries |
| Dashboard → Alertas | Fraca | Widget de alertas (opcional em M4) |
| Dashboard → History (SQLite) | Forte | KPIs sobre scans |
| IOC Scanner → String Analyzer | Forte | Reusa tokenização/patterns |
| PII Scanner → String Analyzer | Forte | Reusa tokenização |
| String/Entropy → SQLite | Fraca (existência) | Plugin funciona sem; persistência usa SQLite |
| String/Entropy → PluginManager | Forte | Contrato obrigatório |

---

## 4. Impacto de Cada Alteração

### 4.1 M1 — SQLite History (movido de M2 para M1)

| Impacto | Detalhe |
|---------|---------|
| **Positivo** | Fundação pronta; zero retrabalho para módulos seguintes |
| **Positivo** | ARES-QA-033 resolvido cedo; `edyshield history` habilitado |
| **Negativo** | Primeira entrega é infraestrutura (menos "visível" que análise) |
| **Mitigação** | Documentar que M1 resolve bug real + habilita comando novo |
| **Escopo** | Restrito a persistência — NÃO incluir alertas em M1 (evita scope creep) |

### 4.2 M2 — String/Entropy (movido de M1 para M2)

| Impacto | Detalhe |
|---------|---------|
| **Positivo** | Plugins já nascem com persistência SQLite (sem segunda migração) |
| **Positivo** | Ordem de implementação segue a lógica fundação→folhas |
| **Negativo** | Valor visível chega ~1 semana depois |
| **Mitigação** | M1 curto (~3-5d); M2 entrega análise logo em seguida |

### 4.3 M3 — Alert Engine (inalterado)

| Impacto | Detalhe |
|---------|---------|
| **Positivo** | SQLite já disponível para `AlertRecord` |
| **Nenhum negativo** | Ordem já era coerente |

### 4.4 M4 — Dashboard + CLI (inalterado, mas mais simples)

| Impacto | Detalhe |
|---------|---------|
| **Positivo** | Agregação SQLite pronta; KPIs triviais de implementar |
| **Nenhum negativo** | — |

### 4.5 M5 — Plugins extras (desmembrado de M4)

| Impacto | Detalhe |
|---------|---------|
| **Positivo** | M4 fica focado em UX; M5 vira expansão contínua pós-RC |
| **Negativo** | IOC/PII não entram na release v2.1 oficial (ficam para patch/2.2) |
| **Decisão** | Aceito — foco da v2.1 é fundação + análise + alertas + UX |

### 4.6 Impacto global no backlog

| Item | Antes | Depois |
|------|-------|--------|
| B-04/B-05/B-06 (SQLite) | M2 | **M1** |
| B-01/B-02/B-03 (String/Entropy) | M1 | **M2** |
| B-07/B-08 (Alertas) | M3 | M3 |
| B-10/B-11 (Dashboard/CLI) | M4 | M4 |
| B-09 (IOC Scanner) | M4 | **M5 (pós-RC)** |

---

## 5. Roadmap Atualizado (v2.1)

| Fase | Entregas | Critério de saída | Esforço |
|------|----------|-------------------|---------|
| **M1 — Fundação** | SQLite: schema + adapter `HistoryStore` + adapter `FimStore` + migração JSON→SQLite + ARES-QA-033 resolvido | Contrato preservado; testes de migração; `edyshield history` funcional | ~3-5d |
| **M2 — Análise** | `core/string` + plugin `string_analyzer` · `core/entropy` + plugin `entropy_analyzer` · CLI `string|entropy` · view Console | Unit ≥ 90%; plugins via PluginManager; E2E CLI; persistência SQLite | ~3-5d |
| **M3 — Alertas** | `core/alerts` + `AlertEngine` + canais console/arquivo + CLI `alerts list|clear` + view Alertas | Regras testadas; dedup/supressão validados; persistência SQLite | ~2-3d |
| **M4 — UX** | Dashboard KPIs + gráfico severidade + timeline + widget alertas · CLI `--json` + filtros | Lighthouse ≥ 90 (site); CLI `--json` funcional; agregação SQLite | ~3-6d |
| **M5 — Expansão** (pós-RC) | Plugin `ioc_scanner` (reusa String) · Plugin `pii_scanner` (reusa String) | Unit ≥ 90%; novos plugins via PluginManager | ~2-4d |
| **RC — Release** | Hardening ARES + docs (CHANGELOG, RELEASE_NOTES_v2.1, QA_REPORT, API_STABILITY) | 0 Critical/High; cobertura ≥ 90%; CI verde | ~1d |

### Sequência de implementação (ordem ideal)

```
M1 SQLite ──► M2 String/Entropy ──► M3 Alertas ──► M4 Dashboard/CLI ──► M5 Plugins ──► RC
   (fundação)      (análise)           (reação)        (UX)            (expansão)    (release)
```

---

## 6. Resumo da Decisão

> **A ordem original (String/Entropy → SQLite) foi REVISADA.**
> **Nova ordem: SQLite (M1) → String/Entropy (M2) → Alertas (M3) → Dashboard/CLI (M4) → Plugins (M5) → RC.**
>
> Motivo: SQLite é a fundação transversal — minimiza retrabalho, mantém a arquitetura
> limpa (camadas unidirecionais, core 100% stdlib) e desbloqueia Alertas + Dashboard.

---

> **EDY Shield — Defenda. Verifique. Confie.**
> Revisão Técnica v2.1 · jr (Software Architect) + ATLAS · TITAN AI SQUAD · **Aguardando OK para implementação**
