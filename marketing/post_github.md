# 🛡️ EDY Shield v2.0.0 — File Integrity Monitor está no ar!

> **Defenda. Verifique. Confie.** · Python 3.12 · 100% stdlib no core

---

O **EDY Shield** é uma plataforma modular de cibersegurança defensiva (Blue Team). A v2.0
entrega o **File Integrity Monitor** — o módulo que cria uma baseline criptográfica de
diretórios e detecta alterações em tempo de varredura.

## ✨ O que há de novo

### File Integrity Monitor (FIM)

- 📸 **Baseline** — fotografia criptográfica do alvo (path relativo, digest SHA-256,
  tamanho, mtime, permissões) em JSON determinístico com round-trip validado
- 🔍 **Scan** — detecta arquivos **novos**, **modificados** e **removidos** com o digest
  como fonte de verdade
- 🔬 **Compare** — compara duas baselines persistidas (auditoria antes/depois)
- 🧩 **Plugin oficial** `file_integrity` via PluginManager
- 🖥️ **CLI**: `edyshield fim baseline criar ./conf` · `edyshield fim scan ./conf --baseline baseline.json`
- 📊 **Relatório Markdown** (novo formato além de JSON/TXT/HTML)
- 🎛️ **View FIM** no Console SOC com dropdown de baselines

### Identidade & Website

- 🎨 Branding oficial: **Escudo Verificado** + **Monograma E+Hash**
- 🌐 Website oficial criado (dark premium, GitHub Pages pronto)

## ✅ Qualidade

| Métrica | Valor |
|---|---|
| Testes | **361 passed, 2 skipped** |
| Cobertura | **91.92%** |
| mypy strict | **0 issues** (49 arquivos) |
| Core deps | **0** (100% stdlib) |

## 🚀 Instalação

```bash
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield && pip install -e .
edyshield --version   # edyshield 2.0.0
```

## 🗺️ Roadmap

- **v2.1** — String Analyzer · Entropy Analyzer · SQLite (baselines)
- **v2.2** — IOC Scanner
- **v3.0** — SOC Platform

Veja o **[CHANGELOG](https://github.com/EDY075/edy-shield/blob/main/CHANGELOG.md)** e a
**[Release Notes](https://github.com/EDY075/edy-shield/blob/main/docs/RELEASE_NOTES_v2.0.md)**.

**Contribua:** [`CONTRIBUTING.md`](https://github.com/EDY075/edy-shield/blob/main/CONTRIBUTING.md) · **Segurança:** [`SECURITY.md`](https://github.com/EDY075/edy-shield/blob/main/SECURITY.md)

---
*Feito com ♥ para o Blue Team · [EDY075](https://github.com/EDY075)*
