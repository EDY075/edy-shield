# 🛡️ EDY SHIELD — Arquitetura e Planejamento da v2.1

> **Autor:** jr (Tech Lead / Software Architect) + ATLAS (Arquiteto) — TITAN AI SQUAD
> **Versão:** 0.1.0 (proposta) · **Status:** PLANEJAMENTO — nenhum código será escrito
> **Data:** 02/08/2026 · *Base: v2.0.0 (feature freeze) — Core FIM, plugins, CLI, Console SOC*

---

## 1. Visão Geral

A **v2.1** expande a plataforma EDY Shield de **ferramenta de verificação de integridade**
para **plataforma de análise defensiva (Blue Team)** — adicionando análise de conteúdo
(String/Entropy), persistência relacional (SQLite), um sistema de alertas e refinamentos
de UX (Dashboard + CLI) — **sem quebrar a arquitetura atual** (ADR-001/002/005).

### Princípio central

> **Evoluir por composição, não por acoplamento.** Novos módulos nascem como **plugins**
> (mesma via do `file_integrity`), o Core permanece **100% stdlib** (ADR-001 — `sqlite3`
> é stdlib, portanto **não quebra ADR-001**), e a UI **nunca** toca o Core (ADR-002).

---

## 2. Objetivos

| # | Objetivo | Critério de sucesso |
|---|----------|---------------------|
| O1 | **Análise de conteúdo** — identificar strings suspeitas e alta entropia | Plugins `string_analyzer` + `entropy_analyzer` com evidências e severidades |
| O2 | **Persistência relacional** — histórico e baselines em SQLite | `HistoryStore` e `FimStore` com backend SQLite (contrato atual preservado) |
| O3 | **Alertas** — notificação de mudanças/achados de segurança | `AlertEngine` com regras, canais (console/arquivo) e supressão |
| O4 | **Usabilidade** — Dashboard com métricas e CLI com saída estruturada | Dashboard com KPIs/gráficos; CLI com `--json` e filtros |
| O5 | **Zero regressão** — manter gates de qualidade | 361+ testes, cobertura ≥ 90%, mypy strict 0, ruff limpo |

---

## 3. Roadmap (v2.1)

| Fase | Entrega | Status |
|------|---------|--------|
| **v2.1-M1** | String Analyzer + Entropy Analyzer (core + plugins + CLI) | ⬜ Planejada |
| **v2.1-M2** | SQLite History (HistoryStore + FimStore + migração) | ⬜ Planejada |
| **v2.1-M3** | Sistema de Alertas (AlertEngine + canais + regras) | ⬜ Planejada |
| **v2.1-M4** | Plugins adicionais + Dashboard + CLI refinadas | ⬜ Planejada |
| **v2.1-RC** | Hardening ARES + docs + release | ⬜ Planejada |

---

## 4. Arquitetura

### 4.1 Princípios preservados (invariantes)

| Princípio | Aplicação na v2.1 |
|-----------|-------------------|
| **ADR-001** Core 100% stdlib | `sqlite3`, `math`, `re`, `statistics` — todos stdlib; zero deps runtime |
| **ADR-002** Camadas unidirecionais | `ui → services → plugins → core`; UI nunca chama o Core |
| **ADR-005** Erros de domínio | Novos erros herdam `EDYShieldError` (ex.: `AlertError`, `AnalyzerError`) |
| **Plugin como cidadão** | String/Entropy nascem como plugins via `PluginManager` |
| **Fronteira de paths única** | `resolve_safe_path` continua sendo a única validação de paths |
| **Testável** | Módulos puros no core + plugins finos; cobertura ≥ 90% por módulo |

### 4.2 Evolução das camadas

```text
UI (v2.1)
 ├── Console SOC (Dashboard com KPIs/gráficos; views String/Entropy/Alertas)
 ├── Website (inalterado — marketing)
 └── CLI (comandos string/entropy/alerts + saída --json)
      ↓
SERVICES (v2.1)
 ├── PluginManager (inalterado)
 ├── ReportEngine (json|txt|html|md) — suporta novos plugins
 ├── HistoryStore → SQLite (novo backend, contrato preservado)
 ├── FimStore → SQLite (novo backend, contrato preservado)   [ARES-QA-033 resolvido]
 └── AlertEngine (NOVO) — regras, canais, supressão
      ↓
PLUGINS (v2.1)
 ├── log_analyzer · hash_checker · file_integrity (inalterados)
 ├── string_analyzer (NOVO)
 ├── entropy_analyzer (NOVO)
 └── (futuros) ioc_scanner · pii_scanner
      ↓
CORE (v2.1)
 ├── core/string (NOVO) — tokenização, padrões, scoring
 ├── core/entropy (NOVO) — Shannon entropy, janela deslizante
 ├── core/alerts (NOVO) — avaliação de regras, canais
 ├── core/fim (inalterado — store pode ganhar adapter SQLite)
 └── core/* (inalterado)
```

### 4.3 SQLite — decisão central

| Aspecto | Decisão |
|---------|---------|
| **Módulo** | `sqlite3` da stdlib (não quebra ADR-001) |
| **Backend** | Adapters opcionais em `HistoryStore` e `FimStore`; contrato público **inalterado** |
| **Local** | `~/.edyshield/edy_shield.db` (single-file) |
| **Migração** | Script `tools/migrate_json_to_sqlite.py` (uma vez) + fallback de leitura JSON legado |
| **Benefício** | Resolve **ARES-QA-033** (baseline_id único via AUTOINCREMENT); queries de histórico; integridade transacional |
| **Risco** | `sqlite3` embutido é suficiente para single-user; concorrência multi-processo limitada (aceito — produto desktop/CLI) |

### 4.4 AlertEngine — visão

```text
ScanResult (qualquer plugin)
   → AlertEngine.ingest(result)
      → regras (severity >= MEDIUM, mudanças FIM, novas baselines)
      → supressão (janela de tempo, dedup por hash do alerta)
      → canais: console (log), arquivo (~/.edyshield/alerts/), (futuro: webhook/email)
      → AlertRecord persistido (SQLite) + consultável via API/CLI
```

**Não-objetivo:** notificação em tempo real (push/websocket) — fora do escopo v2.1;
produto é **sob demanda** (ADR-FIM-004: varredura quando solicitada).

---

## 5. Módulos (detalhe)

### 5.1 String Analyzer — `core/string` + plugin `string_analyzer`

| Item | Especificação |
|------|---------------|
| **Objetivo** | Detectar strings suspeitas em arquivos/logs: URLs, IPs, comandos, paths, padrões de IOC |
| **Core puro** | `core/string/` — tokenização por regex, normalização, scoring por categoria |
| **Plugin** | `string_analyzer` (validate/execute/health_check) → `ScanResult` |
| **Evidências** | Categoria + severidade (ex.: IP externo=LOW, credencial aparente=HIGH) |
| **Opções** | `categories` (url/ip/command/path), `min_length`, `encoding` |
| **Reuso** | `open_regular_file`, `resolve_safe_path`, `PluginManager`, `ReportEngine` |

### 5.2 Entropy Analyzer — `core/entropy` + plugin `entropy_analyzer`

| Item | Especificação |
|------|---------------|
| **Objetivo** | Medir entropia de Shannon de arquivos/strings para detectar criptografia/obfuscação/dados embaralhados |
| **Core puro** | `core/entropy/` — Shannon entropy (bytes), janela deslizante, classificação (low/normal/high) |
| **Plugin** | `entropy_analyzer` → `ScanResult` com métrica por arquivo |
| **Evidências** | Arquivo com entropia > limiar (ex.: ≥ 7.5 bits/byte) = MEDIUM/HIGH |
| **Limiares** | Configuráveis via `options["threshold"]`; default documentado |

> **Dependência estratégica:** Entropy complementa o String Analyzer (strings em alto
> entropia = suspeitas). Podem ser **implementados juntos** (M1).

### 5.3 SQLite History — evolução de `HistoryStore` + `FimStore`

| Item | Especificação |
|------|---------------|
| **Contrato** | `save/list/get/clear` (History) e `save/load/list/delete` (Fim) **inalterados** |
| **Implementação** | Adapter SQLite atrás da interface existente; JSON vira modo legado |
| **Tabelas** | `scans`, `baselines`, `baseline_entries`, `alerts` |
| **IDs** | `baseline_id` com AUTOINCREMENT → resolve ARES-QA-033 |
| **API** | Sem mudança no contrato de plugin/UI (mesmos endpoints `/api/history`, `/api/fim/*`) |

### 5.4 Sistema de Alertas — `core/alerts` + service `AlertEngine`

| Item | Especificação |
|------|---------------|
| **Core** | `core/alerts/rules.py` (avaliação pura), `channels.py` (console/arquivo) |
| **Service** | `AlertEngine` — ingere `ScanResult`, aplica regras, suprime, persiste, expõe |
| **Regras (v1)** | severidade ≥ MEDIUM; FIM com mudanças; baseline criada |
| **Supressão** | dedup por `(plugin, rule, hash_conteúdo)` dentro de janela |
| **CLI** | `edyshield alerts list|clear` |
| **UI** | View Alertas (count + lista) |

### 5.5 Plugins adicionais (roadmap imediato)

| Plugin | Prioridade | Nota |
|--------|-----------|------|
| `ioc_scanner` | P1 (pós M1) | Detecta IOCs (IPs, domínios, hashes) — reusa String Analyzer |
| `pii_scanner` | P2 (pós M2) | Detecta PII aparente (e-mail, CPF, cartão) — cuidado LGPD |
| `file_scanner` | P3 | Metadados + tipo + magic bytes |

> **Regra:** cada plugin novo segue o template existente (Plugin + Core puro + testes).

### 5.6 Dashboard melhorias

| Melhoria | Prioridade |
|----------|-----------|
| KPIs de segurança (total achados, por severidade) | P1 |
| Gráfico de severidade por plugin (SVG/Canvas leve, sem dep externa) | P1 |
| Últimos scans (timeline) | P1 |
| Widget de alertas (contagem + últimas notificações) | P2 |
| Filtro por plugin/severidade no histórico | P2 |

### 5.7 CLI melhorias

| Melhoria | Prioridade |
|----------|-----------|
| `--json` global (saída estruturada para automação) | P1 |
| `edyshield string|entropy` (novos comandos) | P1 |
| `edyshield alerts list|clear` | P1 |
| `edyshield history` (listar scans) | P2 |
| Filtros (`--severity`, `--plugin`, `--since`) | P2 |
| Colorização consistente + tabelas | P3 |

---

## 6. Prioridades (definidas pelo PO)

| # | Item | Prioridade | Fase |
|---|------|-----------|------|
| 1 | **String Analyzer** | 🔴 Alta | M1 |
| 2 | **Entropy Analyzer** | 🔴 Alta | M1 |
| 3 | **SQLite History** | 🟠 Média | M2 |
| 4 | **Sistema de Alertas** | 🟠 Média | M3 |
| 5 | **Plugins adicionais** | 🟡 Média | M4 |
| 6 | **Dashboard melhorias** | 🟡 Baixa | M4 |
| 7 | **CLI melhorias** | 🟡 Baixa | M4 |

---

## 7. Backlog (v2.1, priorizado)

| ID | Item | Fase | Esforço |
|----|------|------|---------|
| B-01 | `core/string` + plugin `string_analyzer` + testes | M1 | M |
| B-02 | `core/entropy` + plugin `entropy_analyzer` + testes | M1 | M |
| B-03 | CLI `string`/`entropy` + view Console | M1 | S |
| B-04 | SQLite: schema + adapter `HistoryStore` | M2 | M |
| B-05 | SQLite: adapter `FimStore` + migração JSON→SQLite | M2 | M |
| B-06 | Migração resolve ARES-QA-033 (baseline_id único) | M2 | S |
| B-07 | `core/alerts` + `AlertEngine` + canais console/arquivo | M3 | M |
| B-08 | CLI `alerts list|clear` + view Alertas | M3 | S |
| B-09 | Plugin `ioc_scanner` | M4 | M |
| B-10 | Dashboard KPIs + gráfico severidade + timeline | M4 | M |
| B-11 | CLI `--json` + filtros | M4 | M |
| B-12 | Hardening ARES + docs (CHANGELOG, RELEASE_NOTES, QA_REPORT) | RC | S |

---

## 8. Milestones

| Milestone | Escopo | Critério de saída |
|-----------|--------|-------------------|
| **M1 — Análise** | String + Entropy Analyzer (core, plugins, CLI, view) | Unit ≥ 90%; plugins via PluginManager; E2E CLI |
| **M2 — Persistência** | SQLite History + FimStore + migração | Contrato preservado; testes de migração; ARES-QA-033 resolvido |
| **M3 — Alertas** | AlertEngine + canais + CLI + view | Regras testadas; dedup/supressão validados |
| **M4 — UX** | Plugins extras + Dashboard + CLI refinadas | Lighthouse ≥ 90 (site); CLI `--json` funcional |
| **RC — Release** | Hardening + docs + RELEASE_NOTES_v2.1 | 0 Critical/High; cobertura ≥ 90%; CI verde |

---

## 9. Riscos

| # | Risco | Probabilidade | Impacto | Mitigação |
|---|-------|---------------|---------|-----------|
| R1 | **SQLite rompe ADR-001** | Baixa | Alto | `sqlite3` é stdlib — documentar ADR; testes de import sem deps |
| R2 | **Migração JSON→SQLite perde dados** | Média | Alto | Script idempotente + fallback de leitura legado + backup `~/.edyshield/backup/` |
| R3 | **Alertas geram ruído (falsos positivos)** | Média | Médio | Supressão + limiares configuráveis + severidade mínima |
| R4 | **Entropy com falsos positivos (binários legítimos)** | Alta | Médio | Limiar configurável; classificação low/normal/high; docs |
| R5 | **Crescimento do SQLite** | Baixa | Baixo | WAL mode; índices; `--vacuum` documentado |
| R6 | **Escopo cresce (v2.1 → v2.2)** | Média | Alto | Backlog priorizado; M1–M3 foco; M4 opcional se apertar |

---

## 10. Estimativa de Esforço

> Estimativa relativa em **pontos de história** (S = pequeno ~0.5-1d, M = médio ~1-2d, L = grande ~2-4d).

| Fase | Itens | S | M | L | Total estimado |
|------|-------|---|---|---|----------------|
| **M1** | B-01..B-03 | 1 | 2 | 0 | ~3-5 dias |
| **M2** | B-04..B-06 | 1 | 2 | 0 | ~3-5 dias |
| **M3** | B-07..B-08 | 1 | 1 | 0 | ~2-3 dias |
| **M4** | B-09..B-11 | 0 | 3 | 0 | ~3-6 dias |
| **RC** | B-12 | 1 | 0 | 0 | ~1 dia |
| **Total** | 12 itens | 4 | 8 | 0 | **~12-20 dias** (2-4 semanas) |

---

## 11. Dependências

```text
String Analyzer  ──┐
                   ├─► (independentes, podem ir juntos em M1)
Entropy Analyzer ──┘
        │
        ▼
SQLite History (M2) ──► resolve ARES-QA-033
        │
        ▼
Sistema de Alertas (M3) ──► consome ScanResult de QUALQUER plugin
        │
        ▼
Plugins extras + Dashboard + CLI (M4)
```

| Dependência | Justificativa |
|-------------|---------------|
| Alertas dependem de SQLite | AlertRecord persistido em SQLite |
| Entropy/String não dependem de SQLite | Podem ser entregues primeiro (M1) |
| IOC Scanner depende de String Analyzer | Reusa tokenização/pattern |
| Dashboard KPIs dependem de History (SQLite) | Queries de agregação |

---

## 12. Ordem Ideal de Implementação

1. **M1 — String + Entropy Analyzer** (primeiro; maior valor, sem dependências, valida o padrão de plugin para a plataforma)
2. **M2 — SQLite History** (funda a persistência relacional; desbloqueia alertas)
3. **M3 — Sistema de Alertas** (agrega valor a todos os plugins existentes)
4. **M4 — Plugins extras → Dashboard → CLI** (UX e expansão)
5. **RC — Hardening + docs** (fecha a release)

---

## 13. Não-Objetivos (fora do escopo v2.1)

- ❌ Monitoramento em tempo real (watchdog/agendador) — roadmap v3.0
- ❌ Notificações push/email/webhook — futuro
- ❌ Multi-usuário / multi-processo — produto desktop/CLI single-user
- ❌ Dependências de terceiros no Core (ADR-001 permanece)
- ❌ Nova stack de UI (React/Vue) — Console permanece vanilla + stdlib

---

## 14. Métricas de Sucesso da v2.1

| Métrica | Alvo |
|---------|------|
| Cobertura de testes | ≥ 90% (esperado ~93-94% com módulos novos) |
| Testes | 361 → ~480+ |
| Novos plugins | +2 a +3 (string, entropy, ioc) |
| ARES-QA-033 | ✅ Resolvido (SQLite) |
| 0 Critical/High | ✅ Gate ARES |
| CLI `--json` | Funcional (automação) |
| Docs | ARCHITECTURE/API_STABILITY/QA_REPORT/RELEASE_NOTES atualizados |

---

## 15. ADRs Propostos (materializar na implementação)

| ADR | Decisão | Motivo |
|-----|---------|--------|
| ADR-V21-001 | SQLite como backend de History/Fim (stdlib) | ADR-001 preservado; resolve ARES-QA-033 |
| ADR-V21-002 | String/Entropy como plugins + core puro | Mesmo padrão FIM; testabilidade |
| ADR-V21-003 | AlertEngine em services, regras no core | Separação regra (pura) × efeito (canal) |
| ADR-V21-004 | Backward compat: JSON legado legível após migração | Zero perda de dados |
| ADR-V21-005 | CLI `--json` como contrato estável | Automação e integração |

---

> **EDY Shield — Defenda. Verifique. Confie.**
> Planejamento v2.1 · jr (Software Architect) + ATLAS · TITAN AI SQUAD · **Aguardando aprovação do PO**
