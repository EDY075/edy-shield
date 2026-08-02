# 🧭 EDY Shield — Modelo de Ameaças

> Modelo de ameaças formal do **EDY Shield** (Hash Checker v1 / Sprint 2). Descreve as ameaças
> relevantes, seus vetores (mapeados onde aplicável para MITRE ATT&CK), os controles existentes
> e o risco residual aceito. Baseado no relatório [`QA_REPORT.md`](QA_REPORT.md) (ARES,
> ARES-QA-001..024) e na arquitetura [`ARCHITECTURE.md`](ARCHITECTURE.md).

- **Versão:** 1.1.0 · **Data:** 01/08/2026
- **Escopo:** core (hash, paths, validação), CLI, configuração e logging.
- **Fora de escopo:** UI web estática (sem lógica sensível), módulos futuros (v2/v3).

---

## 1. Tabela de ameaças

| # | Ameaça | Vetor | Controle existente | Residual | Referência |
|---|--------|-------|--------------------|----------|------------|
| T01 | **Path traversal / leitura arbitrária** (MITRE **T1552.001** — Unsecured Credentials: Credentials In Files) | `..`, caminhos absolutos fora da raiz, symlinks que escapam; em serviço público (v2/v3) → leitura de `/etc/passwd`, `.env`, SAM | `resolve_safe_path()` resolve (`Path.resolve()`) e valida contenção na raiz via `relative_to`; `..`/absolutos fora/symlink escape → `HashError` genérico | **Baixo em CLI local** (o usuário já acessa os próprios arquivos); **médio-alto se exposto** em API/Streamlit sem `allowed_root` explícito (R3) | ARES-QA-001 |
| T02 | **Symlink escape** | Symlink dentro da raiz apontando para arquivo fora dela | `Path.resolve()` resolve o symlink **antes** da validação `relative_to`; escape → `HashError` | Baixo; 2 testes de symlink skipped no Windows (FS não suporta por padrão), cobertos por design e CI Linux | ARES-QA-001/005/007 |
| T03 | **DoS por arquivo especial** (FIFO/device/socket) | `open()` em FIFO/device bloqueia o processo indefinidamente | `ensure_regular_file()` rejeita não-regulares antes do `open` (`is_dir` → `IsADirectoryError`; não-regular → `HashError`) | TOCTOU entre check e open (janela pequena em CLI local) | ARES-QA-007 |
| T04 | **Algoritmos fracos (MD5/SHA1)** — colisão | Digest colidido em verificação de integridade crítica | Whitelist `HashAlgorithm` + `DeprecationWarning` em runtime (ARES-QA-004); **SHA-256** padrão | Médio **se o usuário optar** por MD5/SHA1; documentado como compat legada não-crítica | ARES-QA-004 |
| T05 | **Timing attack na verificação** (CWE-208) | Medir tempo de comparação `==` para inferir digest | `safe_compare` = `hmac.compare_digest` (tempo constante) | Muito baixo (digest `expected` normalmente público); mitigado por design | ARES-QA-003 |
| T06 | **Injeção de algoritmo** | Nome arbitrário (`sha512`, `md4`, `None`, `int`) alcançando `hashlib.new` | `normalize_algorithm` valida tipo + whitelist antes do `hashlib`; fora da whitelist → `UnsupportedAlgorithmError` (com atributo `algorithm`) | Baixo (whitelist cobre) | ARES-QA-006 |
| T07 | **Fallback silencioso `str` → texto** | Typo de path hasheado como texto → falso "arquivo íntegro" | `_looks_like_path()` + `FileNotFoundError` para string com separador/extensão inexistente; `compute_text` explícito para texto | Baixo; strings com extensão (ex.: `v1.2`, `README`) são tratadas como path por design (R2/ARES-QA-024) | ARES-QA-002/024 |
| T08 | **TOCTOU** (check → open → read) | Arquivo trocado entre checagem de existência/tipo e leitura | Aceito e documentado como trade-off de CLI local no docstring de `_compute_file_impl` | **Médio em serviço concorrente**; hardening planejado (v1.1): `os.open` + `O_NOFOLLOW` + `fstat` no handle + re-verificação | ARES-QA-008/R1/012/019 |
| T09 | **Vazamento de informação em erros** | Mensagens expondo caminhos absolutos → OSINT/reconhecimento | Mensagens usam apenas `target.name` (basename); `HashError` de traversal genérico; `UnsupportedAlgorithmError` ecoa só o nome do algoritmo | Baixo (rebaixado na prática, R4) | ARES-QA-005 |
| T10 | **Exfiltração de conteúdo via log** | Conteúdo do arquivo gravado em log | Política explícita do logger: **nunca** logar conteúdo — apenas hashes e metadados; nunca logar segredos | Baixo (política documentada + revisão ARES) | política `app.core.logging` |
| T11 | **Supply chain** | Dependência maliciosa de terceiros no runtime | Core **zero deps runtime** (ADR-001) — apenas stdlib (`hashlib`, `hmac`, `argparse`, `dataclasses`, `pathlib`, `logging`) | Baixo no runtime; **médio no dev** (dev deps sem pinning — ARES-QA-022) | ARES-QA-022 / ADR-001 |
| T12 | **Entrada malformada (`expected`, `chunk_size`, encoding)** | `expected=None`/não-hex, `chunk_size='1024'`, encoding desconhecido | `validate_expected` (hex + comprimento), `validate_chunk_size` (inteiro positivo), encoding → `ValueError` claro | Baixo (erros de domínio claros, sem traceback bruto) | ARES-QA-009/010/011 |
| T13 | **Abuso de memória (arquivo gigante)** | Arquivo enorme carregado inteiro em memória | Leitura em **chunks** (default 65536 B); `size_bytes` acumulado no loop | Baixo; sem limite máximo de tamanho configurado (limite sugerido em ARES-QA-007) | ARES-QA-007/012 |

---

## 2. Mapeamento MITRE ATT&CK

| Técnica | ID | Cobertura |
|---------|-----|-----------|
| Credentials In Files / Unsecured Credentials | **T1552.001** | Controle primário da T01 (path traversal → leitura arbitrária) |
| (Auxiliar) OWASP Top 10 | A01 (Broken Access Control), A05 (Security Misconfiguration), A07 (CWE-208) | T01, T03, T05 |

---

## 3. Suposições e limites do modelo

1. **CLI local de usuário autorizado** — o modelo assume uso em máquina própria ou autorizada;
   o usuário já tem acesso aos arquivos que pode hashear.
2. **`allowed_root` explícito em exposição pública** — se o core for exposto via Streamlit/API
   (v2/v3), a camada de serviço **deve** exigir `allowed_root` explícito (R3). Na CLI local,
   quando ``--root`` não é informado (ou ``EDY_ALLOWED_ROOT`` não está definido), a raiz
     permitida é o **diretório pai do arquivo alvo** — garantindo contenção sem depender do
     CWD global (ARES-QA-025).
3. **TOCTOU aceito na v1** — janela entre check e `open` é aceitável em CLI local; a camada de
   serviço re-verifica contra fonte imutável ou usa locking (R1).
4. **Sem dados pessoais processados** — o módulo não processa dados pessoais (LGPD/GDPR não
   aplicável neste escopo); apenas hashes de arquivos/textos fornecidos pelo usuário.

---

## 4. Postura de segurança

- 🛂 **Fail-closed em paths:** qualquer caminho que escape a raiz é rejeitado — nunca
  "tolerado" em produção.
- 🧱 **Princípio do menor privilégio:** fronteira única de validação; nenhum `Path.open()`
  direto fora do `app.core.filesystem`.
- 📉 **Superfície mínima:** zero deps runtime; sem execução de código não confiável.
- 🧪 **Testes de segurança contínuos:** 20 testes negativos de segurança (ARES-QA-017) +
  smoke tests manuais na re-review ARES (a–j).

---

## 5. Rastreabilidade

| Documento | Relação |
|-----------|---------|
| [`QA_REPORT.md`](QA_REPORT.md) | Achados ARES-QA-001..024 — origem de cada controle citado |
| [`API_STABILITY.md`](API_STABILITY.md) | Contrato da API pública (estabilidade dos símbolos) |
| [`SECURITY.md`](../SECURITY.md) | Política de segurança + como reportar vulnerabilidades |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Arquitetura em camadas e princípios segurança-first |

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Modelo de ameaças · v1.1.0 · Baseado no QA_REPORT.md (ARES, ARES-QA-001..024)
