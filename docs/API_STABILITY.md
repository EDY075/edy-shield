# 🧬 EDY Shield — Contrato de Estabilidade da API Pública

> Este documento define o **contrato de estabilidade** da API pública do EDY Shield: quais
> símbolos são estáveis, qual o nível de estabilidade por área e a política de versionamento
> semântico. Ele existe para que consumidores (CLI, scripts, ferramentas) saibam **no que podem
> confiar** entre releases.

- **Versão atual:** 1.1.0
- **Status:** Alpha (Development Status :: 3 - Alpha, conforme `pyproject.toml`)

---

## 1. Níveis de estabilidade

| Nível | Significado | Mudanças permitidas |
|-------|-------------|---------------------|
| **STABLE** | API congelada para uso geral | Apenas adições retrocompatíveis; remoções/renomes apenas em **major** (≥1.0) com depreciação prévia |
| **BETA** | Estável em forma, ainda sujeito a ajustes | Mudanças com aviso e depreciação; esperadas antes da 1.0 |
| **RESERVED** | Estrutura reservada — sem API pública | Sem garantia; pode mudar ou ser removida sem aviso |

---

## 2. Símbolos públicos estáveis

### 2.1 `app.core.algorithms` — **STABLE**

API pública do Hash Checker (fonte: `__all__` de `app/core/algorithms/__init__.py`):

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `DEFAULT_CHUNK_SIZE` | `int` | Tamanho padrão de chunk (65536 bytes) |
| `HashAlgorithm` | `enum.Enum` | Whitelist: `SHA256`, `SHA1`, `MD5` |
| `compute(source, algorithm, *, encoding, chunk_size, allowed_root)` | `HashResult` | Dispatcher: `bytes`/`Path`/`str` → resultado estruturado |
| `compute_bytes(data, algorithm)` | `str` | Digest hex de bytes crus |
| `compute_text(text, algorithm, encoding="utf-8")` | `str` | Digest hex de texto |
| `compute_file(path, algorithm, chunk_size, *, allowed_root)` | `str` | Digest hex de arquivo (lido em chunks) |
| `verify_file(path, expected, algorithm, *, chunk_size, allowed_root)` | `bool` | Verificação case-insensitive em tempo constante |
| `supported_algorithms()` | `list[str]` | Nomes suportados (`["SHA256", "SHA1", "MD5"]`) |

> Estes 8 símbolos são a **fronteira de compatibilidade** da v1. Mudanças aqui exigem
> depreciação em 0.x e só breaking em major.

### 2.2 `app.core.models` — **STABLE** (modelos) / re-export (erros)

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `HashResult` | `@dataclass(frozen=True, slots=True)` | Resultado imutável: `algorithm`, `hexdigest`, `source`, `path`, `size_bytes` |
| `HashSource` | `type` (`Literal["file","text","bytes"]`) | Origem dos dados hasheados |
| `HashError` | exceção | Re-export de `app.core.exceptions.domain` |
| `UnsupportedAlgorithmError` | exceção | Re-export de `app.core.exceptions.domain` |

### 2.3 `app.core.crypto` — **BETA**

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `HashAlgorithm` | `enum.Enum` | Fonte canônica da whitelist |
| `normalize_algorithm(algorithm)` | `HashAlgorithm` | Normaliza `str`/membro; rejeita fora da whitelist |
| `new_hasher(member)` | `_Hasher` | Cria hasher `hashlib` (emite `DeprecationWarning` p/ MD5/SHA1) |
| `safe_compare(actual, expected)` | `bool` | Comparação constante via `hmac.compare_digest` |

> Internamente consumida por `algorithms`; exposta para camadas superiores. Mudanças possíveis
> antes da 1.0 com aviso.

### 2.4 `app.core.exceptions` — **STABLE** (hierarquia)

| Símbolo | Hierarquia |
|---------|------------|
| `EDYShieldError` | raiz da hierarquia |
| `HashError` | → `EDYShieldError` |
| `UnsupportedAlgorithmError` | → `HashError` (atributo `algorithm`) |
| `ValidationError` | → `EDYShieldError` |
| `FilesystemError` | → `EDYShieldError` |

> Hierarquia congelada (ADR-005). Novas exceções só como folhas especializadas.

### 2.5 `app.core.config` — **BETA**

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `Settings` | `@dataclass(frozen=True, slots=True)` | `default_hash_algorithm`, `log_level`, `allowed_root`, `chunk_size`, `encoding` |
| `load_settings()` | `Settings` | Lê `EDY_*` do ambiente com validação de tipos |

> Formato estável, mas campos podem ser adicionados antes da 1.0. Nenhum campo existente será
> removido sem depreciação.

### 2.6 `app.core.filesystem` — **BETA**

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `resolve_safe_path(path, *, allowed_root, strict)` | `Path` | Resolve e valida contenção na raiz |
| `validate_allowed_root(root)` | `Path` | Valida/resolve a raiz permitida |
| `is_within_root(resolved, root)` | `bool` | Testa contenção |
| `ensure_regular_file(target)` | `None` | Rejeita diretórios/arquivos especiais |

> Fronteira de segurança (ARES-QA-001/005/007). Sem assinatura garantida até 1.0, mas sem
> breaking planejado.

### 2.7 `app.core.logging` — **BETA**

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `setup_logging(settings)` | `None` | Configura logger raiz `edy_shield` (idempotente) |
| `get_logger(name)` | `logging.Logger` | Logger filho `edy_shield.<name>` |

### 2.8 `app.core.validators` — **BETA**

| Símbolo | Tipo | Descrição |
|---------|------|-----------|
| `validate_chunk_size(chunk_size)` | `None` | Exige inteiro positivo |
| `validate_expected(expected, algorithm)` | `str` | Valida hex + comprimento por algoritmo |

### 2.9 CLI — **STABLE** (interface de comando)

```
edyshield hash <path> [--algorithm SHA256|SHA1|MD5] [--root DIR]
edyshield verify <path> --expected <HASH> [--algorithm SHA256|SHA1|MD5] [--root DIR]
edyshield --help
edyshield --version            # edyshield 1.1.0
```

Contrato:
- Exit codes: **0** sucesso, **1** erro de domínio/validação.
- Saída em **stdout**: hexdigest (`hash`) ou `OK`/`FAIL` (`verify`).
- Logging em **stderr**.
- `allowed_root` default = diretório pai do arquivo alvo (quando `--root` não informado).

### 2.10 Shims de compatibilidade — **compromisso de backward compat**

| Shim | Re-exporta | Compromisso |
|------|------------|-------------|
| `app.core.models.common` | `HashError`, `UnsupportedAlgorithmError` | Mantido enquanto houver imports externos usando `from app.core.models.common import ...` |
| `app.services.file_utils` | `ensure_regular_file`, `is_within_root`, `resolve_safe_path`, `validate_allowed_root` | Mantido como re-export; **nenhuma lógica nova** deve ser adicionada (vai para o Core) |
| `app.services` | `resolve_safe_path`, `validate_allowed_root` | Mantido como ponto único de import das camadas superiores |

> **Regra:** shims não acumulam lógica nova. Eles só re-exportam da fonte canônica no Core.
> A remoção de um shim só ocorre em major, após depreciação e migração dos consumidores.

### 2.11 Áreas RESERVED

| Área | Status |
|------|--------|
| `app.core.report` | RESERVED — estrutura criada, sem código (roadmap v2.0: relatórios JSON/Markdown) |
| `app.core.utils` | RESERVED — estrutura criada, sem código (só adicionar com uso concreto) |
| `app.ui` | Sem contrato de API — interface web estática (não é biblioteca) |

---

## 3. Política de versionamento semântico

O projeto segue [SemVer](https://semver.org/lang/pt-br/) a partir da 1.0.0:

| Versão | Regra |
|--------|-------|
| **0.x (atual)** | API em desenvolvimento. **Breaking changes são possíveis**, mas: (a) devem ser anunciadas no CHANGELOG; (b) devem ter depreciação/aviso quando viável; (c) nunca sem registro em `docs/API_STABILITY.md`. |
| **1.0** | **Congelamento da API STABLE.** A partir daqui, quebras exigem **major** (1.x → 2.x) com depreciação prévia. Áreas BETA podem congelar parcialmente. |
| **1.x / 2.x** | Minor adiciona features retrocompatíveis; patch corrige bugs sem quebrar contrato. |

**Diretrizes:**
- Adição de símbolo novo em área STABLE → **minor** (ou patch se puramente interna).
- Renome/remoção/mudança de assinatura em área STABLE → **major** (após 1.0) ou depreciação em 0.x.
- Áreas RESERVED não contam para compatibilidade — podem mudar sem versão major.

---

## 4. Rastreabilidade

| Documento | Relação |
|-----------|---------|
| [`CHANGELOG.md`](../CHANGELOG.md) | Registro de mudanças por versão |
| [`THREAT_MODEL.md`](THREAT_MODEL.md) | Riscos e controles da fronteira de segurança |
| [`QA_REPORT.md`](QA_REPORT.md) | Achados ARES-QA-001..024 (origem dos controles citados) |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Arquitetura em camadas e ADRs |

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Contrato de estabilidade · v1.1.0 · Alpha
