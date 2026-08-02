# Architecture Summary — EDY Shield v1.1

## Camadas (direção única)
```
UI Layer:      cli/hash_cmd.py → ui/server.py → static/
                  ↓
Service Layer: services/file_utils.py (shim), services/report_engine.py, services/history.py
                  ↓
Plugin Layer:  plugins/contracts.py, plugin_base.py, plugin_manager.py, plugin_registry.py
               plugins/builtin/{log_analyzer.py, hash_checker_plugin.py}
                  ↓
Core Layer:    algorithms/hash_checker.py → crypto/hashing.py, filesystem/safe_path.py,
               validators/input.py, exceptions/domain.py, config/settings.py,
               logging/logger.py, models/*.py
```

## Segurança-First (Arquitetura da Proteção)
| Camada | Controle | Localização |
|--------|----------|-------------|
| Input | normalize_algorithm (whitelist) | crypto/hashing.py |
| Path | resolve_safe_path + ensure_regular_file | filesystem/safe_path.py |
| Validators | validate_chunk_size, validate_expected | validators/input.py |
| Comparison | hmac.compare_digest (constante) | crypto/hashing.py |
| Logging | nunca loga conteúdo de arquivo | logging/logger.py |
| Erros | sanitizados (só target.name) | exceptions/domain.py |
| Apps | Entrypoint edyshield | cli/hash_cmd.py |

## Decisions Magnitude
- ADR-001: Core 100% stdlib (zero deps)
- ADR-002: Camadas unidirecionais
- ADR-006: Core em camadas (modular)
- ADR-007: CLI via argparse
- ADR-008: Config via env EDY_* (Settings frozen)