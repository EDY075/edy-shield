# EDY Shield — Project State

## Versão: 2.0.0-dev ✅ SPRINT 5 RELEASE READY
## Status: Sprint 5 ENCERRADA — File Integrity Monitor (FIM) entregue

## Métricas
| Métrica | Valor |
|---------|-------|
| Testes | 361 passed, 2 skipped |
| Cobertura | 91.92% (gate ≥ 90%) |
| mypy strict | 0 issues (49 arquivos) |
| ruff check | All checks passed |
| ruff format | 86 files OK |
| Core deps | 0 (100% stdlib) |
| Dev deps | pinadas (pytest 9.1.1, mypy 2.3.0, ruff 0.16.1) |

## Sprint 5 (v2.0.0-dev) — ✅ CONCLUÍDA
### Entregas
- ✅ Core FIM (`app/core/fim/`) — models, scanner, baseline, store (100% stdlib)
- ✅ Plugin `file_integrity` (baseline/scan/compare) via PluginManager
- ✅ CLI `edyshield fim baseline criar | scan` (exit 0/1/2)
- ✅ Report Engine Markdown (`fmt=md`)
- ✅ View FIM no Console SOC + endpoints `/api/fim/baselines`
- ✅ Round-trip validado (BaselineCorruptionError)
- ✅ Digest como fonte de verdade (ADR-FIM-002), não segue symlinks (ADR-FIM-003)
- ✅ Cobertura server.py 80% → 94% (endpoints reais)
- ✅ Código morto removido (_REPORT_FORMATS, args não usados)
- ✅ QA_REPORT §13 + RELEASE_NOTES_v2.0.md + CHANGELOG

### Identidade visual (Fases 1–2)
- ✅ Branding v1.0 aprovada (`brand/`) — Escudo Verificado + Monograma E+Hash
- ✅ Website criado (`website/`) — landing dark premium + workflow GitHub Pages

## Qualidade final
- pytest: 361 passed, 2 skipped
- coverage: 91.92%
- mypy strict: 0 issues (49 arquivos)
- ruff: limpo
- CI: verde

## Próximos passos (aprovados — aguardando instrução)
- Fase 3: Screenshots oficiais
- Fase 4: Kit de divulgação
- GitHub Pages público (`website/` pronto)
- Release oficial v2.0
- v2.1: String Analyzer, Entropy Analyzer, SQLite (baselines)

## Core Architecture (resumo)
```
ui (CLI + Console SOC)
  → services (PluginManager · HistoryStore · ReportEngine json|txt|html|md)
    → plugins (log_analyzer · hash_checker · file_integrity)
      → core/fim (models · scanner · baseline · store)
      → core (algorithms · crypto · filesystem · validators · exceptions · config · logging)
```

## Regras Permanentes
- Core é 100% stdlib (ADR-001)
- Direção única: ui → services → core (nunca inversa)
- Path validation: resolve_safe_path() é fronteira única
- Erros: EDYShieldError → HashError/ValidationError/FilesystemError/FimError
- Comparação de hashes: hmac.compare_digest em toda parte
- CI: pre-commit deve passar mypy strict, ruff, pytest, coverage ≥ 90%
