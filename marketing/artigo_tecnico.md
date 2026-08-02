# Construindo um File Integrity Monitor 100% stdlib em Python

> **Artigo técnico · EDY Shield v2.0** · por EDY075 · publicado em Dev.to/Medium
> **Tema:** integridade de arquivos, criptografia, arquitetura em camadas, Blue Team

---

## Resumo

Neste artigo, mostro como construímos um **File Integrity Monitor (FIM)** — ferramenta
que cria uma baseline criptográfica de um diretório e detecta arquivos novos, modificados
e removidos — usando **apenas a biblioteca padrão do Python 3.12**. Zero dependências
externas, arquitetura em camadas e cobertura de testes acima de 90%.

## 1. Por que um FIM?

A integridade de arquivos é um pilar da segurança defensiva (Blue Team). Sistemas de
referência (NIST, CIS Controls) recomendam monitorar alterações em arquivos críticos de
configuração, binários e dados. Um FIM permite:

- Detectar **modificações não autorizadas** (malware, tampering);
- Auditar **instalações e atualizações** (antes/depois);
- Detectar **arquivos novos** (droppers, backdoors) e **removidos** (exfiltração);

## 2. Decisões de arquitetura

| Decisão | Motivo |
|---|---|
| **100% stdlib** (ADR-001) | Menor superfície de ataque por supply chain; portável |
| **Digest como fonte de verdade** | `mtime`/`size` são forjáveis; SHA-256 não tem colisão prática |
| **Camadas unidirecionais** | `ui → services → plugins → core` — domínio puro e testável |
| **JSON determinístico** | Mesmas entradas → mesmo arquivo byte a byte (auditável) |
| **Round-trip validado** | Baseline corrompida é rejeitada, nunca retornada parcial |

## 3. Estrutura do Core FIM

```
app/core/fim/
├── models.py    # Baseline, BaselineEntry, Snapshot, FimDiff, ChangeType
├── ids.py       # build_baseline_id (fim_<algo>_<UTC>)
├── scanner.py   # scan_snapshot, compare_baseline_snapshot
├── baseline.py  # create_baseline, load_baseline, save_baseline
└── store.py     # FimStore (~/.edyshield/fim/)
```

O scanner reutiliza o Core existente (`compute_file` com `O_NOFOLLOW` + `fstat` para
mitigação TOCTOU) e a fronteira única de paths (`resolve_safe_path`).

## 4. Como funciona

```python
from app.core.fim import create_baseline, scan_snapshot, compare_baseline_snapshot

# 1. Fotografia do estado inicial
baseline = create_baseline("./conf", algorithm="SHA256")

# 2. Persistência (JSON determinístico)
save_baseline(baseline, "baseline.json")

# 3. Varredura posterior
snapshot = scan_snapshot("./conf")

# 4. Comparação (digest = fonte de verdade)
diff = compare_baseline_snapshot(baseline, snapshot)
# diff.added / diff.modified / diff.removed
```

## 5. CLI e integração

```bash
edyshield fim baseline criar ./conf
edyshield fim scan ./conf --baseline baseline.json
# novo       config.tpl
# modificado app.ini
# removido   old.cert
```

O FIM também é um **plugin** registrado no `PluginManager`, consumível pelo Console SOC
(web) e exportável em **JSON/TXT/HTML/Markdown**.

## 6. Segurança

- **Path traversal** no baseline_id → charset seguro + regex;
- **Baseline corrompida** → `BaselineCorruptionError` no load;
- **Symlinks** não seguidos (ADR-FIM-003) — registrados como ignorados;
- **TOCTOU** mitigado reutilizando `compute_file` (`O_NOFOLLOW` + `fstat`).

## 7. Qualidade

- **361 testes**, 2 skipped · cobertura **91.92%** · mypy strict **0 issues** · ruff limpo
- Testes E2E validam o comportamento real da CLI (baseline → scan → detecção)

## 8. Próximos passos

- **v2.1** — String Analyzer, Entropy Analyzer, SQLite para baselines
- **v2.2** — IOC Scanner
- **v3.0** — SOC Platform

## Conclusão

Um FIM robusto **não exige dependências pesadas**. Com disciplina de arquitetura,
fronteira de paths e digest como fonte de verdade, entregamos um módulo defensivo
confiável e 100% auditável — tudo com a stdlib do Python.

**Código:** [github.com/EDY075/edy-shield](https://github.com/EDY075/edy-shield) ·
**Licença:** MIT
