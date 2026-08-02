# EDY Shield — Project State

## Versão: 1.1.0 ✅ RELEASE READY
## Status: Sprint 3 ENCERRADA — Release v1.1.0 publicada e pronta para tag

## Métricas
| Métrica | Valor |
|---------|-------|
| Testes | 196 passed, 2 skipped |
| Cobertura | 92.90% (gate ≥ 90%) |
| mypy strict | 0 issues (38 arquivos) |
| ruff check | All checks passed |
| ruff format | 57 files OK |
| Core deps | 0 (100% stdlib) |
| Dev deps | pinadas (pytest 9.1.1, mypy 2.3.0, ruff 0.16.1) |

## Sprint 3 (v1.1) — ✅ CONCLUÍDA
### Pendências fechadas
- ✅ ARES-QA-008: TOCTOU hardening (os.open + O_NOFOLLOW + fstat)
- ✅ ARES-QA-019: exists() redundante removido
- ✅ ARES-QA-020: validate_allowed_root valida is_dir()
- ✅ ARES-QA-022: dev deps pinadas
- ✅ ARES-QA-027: THREAT_MODEL/SECURITY com semântica real da CLI
- ✅ ARES-QA-029: exit codes 0/1/2
- ✅ ADR-001..005 materializados (8/8 ADRs)
- ✅ Bug HashError import corrigido
- ✅ Testes CLI alinhados ao novo contrato

## Qualidade final
- pytest: 196 passed, 2 skipped, 7 warnings esperados
- coverage: 92.90%
- mypy strict: 0 issues (38 arquivos)
- ruff: limpo
- CI: verde

## Próximos passos (v1.2 / v2.0 — NÃO iniciados ainda)
- Batch checksum / checksum files
- Testes E2E via CLI expandidos
- v2.0: File Integrity Monitor, String Analyzer, Dashboard, plugins externos

## Core Architecture (resumo)
```
ui (CLI + server) → services (file_utils, report_engine, history)
  → plugins (LogAnalyzer, HashPlugin)
    → core (algorithms, crypto, filesystem, validators, exceptions, config, logging)
```

## Regras Permanentes
- Core é 100% stdlib (ADR-001)
- Direção única: ui → services → core (nunca inversa)
- Path validation: resolve_safe_path() é fronteira única
- Erros: EDYShieldError → HashError/ValidationError/FilesystemError
- Comparação de hashes: hmac.compare_digest em toda parte
- CI: pre-commit deve passar mypy strict, ruff, pytest, coverage ≥ 90%