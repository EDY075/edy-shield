# 🛡️ EDY Shield v2.0.0 — File Integrity Monitor

> **Defenda. Verifique. Confie.** · Python 3.12 · 100% stdlib no core

---

## 🚀 Destaques

O **File Integrity Monitor (FIM)** é o grande diferencial desta release: cria uma
**baseline criptográfica** de um diretório e detecta arquivos **novos**,
**modificados** e **removidos** em varreduras posteriores — tudo **100% stdlib**,
sem nenhuma dependência externa (ADR-001).

### 🛡️ File Integrity Monitor

- **Baseline** — fotografia criptográfica do alvo (path relativo, digest, tamanho, mtime, permissões)
- **Scan** — detecta novo / modificado / removido / inalterado
- **Compare** — compara duas baselines persistidas (antes/depois)
- **JSON determinístico** + **round-trip validado** (baseline corrompida é rejeitada)
- **Digest como fonte de verdade** · não segue symlinks (ADR-FIM-002/003)

### 🧩 Plugin oficial `file_integrity`

- Ações `baseline` / `scan` / `compare` via `PluginManager`
- Severidades por mudança: novo=LOW · modificado=MEDIUM · removido=HIGH

### 🖥️ CLI

```bash
edyshield fim baseline criar ./conf                 # cria baseline.json + FimStore
edyshield fim scan ./conf --baseline baseline.json  # exit 0 sem mudanças, 1 com mudanças
edyshield fim scan ./conf --baseline fim_sha256_... # por id do FimStore
```

### 📊 Relatório Markdown

- Novo formato `md` no Report Engine + `GET /api/report/{id}?fmt=md`

### 🎛️ Console SOC — view FIM

- Formulário baseline/scan + dropdown de baselines (`GET /api/fim/baselines`)

### 🎨 Identidade visual v1.0

- Branding oficial: **Escudo Verificado** (logo principal) + **Monograma E+Hash** (favicon/app)
- **Website oficial** criado (`website/`) — dark premium, responsivo, SEO, GitHub Pages

---

## 📦 Instalação

```bash
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
edyshield --version          # edyshield 2.0.0
```

---

## ✅ Qualidade

| Métrica | Valor |
|---|---|
| Testes | **361 passed, 2 skipped** |
| Cobertura | **91.92%** (gate ≥ 90%) |
| mypy strict | **0 issues** (49 arquivos) |
| ruff | limpo |
| Core deps | **0** (100% stdlib) |

---

## 🗺️ Roadmap

| Versão | Entregas |
|---|---|
| **v2.0** ✅ | File Integrity Monitor, relatório Markdown, view FIM, branding + website |
| **v2.1** | String Analyzer · Entropy Analyzer · SQLite (baselines) |
| **v2.2** | IOC Scanner |
| **v3.0** | SOC Platform — console integrado |

---

## 🤝 Contribua

Veja [`CONTRIBUTING.md`](https://github.com/EDY075/edy-shield/blob/main/CONTRIBUTING.md) e [`SECURITY.md`](https://github.com/EDY075/edy-shield/blob/main/SECURITY.md).

**Full Changelog:** [`CHANGELOG.md`](https://github.com/EDY075/edy-shield/blob/main/CHANGELOG.md) · **Release Notes:** [`docs/RELEASE_NOTES_v2.0.md`](https://github.com/EDY075/edy-shield/blob/main/docs/RELEASE_NOTES_v2.0.md)
