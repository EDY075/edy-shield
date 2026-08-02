# 🤝 Contribuindo para o EDY Shield

> Guia de contribuição do **EDY Shield** — plataforma modular de cibersegurança defensiva em
> **Python 3.12**, core **100% stdlib**. Obrigado por contribuir! 💙

---

## 1. Setup do ambiente

### Pré-requisitos

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **git** (para clonar e abrir PRs)

### Passo a passo

```bash
# 1. Clone e entre na pasta
git clone https://github.com/usuario/edyshield.git
cd EDYShield

# 2. Crie e ative um ambiente virtual
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 3. Instale o pacote em modo editable COM as dependências de desenvolvimento
pip install -e ".[dev]"
# alternativa equivalente (requirements-dev.txt):
# pip install -e . && pip install -r requirements-dev.txt
```

> O core é 100% stdlib — o runtime não instala nenhuma dependência de terceiros
> (ADR-001). `[dev]` instala apenas ferramentas de qualidade: `pytest`, `pytest-cov`,
> `mypy` e `ruff`.

---

## 2. Fluxo de trabalho

1. **Crie uma branch** a partir de `main` com nome descritivo:
   ```bash
   git checkout -b feat/minha-melhoria
   ```
2. **Implemente a mudança com testes** — todo código novo deve ter cobertura unitária;
   funcionalidades de segurança exigem testes negativos (ver suíte existente).
3. **Rode os Quality Gates localmente** (seção 3).
4. **Commit** usando **Conventional Commits**:
   ```text
   feat: adiciona verificação de integridade em lote
   fix: corrige validação de path traversal
   docs: atualiza roadmap e API stability
   refactor: extrai validação de digest para app.core.validators
   ```
5. **Abra um Pull Request** descrevendo:
   - O que mudou e por quê;
   - Testes executados (comandos e resultado);
   - Impacto em segurança, API pública ou documentação.

---

## 3. Quality Gates (obrigatórios antes do merge)

Rode todos os comandos na raiz do projeto:

```bash
# 1. Testes + cobertura (gate: >= 90%, configurado no pyproject)
pytest

# 2. Type check estrito (mypy strict)
mypy app

# 3. Lint
ruff check .

# 4. Formatação
ruff format --check .
```

**Estado atual de referência (Sprint 2):**

| Check | Referência |
|-------|------------|
| `pytest` | ✅ 101 passed, 2 skipped (symlink Windows), 7 warnings (DeprecationWarning MD5/SHA1 esperados) |
| Cobertura | ✅ **92.90%** (gate 90%) |
| `mypy app` | ✅ 0 issues em 25 arquivos |
| `ruff check .` | ✅ limpo |
| `ruff format --check .` | ✅ 36 arquivos OK |

> ⚠️ Os 7 warnings de `DeprecationWarning` (MD5/SHA1) são **esperados e intencionais**
> (ARES-QA-004) — não os remova.

---

## 4. Regras de arquitetura

O projeto segue camadas unidirecionais **`ui → services → core`**:

```text
app/
├── cli/       → INTERFACE CLI (argparse)
├── core/      → DOMÍNIO PURO — 100% stdlib, sem UI/CLI
│   ├── algorithms/    → API pública de hash (compute, verify_file, ...)
│   ├── config/        → Settings frozen + load_settings (EDY_*)
│   ├── crypto/        → HashAlgorithm, normalize_algorithm, new_hasher, safe_compare
│   ├── exceptions/    → EDYShieldError → HashError/ValidationError/FilesystemError
│   ├── filesystem/    → resolve_safe_path, ensure_regular_file (fronteira de paths)
│   ├── logging/       → setup_logging (idempotente), get_logger
│   ├── models/        → HashResult, HashSource (+ shims de erros)
│   ├── report/        → RESERVADO (sem código — roadmap v2.0)
│   └── utils/         → RESERVADO (sem código)
├── services/   → CASOS DE USO (shim de segurança de paths)
└── ui/         → INTERFACE WEB (static, dark)
```

Regras inegociáveis:

- 🔄 **Direção única de dependências** — `ui → services → core`. Nada no `core` importa de
  `services`, `cli` ou `ui`.
- 🧱 **Core 100% stdlib** — proibido adicionar dependência de terceiros no runtime (ADR-001).
- 🚫 **Sem código morto / abstrações sem uso** — não crie `Protocol`/classes/helpers que nenhum
  chamador utiliza (ADR-001: "evitar abstrações sem uso"). `report/` e `utils/` são reservados
  justamente por isso.
- 🔐 **Fronteira única de paths** — qualquer nova operação de arquivo deve passar por
  `app.core.filesystem.safe_path` (`resolve_safe_path` + `ensure_regular_file`). Nada de
  `Path.open()` direto sem validação.
- 🛂 **Whitelist de algoritmos** — novos algoritmos entram no enum `HashAlgorithm`
  (`app.core.crypto`) e na validação; nunca aceite nomes arbitrários do usuário.
- 📦 **Shims preservados** — `app.core.models.common` e `app.services.file_utils` são re-exports
  de compatibilidade; **não adicione lógica nova** neles (vai para o Core).
- 🧪 **Segurança testada** — mudanças na fronteira de paths/algoritmos/comparação exigem testes
  negativos (traversal, `None`, tipos inválidos, arquivos especiais).

---

## 5. Convenções

- **Python 3.12+** — use type hints modernos (`str | Path`, `type X = ...` quando aplicável).
- **Docstrings** em estilo Google para módulos, classes e funções públicas.
- **Dataclasses frozen + slots** para resultados imutáveis (`HashResult`, `Settings`).
- **Erros de domínio** — nunca vaze traceback bruto para o usuário; use a hierarquia
  `app.core.exceptions.domain` (ADR-005).
- **Mensagens de erro** — nunca exponha caminhos absolutos (ARES-QA-005); use `basename`.
- **Logging** — use `get_logger("modulo.x")`; nunca logue conteúdo de arquivo.
- **`ruff` line-length 100** — formatação automática via `ruff format`.
- **PT-BR** nos docstrings/mensagens de usuário; **EN** em código e identificadores (padrão atual).

---

## 6. Checklist do PR

- [ ] Testes passando (`pytest`) com cobertura ≥ 90%
- [ ] `mypy app` sem erros (strict)
- [ ] `ruff check .` limpo e `ruff format --check .` OK
- [ ] Sem dependências de terceiros no core
- [ ] Documentação atualizada (README, CHANGELOG, API_STABILITY quando aplicável)
- [ ] Mudanças de segurança revisadas (ARES) e refletidas em `SECURITY.md`/`THREAT_MODEL.md`

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Guia de contribuição · TITAN AI SQUAD
