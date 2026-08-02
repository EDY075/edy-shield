# 🛡️ EDY Shield v1.1.0 — Sprint 3: Estabilização

> **Defenda. Verifique. Confie.**

Plataforma modular de cibersegurança defensiva em **Python 3.12** — Core 100% stdlib, zero dependências de runtime.

---

## 🎯 Destaques desta release

- 🔒 **TOCTOU hardening** — leitura de arquivos com `os.open` + `O_NOFOLLOW` + `os.fstat` no file descriptor, fechando a janela de race entre validação e leitura
- 🔢 **Exit codes definitivos na CLI** — `0` sucesso · `1` MISMATCH · `2` erro de domínio
- 📚 **8/8 ADRs materializados** — documentação de decisões arquiteturais completa
- 🧠 **JR Memory Engine v1.0** — sistema de contexto incremental (economia ~40% de tokens)
- 📌 **Dev deps pinadas** — build determinístico e reproduzível

## ✅ Quality Gates

| Gate | Resultado |
|------|-----------|
| 🧪 pytest | **196 passed, 2 skipped** |
| 📊 coverage | **92.90%** (gate ≥ 90%) |
| 🔍 mypy strict | **0 issues** (38 arquivos) |
| 🧹 ruff | **All checks passed** |
| 🚀 CLI | `edyshield 1.1.0` |

## 🔒 Segurança

- TOCTOU hardening (ARES-QA-008)
- `validate_allowed_root` valida `is_dir()` (ARES-QA-020)
- `exists()` redundante removido (ARES-QA-019)
- Path traversal bloqueado na fronteira única (`resolve_safe_path`)
- Comparação de hashes em tempo constante (`hmac.compare_digest`)
- Core 100% stdlib — zero superfície de ataque de supply chain

## 📦 Instalação

```bash
pip install edy-shield
# ou em desenvolvimento:
git clone <repo-url>
cd EDYShield
pip install -e ".[dev]"
```

## 🚀 Uso rápido

```bash
edyshield --version                    # edyshield 1.1.0
edyshield hash arquivo.txt             # calcula SHA-256
edyshield verify arquivo.txt --expected <hash>   # 0=OK, 1=FAIL, 2=erro
edyshield --help                       # ajuda completa
```

## 📁 Estrutura

```
EDYShield/
├── app/
│   ├── core/          # Domínio puro (100% stdlib)
│   ├── services/      # Casos de uso (report, history, file_utils)
│   ├── plugins/       # Plugin framework + builtin (LogAnalyzer, HashChecker)
│   ├── cli/           # CLI argparse
│   └── ui/            # UI HTML dark + REST server
├── docs/
│   ├── adr/           # 8 Architecture Decision Records
│   ├── context/       # JR Memory Engine
│   └── RELEASE_NOTES_v1.1.md
└── tests/             # 196 testes (unit + integration)
```

## 📄 Documentação

- [Release Notes](RELEASE_NOTES_v1.1.md)
- [Arquitetura](ARCHITECTURE.md)
- [Modelo de Ameaças](THREAT_MODEL.md)
- [QA Report](QA_REPORT.md)
- [API Stability](API_STABILITY.md)

## 📜 Licença

[MIT](../LICENSE)

---

**Full Changelog:** [CHANGELOG.md](../CHANGELOG.md) · **Release Summary:** [RELEASE_SUMMARY_v1.1.0.md](RELEASE_SUMMARY_v1.1.0.md)

> EDY Shield — Defenda. Verifique. Confie. 🛡️