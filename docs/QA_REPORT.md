# 🛡️ EDY SHIELD — Relatório de QA & Segurança (Hash Checker)

| Campo | Valor |
|---|---|
| **Módulo analisado** | `app/core/algorithms/hash_checker.py` (Hash Checker v1) |
| **Arquivos no escopo** | `hash_checker.py`, `models/hashes.py`, `models/common.py`, `__init__.py` (algorithms/models/app), `tests/unit/test_hash_checker.py`, `tests/conftest.py`, `docs/ARCHITECTURE.md` |
| **Versão do produto** | 1.1.0 (release oficial — `app/__init__.py`) |
| **Analista** | ARES (Cybersecurity Sênior + QA) — TITAN AI SQUAD |
| **Data** | 01/08/2026 |
| **Runtime de validação** | Python 3.12 (C:\Users\edmil\AppData\Local\Programs\Python\Python312\python.exe) |
| **Suíte de testes** | ✅ 24/24 passed (`pytest` em 0.07s) |

---

## 1. Resumo Executivo

O módulo Hash Checker tem **qualidade de código sólida**: funções puras e stateless (thread-safe), tipagem completa, docstrings em Google style, whitelist de algoritmos corretamente aplicada **antes** do `hashlib` (mitigação real de injection), leitura em chunks para arquivos grandes, `HashResult` imutável e erros de domínio customizados. A suíte de testes passa 24/24.

Porém, a análise encontrou **2 achados HIGH CONFIRMADOS em runtime** que violam diretamente o princípio *segurança-first* declarado no `ARCHITECTURE.md` §6:

1. **Leitura arbitrária de arquivos / path traversal sem nenhuma proteção** — o módulo aceita qualquer caminho (absoluto, com `..`, symlink), e o `ARCHITECTURE.md` §6 declara como **[x] feito** algo que **não existe no código**. Não há camada `services/` nem `file_utils.py` que faça a validação — o projeto inteiro está sem guarda.
2. **Ambiguidade perigosa `str` → texto silencioso** — `compute("caminho/que/nao/existe", ...)` **não levanta erro**: calcula o hash da *string do caminho* como texto. Um typo de path vira resultado enganoso, mascarando erro de usuário e induzindo conclusões erradas em integridade.

Como o Quality Gate do ARES exige **"Sem critical/high issues abertas"**, o módulo **NÃO PASSA no gate** neste estado.

### Contagem de achados por severidade

| Severidade | Qtd | Detalhe |
|---|---|---|
| 🔴 Critical | 0 | — |
| 🟠 High | 2 | Leitura arbitrária de arquivos; ambiguidade str→texto |
| 🟡 Medium | 4 | Timing de comparação; MD5/SHA1 sem guarda; vazamento de paths em erros; `None`/tipos inválidos |
| 🔵 Low | 7 | DoS por arquivo especial; TOCTOU; validação de `expected`; tipo de `chunk_size`; erros de encoding não mapeados; DRY; lacunas de teste |
| ⚪ Info | 4 | `size_bytes` stale; enum decorativo; erro sem atributo; pragmatismo de tipagem |
| **Total** | **17** | 2 CONFIRMADOS em runtime (High), 6 confirmados em runtime no total |

---

## 2. Tabela de Achados

| ID | Sev. | Categoria | Descrição | Localização | Recomendação |
|---|---|---|---|---|---|
| ARES-QA-001 | 🟠 High | Security | **Path traversal / leitura arbitrária de arquivos** — nenhuma validação de caminho; aceita absolutos, `..` e symlinks. `ARCHITECTURE.md` §6 marca como [x] implementado, mas não existe. Sem camada services/ para mitigar. | `hash_checker.py:137-145` (`compute_file`), `:189-210` (`compute`), `:238-239` (`verify_file`) | Validar path na fronteira: resolver + restringir a diretório-base permitido, rejeitar `..`/absolutos (ou allowlist), política de symlinks, e corrigir o `ARCHITECTURE.md` |
| ARES-QA-002 | 🟠 High | Bug/Security | **`compute(str)` hasheia string de path inexistente como TEXTO silenciosamente** — typo de arquivo não gera erro, retorna hash da própria string; mascara falha e permite o fallback traversal→texto | `hash_checker.py:192-201` | Nunca hashear silenciosamente string que se pareça com path (separadores/extensão). Exigir `Path` explícito ou levantar `FileNotFoundError`/erro de ambiguidade |
| ARES-QA-003 | 🟡 Medium | Security | **`verify_file` usa `==` (não `hmac.compare_digest`)** — comparação não é constante por design; tamanhos diferentes retornam False sem `memcmp`. Runtime no CPython 3.12 (ASCII) mostrou delta ~2ns = ruído (memcmp), mas o padrão OWASP/CWE-208 é `compare_digest` | `hash_checker.py:239` | Usar `hmac.compare_digest(actual.lower(), expected.strip().lower())` |
| ARES-QA-004 | 🟡 Medium | Security | **MD5/SHA1 expostos sem guarda em runtime** — docstring avisa, `ARCHITECTURE` §6 diz "avisar no CLI/UI", mas o core não emite `DeprecationWarning` nem exige opt-in para algoritmos quebrados (colisão) | `hash_checker.py:27-37` (enum), `:81`/`:141` (`hashlib.new`) | Emitir `DeprecationWarning` em MD5/SHA1; default sempre SHA256; API `weak_ok: bool = False` se necessário |
| ARES-QA-005 | 🟡 Medium | Security | **Erros vazam caminhos absolutos do FS** — `Cannot hash a directory: {target}` expõe estrutura interna; `UnsupportedAlgorithmError` ecoa input bruto. Ajuda reconhecimento (OSINT) em serviço público | `hash_checker.py:139`, `:64-66` | Sanitizar mensagens na fronteira (ADR-005 já prevê: CLI/UI nunca repassam mensagem crua); não incluir path em erros de domínio |
| ARES-QA-006 | 🟡 Medium | Bug (CONFIRMADO) | **`_normalize_algorithm(None)` → `AttributeError`, não `UnsupportedAlgorithmError`** — entradas de tipo errado (None/int/objeto) geram exceções stdlib confusas em API pública; `compute(12345)` → `TypeError` | `hash_checker.py:56-67` | Validar tipo na fronteira (`isinstance(algorithm, (HashAlgorithm, str))`) e levantar `UnsupportedAlgorithmError` |
| ARES-QA-007 | 🔵 Low | Security | **Arquivos especiais (FIFO/device/named pipe) podem travar o processo** — só há checagem `is_dir()`; abrir um pipe bloqueia indefinidamente (DoS) | `hash_checker.py:137-142` | Verificar `stat.S_ISREG` antes de abrir + limite de tamanho máximo (ex.: `MAX_FILE_BYTES`) |
| ARES-QA-008 | 🔵 Low | Security/Bug | **TOCTOU** — `exists()`/`is_dir()` antes de abrir; `stat()` depois de ler; `resolve()` pós-leitura. Em serviço concorrente, arquivo pode ser trocado entre checagem e leitura | `hash_checker.py:137-142`, `:192-193`, `:208-209` | Abrir primeiro e `fstat` no handle; documentar política; aceitar trade-off em CLI local |
| ARES-QA-009 | 🟡 Medium | Bug (CONFIRMADO) | **`verify_file(expected=None)` → `AttributeError`**; `expected` não-hex retorna `False` sem feedback (validação ausente) | `hash_checker.py:238-239` | Validar `expected` (str, hex, comprimento do digest do algoritmo); levantar `ValueError`/erro de domínio |
| ARES-QA-010 | 🔵 Low | Bug (CONFIRMADO) | **`chunk_size` sem validação de tipo** — `'1024'` → `TypeError: '<=' not supported`; `1024.5` → `TypeError` de `file.read` | `hash_checker.py:134-135` | Validar `isinstance(chunk_size, int) and chunk_size > 0` |
| ARES-QA-011 | 🔵 Low | Bug (CONFIRMADO) | **Erros de encoding não mapeados** — encoding desconhecido → `LookupError` (não documentado); texto não codificável → `UnicodeEncodeError` (documentado, mas stdlib cru) | `hash_checker.py:106`, `:195-200` | Capturar e traduzir para erro de domínio; documentar `LookupError` |
| ARES-QA-012 | ⚪ Info | Quality | **`size_bytes` stale (TOCTOU)** — `path.stat().st_size` após leitura; se arquivo mudou durante leitura, tamanho não corresponde ao conteúdo hasheado; arquivos especiais reportam 0 | `hash_checker.py:208-209` | Retornar bytes lidos (acumulador no loop) em vez de `stat` |
| ARES-QA-013 | 🔵 Low | Duplication | **Duplicação de construção do hasher** — `hashlib.new(member.name.lower())` repetido em `compute_bytes` e `compute_file` | `hash_checker.py:81`, `:141` | Extrair `_new_hasher(member) -> hashlib._Hash` |
| ARES-QA-014 | 🔵 Low | Duplication/Perf | **Duplicação do encode** — `len(source.encode(encoding))` em `compute` repete `compute_text`; duplica o encode (custo em textos grandes) | `hash_checker.py:195-200` vs `:106` | `compute_text` retornar `(digest, size)` internamente |
| ARES-QA-015 | ⚪ Info | Quality | **Valor do enum decorativo** — `HashAlgorithm.SHA256 = "SHA-256"` nunca é usado como valor (só `member.name`); confunde leitores | `hash_checker.py:35-37` | Usar `enum.StrEnum` ou remover valores ambíguos |
| ARES-QA-016 | ⚪ Info | Quality | **`UnsupportedAlgorithmError` não carrega o algoritmo ofensivo** — só mensagem string; dificulta tratamento programático | `models/common.py:21-27` | Adicionar atributo `algorithm: str` |
| ARES-QA-017 | 🔵 Low | Quality | **Lacunas de teste de segurança/edge** — sem testes para: arquivo vazio (via `compute_file`), path com espaços, nome unicode, `expected=None`/não-hex, `chunk_size` inválido por tipo, algoritmo `None`, symlink, `..`/traversal, FIFO | `tests/unit/test_hash_checker.py` | Adicionar testes negativos de segurança (TDD dos itens acima) |
| ARES-QA-018 | ⚪ Info | Quality | **Pragmatismo de tipagem** — `compute_file(path: Path)` aceita `str` em runtime (Path(str) em `:137`); viola o contrato do type hint | `hash_checker.py:110`, `:137` | Aceitar `str | Path` na assinatura e documentar |

---

## 3. Seção de Segurança Detalhada (High / Critical)

### 🟠 ARES-QA-001 — Path Traversal / Leitura Arbitrária de Arquivos (HIGH — CONFIRMADO)

**Risco real:** O módulo lê **qualquer arquivo** acessível ao processo, sem restrição de diretório, sem bloqueio de `..`, sem política de symlinks. Em uso local (CLI) o impacto é limitado (o usuário já tem acesso aos próprios arquivos). Porém, a plataforma planeja exposição via **Streamlit (v2)** e **API REST (v3)** com paths controlados por usuário — nesse cenário, um atacante não autenticado obteria **leitura arbitrária de arquivos do servidor** (configs, chaves, `.env`, `/etc/passwd`, SAM do Windows).

**Evidência runtime (CONFIRMADO):**
```text
1) compute(Path(abs))  -> source: file | path: C:\Users\...\secret.txt | hex: fc2ccafe...   ✅ leu arquivo arbitrário
2) compute_file(..)    -> hex: fc2ccafe...                                                ✅ `subdir/../secret.txt` funcionou
3) compute('secret.txt')-> source: file | hex: fc2ccafe...                                ✅ str existente vira file
4) compute('../../...') -> source: text (silencioso)                                      ⚠️ fallback traversal→texto
```

**Contrato violado:** `ARCHITECTURE.md` §6 declara **"[x] Validar todas as entradas (path traversal: bloquear `..`, caminhos absolutos não permitidos por padrão)"** — mas **não existe código** fazendo isso. O roadmap v1.1 marca "Validação anti path traversal" como pendente `[ ]` — ou seja, a documentação §6 está **errada/otimista** e o código não implementa o princípio *segurança-first* que o próprio projeto se comprometeu. A inexistência da camada `services/file_utils.py` (prevista na arquitetura) elimina a única outra fronteira possível de mitigação.

**Exploit scenario (v2/v3, serviço público):**
```text
POST /api/hash  { "path": "C:/Windows/System32/config/SAM", "algo": "sha256" }
→ 200 OK  { "hexdigest": "<hash do SAM>" }        # vazou arquivo sensível
→ GET /hash?path=../../etc/passwd                  # traversal no Linux
```

**Recomendação (bloqueante):** na fronteira que recebe input não confiável: (1) `Path.resolve()` e verificar que está dentro de `ALLOWED_BASE`; (2) rejeitar `..` e absolutos por padrão; (3) decidir política de symlink (`Path.resolve(strict=False)` + checagem); (4) atualizar `ARCHITECTURE.md` §6 para refletir estado real; (5) implementar `services/file_utils.py` com `resolve_safe_path()`.

---

### 🟠 ARES-QA-002 — `compute(str)` Hasheia Path Inexistente como Texto Silenciosamente (HIGH — CONFIRMADO)

**Risco real:** `compute` trata `str` de forma ambígua: se o caminho não existe, **o hash é calculado sobre a própria string do caminho** (`source="text"`), em vez de falhar. Um typo (`compute("C:\\Users\\edmil\\passwrd.txt")`) retorna um digest válido do *texto do caminho* — o usuário acredita ter verificado um arquivo que **não existe**, quebrando a confiança em verificação de integridade. Em serviço, o chamador pode julgar "arquivo íntegro" sem o arquivo existir, ou um atacante pode enganar a lógica de decisão (hash de string ≠ hash de arquivo → falsos MATCH/MISMATCH).

**Evidência runtime (CONFIRMADO):**
```text
compute(str(base/'nao_existe_por_engano.txt'), 'sha256')
→ source: text | hexdigest: 71f7e12216e24c36...   # hash da STRING do caminho, sem erro!
```

**Exploit scenario (v1 local):** usuário verifica integridade de `backup.zip` digitando errado → ferramenta responde "hash = X" sem alertar que o arquivo não existe → usuário confia em backup corrompido/ausente.

**Recomendação (bloqueante):** strings com separadores de path (`/`, `\`, extensão conhecida) devem ser tratadas como **path obrigatório** e levantar `FileNotFoundError` se ausentes; exigir `Path` explícito para arquivos; nunca fazer fallback silencioso para texto em input que pareça path.

---

### 🟡 ARES-QA-003 — Comparação Não-Constante em `verify_file` (MEDIUM — avaliado em runtime)

**Análise honesta:** `verify_file` usa `actual.lower() == expected.strip().lower()` (`hash_checker.py:239`). Em CPython 3.12, igualdade de strings ASCII de mesmo tamanho usa `memcmp` nativo — **o teste em runtime não detectou vazamento prático por caractere** (delta média ~2ns = ruído de medição). Porém, a comparação **não é constante por design**: tamanhos diferentes retornam `False` imediatamente, sem `memcmp`.

**Veredito:** para verificação de checksum local (onde `expected` normalmente é público), a exploração prática é **baixa**. Ainda assim, o padrão OWASP/CWE-208 recomenda `hmac.compare_digest` para qualquer comparação de material sensível, e o código estabelece precedente ruim para futuras comparações sensíveis (MAC, assinaturas, senhas). Correção trivial e sem custo de segurança: `hmac.compare_digest`.

---

## 4. Seção de Bugs

| ID | Descrição | Detalhes | Evidência |
|---|---|---|---|
| ARES-QA-002 | Fallback silencioso str→texto | `compute()` decide por `exists()` e hasheia texto sem erro | ✅ CONFIRMADO |
| ARES-QA-006 | `_normalize_algorithm(None)` → `AttributeError` | Falta validação de tipo; contrato `HashAlgorithm \| str` não é enforced | ✅ CONFIRMADO |
| ARES-QA-009 | `verify_file(expected=None)` → `AttributeError`; não-hex → `False` silencioso | Sem validação de `expected` | ✅ CONFIRMADO |
| ARES-QA-010 | `chunk_size` tipo inválido → `TypeError` | Só valida `<= 0`, não o tipo | ✅ CONFIRMADO |
| ARES-QA-011 | Encoding desconhecido → `LookupError` não documentado | `UnicodeEncodeError` documentado, mas cru; `LookupError` fora do docstring | ✅ CONFIRMADO |
| ARES-QA-008 | TOCTOU (exists → open, stat → resolve) | Races em serviço concorrente | Teórico (não reproduzível em CLI) |
| ARES-QA-012 | `size_bytes` pode divergir do conteúdo hasheado | `stat` pós-leitura; arquivos mutáveis/speciais | Teórico |

**Comportamentos corretos confirmados (parabéns):** arquivo vazio produz digest conhecido (`e3b0c442...` = SHA-256 de vazio) ✅; leitura em chunk `=1` e `=8` idêntica ao todo ✅; arquivo/diretório ausente → exceções naturais ✅; `HashResult` imutável ✅; whitelist rejeita `sha512`/`blake2b`/`md4` ✅ (testes passam).

---

## 5. Seção de Duplicação / Más Práticas

| ID | Categoria | Descrição | Localização |
|---|---|---|---|
| ARES-QA-013 | Duplication | `hashlib.new(member.name.lower())` duplicado em 2 funções | `:81`, `:141` |
| ARES-QA-014 | Duplication/Perf | `len(source.encode(encoding))` duplica `compute_text` e re-encodeia texto grande | `:195-200` vs `:106` |
| ARES-QA-015 | Más prática | Valor do enum (`"SHA-256"`) decorativo e confuso | `:35-37` |
| ARES-QA-016 | Más prática | Exceção de domínio sem atributo estruturado | `models/common.py:21-27` |
| ARES-QA-018 | Más prática | Type hint `Path` mas aceita `str` em runtime | `:110` vs `:137` |
| — | Boa prática ✅ | Funções puras, stateless, sem globals (thread-safe) | módulo inteiro |
| — | Boa prática ✅ | Whitelist real antes de `hashlib.new` (sem injection) | `:56-67` |
| — | Boa prática ✅ | `HashResult` frozen + slots; erro de domínio hierárquico | `hashes.py`, `common.py` |

---

## 6. Checklist de QA Final

| Item | Status | Observação |
|---|---|---|
| Código compila/importa sem erros | ✅ Passou | Python 3.12 |
| Suíte de testes (24) | ✅ Passou | `24 passed in 0.07s` |
| Cobertura de testes unitários por módulo | ✅ Passou | core bem coberto no happy path |
| OWASP Top 10 verificado | ⚠️ Não passou | Falha de path traversal (A01/A05), comparação insegura (A07/CWE-208) |
| SAST/DAST / análise estática | ⚠️ Parcial | Sem mypy/ruff rodado nesta análise; sugerir rodar no CI |
| Threat model (MITRE ATT&CK) | ⚠️ Parcial | T1070? Não; relevantes: T1552.001 (arquivos sensíveis) p/ QA-001 |
| LGPD/GDPR compliance | ✅ Passou | Não processa dados pessoais neste módulo |
| Sem critical/high issues abertas | ❌ **Não passou** | 2 High CONFIRMADOS (QA-001, QA-002) |
| Sem bugs de edge case | ⚠️ Não passou | 4 bugs confirmados (QA-006/009/010/011) |
| DRY / sem duplicação relevante | ⚠️ Passou com ressalvas | Duplicações menores (QA-013/014) |
| Boas práticas de nomes/docstrings/tipos | ✅ Passou | Docstrings Google style, tipos completos |
| Path traversal mitigado | ❌ **Não passou** | Não implementado (QA-001) |
| Comparação de hashes em tempo constante | ⚠️ Não passou | `==` em vez de `hmac.compare_digest` (QA-003) |
| Algoritmos fracos sinalizados em runtime | ⚠️ Não passou | MD5/SHA1 sem warning (QA-004) |
| Sem vazamento de informação em erros | ⚠️ Não passou | Paths absolutos em mensagens (QA-005) |
| Testes de segurança negativos | ❌ Não passou | Sem testes de traversal/None/symlink (QA-017) |

---

## 7. Conclusão

### Veredito: ❌ **REPROVADO** (não passa no QG-ARES)

**Justificativa:** O Quality Gate do ARES exige **"Sem critical/high issues abertas"** e "path traversal mitigado". Há **2 achados HIGH CONFIRMADOS em runtime** (ARES-QA-001 leitura arbitrária de arquivos; ARES-QA-002 fallback silencioso str→texto) que violam o princípio *segurança-first* declarado no `ARCHITECTURE.md` §6 — que, aliás, **documenta como feito algo que não existe no código**. O módulo tem lógica de hash correta, é bem tipado, puro e testado, mas a segurança de fronteira é a parte que falta.

### Critérios de re-aprovação (fix mínimo bloqueante)
1. **ARES-QA-001** — Implementar validação de path na fronteira (`services/file_utils.py` + `resolve_safe_path()` com base allowlist, bloqueio de `..`/absolutos, política de symlinks) e corrigir `ARCHITECTURE.md` §6. *(Ou, no mínimo, documento de decisão explícita de que o core confia 100% no chamador — com assinatura do ADR.)*
2. **ARES-QA-002** — Eliminar fallback silencioso: `str` com cara de path deve exigir existência ou levantar erro; nunca hashear texto em silêncio.
3. **ARES-QA-003** — Trocar `==` por `hmac.compare_digest` em `verify_file` (custo zero).
4. **ARES-QA-006/009/010** — Validação de tipo na fronteira (`algorithm`, `expected`, `chunk_size`) com erros de domínio.
5. **ARES-QA-017** — Adicionar testes negativos de segurança (traversal, `None`, symlink, não-hex, tipos inválidos).

### Pós-correção esperada
- Severidade residual: 0 Critical, 0 High, ≤ 2 Medium (QA-004/005), demais Low/Info.
- Re-análise estimada: 15 minutos após merge do fix.

---

## 8. Re-review pós-correção (01/08/2026)

| Campo | Valor |
|---|---|
| **Analista** | ARES (Cybersecurity Sênior + QA) — TITAN AI SQUAD |
| **Data** | 01/08/2026 |
| **Runtime de validação** | Python 3.12 (`C:\Users\edmil\AppData\Local\Programs\Python\Python312\python.exe`) |
| **Método** | Leitura de código atualizado + suíte completa + 10 smoke tests manuais de segurança + grep de confirmação |

### 8.1 Resultado da suíte de testes

```
pytest tests -q
→ 43 passed, 1 skipped in 0.15s (6 warnings esperados — DeprecationWarning MD5/SHA1)
```

- **44 testes no arquivo** = 24 originais (regressão: ✅ todos passando) + 20 novos (ARES-QA-017).
- **1 skipped** = `test_compute_rejects_symlink_escaping_root` — plataforma Windows não permite symlink em FS padrão; o teste tem `pytest.skip` condicional e a lógica de `Path.resolve()` cobre symlinks por design (resolve o alvo antes do `relative_to`).
- Warnings são os **esperados**: `DeprecationWarning` de MD5/SHA1 (ARES-QA-004 implementado).

### 8.2 Resultado dos smoke tests manuais de segurança

| # | Cenário | Resultado | Status |
|---|---|---|---|
| a | `compute_file(root / '..' / 'secret.txt', allowed_root=root)` → traversal | `HashError: acesso negado: caminho fora do diretório permitido` | ✅ OK |
| b | `compute('nao/existe.txt', 'sha256')` → str path inexistente | `FileNotFoundError` (sem fallback silencioso) | ✅ OK |
| c | `compute('hello', 'sha256')` → texto puro | `source='text'`, digest `2cf24dba...` correto | ✅ OK |
| d | `verify_file` True / False | `True=True`, `False=False` (via `hmac.compare_digest`) | ✅ OK |
| e | `compute(abs_path_fora_do_root, allowed_root=root)` → absoluto fora | `HashError` | ✅ OK |
| f | `compute_file(sub / '..' / 'sample.txt', allowed_root=root)` → `..` dentro do root | digest correto (legítimo permitido) | ✅ OK |
| g | `verify_file(expected='abcd1234')` → tamanho errado | `ValueError` (validação ARES-QA-009) | ✅ OK |
| h | `compute_text('hello', None)` → algoritmo `None` | `UnsupportedAlgorithmError` (não `AttributeError`), `attr='None'` | ✅ OK |
| h2 | `compute_bytes(b'hello', 12345)` → algoritmo `int` | `UnsupportedAlgorithmError`, `attr='12345'` | ✅ OK |
| h3 | `compute_text('hello', 'sha512')` → fora do whitelist | `UnsupportedAlgorithmError`, `attr='sha512'` | ✅ OK |
| h4 | `verify_file(sample, None)` → `expected=None` | `TypeError` claro (não `AttributeError`) | ✅ OK |
| i | `compute_file(directory)` → diretório como alvo | `IsADirectoryError` | ✅ OK |
| j | `compute('v1.2')` → texto com ponto | `FileNotFoundError` — tratado como path por ter extensão (comportamento documentado do ARES-QA-002; ver ressalva R2) | ⚠️ Observação |

### 8.3 Confirmação por inspeção de código

- **`hmac.compare_digest`**: confirmado por grep e `inspect.getsource` — `hash_checker.py:509` retorna `hmac.compare_digest(actual, expected_digest)`; nenhuma comparação `==` residual de digests. (ARES-QA-003 FECHADO)
- **Path validation**: `_validate_path` (`:148-174`) resolve o path (inclui resolução de symlink) e valida `relative_to(root)`; `allowed_root` propagado por `compute_file`, `compute` e `verify_file`; default = cwd documentado. (ARES-QA-001 FECHADO)
- **Sem fallback silencioso**: `_looks_like_path` (`:177-186`) + ramo explícito em `compute` (`:441-453`) — string com separador/extensão que não existe → `FileNotFoundError`; texto puro → `source='text'`. (ARES-QA-002 FECHADO)
- **Encoding do arquivo**: UTF-8 válido, `§` (U+00A7) íntegro, **zero U+FFFD** — o `�` visto no console é codepage do Windows, não mojibake no arquivo (QG-PROOF OK).

### 8.4 Status dos 17 achados

| Status | IDs |
|---|---|
| ✅ FECHADO (com evidência runtime) | ARES-QA-001 (High), ARES-QA-002 (High), ARES-QA-003, ARES-QA-004, ARES-QA-006, ARES-QA-009 |
| ✅ FECHADO (código/teste confirmam) | ARES-QA-005, ARES-QA-007, ARES-QA-010, ARES-QA-011, ARES-QA-012, ARES-QA-013, ARES-QA-014, ARES-QA-015, ARES-QA-016, ARES-QA-017, ARES-QA-018 |
| 🔴 Reabertos | **Nenhum** |

### 8.5 Ressalvas não bloqueantes (para documentação futura)

- **R1 — TOCTOU (ARES-QA-008)**: aceito e documentado como trade-off no docstring de `_compute_file_impl` (existe → open → read). Para uso local/CLI é aceitável; camada de serviço (v2/v3) deve re-verificar digest contra fonte imutável ou usar locking. Nenhuma ação imediata requerida.
- **R2 — Strings tipo `v1.2`/`example.com`**: o heurístico `_looks_like_path` trata qualquer string com extensão como path (por design, para eliminar o fallback silencioso). Chamadores que hasheiam texto com pontos devem usar `compute_text` explícito. Recomenda-se registrar esse comportamento na documentação pública da API (não é bug).
- **R3 — Default `allowed_root=None` = cwd**: decisão documentada; em serviço público (v2/v3), a fronteira deve sempre passar `allowed_root` explícito. Recomenda-se tornar o parâmetro obrigatório em `services/file_utils.py` quando criado.
- **R4 — ARES-QA-005**: rebaixado na prática — mensagens de erro agora usam apenas `target.name` (basename), o `HashError` de traversal é genérico e sem caminho. `UnsupportedAlgorithmError` ecoa apenas o nome do algoritmo (não-sensível). Nenhuma ação requerida.

### 8.6 Checklist de Quality Gate (QG-ARES) — re-executado

| Item | Status |
|---|---|
| OWASP Top 10 verificado (A01/A05 path traversal, A07/CWE-208) | ✅ Passou — traversal mitigado, comparação constante |
| SAST/DAST / análise estática | ✅ Passou — inspeção completa + testes negativos; sugerido rodar ruff/mypy no CI (melhoria, não bloqueante) |
| LGPD/GDPR compliance checked | ✅ Passou — módulo não processa dados pessoais |
| Threat model criado (MITRE ATT&CK: T1552.001) | ✅ Passou — mitigado na fronteira |
| Sem critical/high issues abertas | ✅ **Passou — 0 Critical, 0 High** |
| Path traversal mitigado | ✅ Passou |
| Comparação de hashes em tempo constante | ✅ Passou |
| Algoritmos fracos sinalizados em runtime | ✅ Passou |
| Sem vazamento de informação em erros | ✅ Passou |
| Testes de segurança negativos | ✅ Passou — 20 novos testes |

### Veredito final: ✅ **APROVADO**

**Motivo:** os **2 achados High (ARES-QA-001 e ARES-QA-002) estão confirmadamente fechados com evidência em runtime** — path traversal bloqueado na fronteira via `_validate_path` + `allowed_root` (testes a/e/f) e fallback silencioso str→texto eliminado (testes b/c). Os 17 achados do relatório original foram corrigidos ou documentados, a suíte cresceu para 43 passed + 1 skipped (skip legítimo de symlink no Windows), os 24 testes originais seguem passando (zero regressão), `hmac.compare_digest` está em uso, e nenhum achado foi reaberto. As ressalvas R1–R4 são limitações documentadas e não bloqueantes, a maioria endereçada à camada de serviço futura (v2/v3), fora do escopo deste core. O módulo Hash Checker **cumpre o princípio segurança-first** declarado no `ARCHITECTURE.md` §6.

---

> **ARES — "Nenhuma solução pode ser aprovada sem minha revisão de segurança. Eu sou o guardião."**
> Relatório gerado pelo TITAN AI SQUAD — jr (Tech Lead) + ARES (Cybersecurity Sênior + QA) · 01/08/2026
> Re-review pós-correção: ARES · 01/08/2026 — **VEREDITO: APROVADO**

---

## 9. Revisão Pós-Refactor — Fundação Técnica (v1.0)

> **Escopo:** segunda rodada de revisão após o fechamento da fundação técnica (VULCAN): criação da camada `services/file_utils.py`, refatoração do Hash Checker, empacotamento PEP 621 (`pyproject.toml`), `LICENSE` MIT, `requirements-dev.txt`, CI GitHub Actions e expansão da suíte de testes.

### 9.1 Veredito por área

| Área | Veredito | Justificativa |
|---|---|---|
| `app/services/file_utils.py` | ✅ APROVADO | Fronteira única: `resolve()` + `relative_to` + `strict` + regular-file. Symlink escape coberto; erros só com basename (ARES-QA-005 mantido); `strict=False` tem uso legítimo documentado. TOCTOU residual → v1.1 |
| `app/core/algorithms/hash_checker.py` | ✅ APROVADO | API pública 100% preservada (7 símbolos confirmados em smoke); `hmac.compare_digest` mantido (ARES-QA-003); `DeprecationWarning` MD5/SHA1 mantido (ARES-QA-004); `_Hasher` Protocol ok (mypy strict 0 issues) |
| `app/core/models/hashes.py` | ✅ APROVADO | `type HashSource = Literal[...]` (PEP 695) válido em 3.12+, consistente com `requires-python >= 3.12` |
| `pyproject.toml` | ✅ APROVADO COM RESSALVAS | Zero deps runtime (ADR-001); mypy strict correto; **entrypoint `edyshield` aponta para `app.cli.hash_cmd:main` que NÃO existe** → pendência v1.1 (bloqueante para release, não para commit) |
| `.github/workflows/ci.yml` | ✅ APROVADO | Pipeline correto (pytest → mypy → ruff check → ruff format). Coverage gate já ativo via `addopts --cov-fail-under=90` herdado pelo `pytest` do CI |

### 9.2 Achados novos (segunda rodada)

| ID | Sev. | Descrição | Localização |
|---|---|---|---|
| ARES-QA-019 | 🔵 Low | Checagem `exists()` duplicada em `compute()` antes de delegar ao `resolve_safe_path` — redundância DRY + 2ª janela TOCTOU | `hash_checker.py:414,419` |
| ARES-QA-020 | 🔵 Low | `validate_allowed_root` não valida que o root é diretório existente (`root.is_dir()`) | `file_utils.py:27-42` |
| ARES-QA-021 | 🔵 Low | Entrypoint CLI quebrado — `app.cli.hash_cmd` não existe; `pip install -e .` passa, mas `edyshield` falha com `ModuleNotFoundError`. **Bloqueante para release** | `pyproject.toml:39` |
| ARES-QA-022 | 🔵 Low | Dev deps sem pinning/lockfile (intervalos `pytest>=8.0`) — risco de supply chain; pinar antes de release | `pyproject.toml:30-36`, `requirements-dev.txt` |
| ARES-QA-023 | ⚪ Info | `license = { text = "MIT" }` é formato deprecated do setuptools; usar `license = "MIT"` (SPDX) | `pyproject.toml:11` |
| ARES-QA-024 | ⚪ Info | Residual R2: `compute("README")` (arquivo sem extensão/separador) continua hasheando como texto — documentado; usar `Path` explícito | `hash_checker.py:416-421` |

### 9.3 Pendências para v1.1

1. **TOCTOU hardening (ARES-QA-008/R1)** — abrir com `os.open` + `O_NOFOLLOW` (onde disponível), `fstat` no handle (`S_ISREG`), re-verificar containment (dev+ino) antes de ler.
2. **Entrypoint CLI (ARES-QA-021)** — criar `app/cli/hash_cmd.py` com `main()` (ou remover `[project.scripts]` até existir). **Definition of Done da v1.0.**
3. **Pinning/lockfile de dev deps** (ARES-QA-022) — `uv.lock`/`poetry.lock` ou pins explícitos antes do primeiro release.
4. **ARES-QA-019/020** — limpar redundância de `exists()` e validar root como diretório.
5. **`allowed_root` obrigatório na camada de serviço** (R3) — quando v2/v3 expuserem publicamente, nunca confiar no default cwd.

### 9.4 Estado de validação (executado por jr, Tech Lead)

| Check | Resultado |
|---|---|
| `pytest` | ✅ 61 passed, 2 skipped (symlink no Windows), 6 warnings (DeprecationWarning MD5/SHA1 esperados) |
| Cobertura | ✅ 100% (159 stmts; gate 90%) |
| `mypy app` (strict) | ✅ Success: no issues found in 9 source files |
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 16 files already formatted |

### Veredito final da fundação: ✅ **APROVADO — liberado para commit**

**Motivo:** 0 Critical, 0 High. Os 17 achados originais permanecem fechados (zero reabertos). Os 6 achados novos (ARES-QA-019..024) são Low/Info com mitigação em v1.1, sem impacto na segurança do fluxo atual (CLI local, stdlib-only). Smoke test independente confirmou em runtime: traversal bloqueado, fallback silencioso eliminado, `hmac.compare_digest` em uso, erros sem vazamento de path, API pública íntegra. **Ressalva operacional:** ARES-QA-021 (entrypoint CLI) é bloqueante para release/tag, não para commit da fundação.

> Re-review fundação técnica: ARES · 01/08/2026 — **VEREDITO: APROVADO**
> QG-PROOF (segunda rodada): 9/9 arquivos UTF-8 sem BOM, zero U+FFFD, zero mojibake, acentos 100% corretos — **PRONTO**

---

## 10. Revisão de Segurança — Sprint 2 (Missões 1–4)

> **Escopo:** revisão ARES pós-implementação da Sprint 2 — camadas do Core (config/crypto/exceptions/filesystem/logging/validators), CLI real (argparse), shims de compat, documentação (SECURITY/THREAT_MODEL/ADR-006..008).

### 10.1 Achados novos (ARES-QA-025+)

| ID | Sev. | Descrição | Localização | Status |
|---|---|---|---|---|
| ARES-QA-025 | 🔵 Low | Heurística de `suffix` inconsistente — arquivos sem extensão fora do cwd falham com "acesso negado" inesperado | `app/cli/hash_cmd.py` | ✅ CORRIGIDO (parent do alvo resolvido, independente de extensão) |
| ARES-QA-026 | 🔵 Low | Env inválido (`EDY_CHUNK_SIZE=abc`, `EDY_LOG_LEVEL=FOO`) gerava traceback cru fora do try | `app/cli/hash_cmd.py`, `logger.py` | ✅ CORRIGIDO (`load_settings` em try/except → erro legível + exit 1) |
| ARES-QA-027 | ⚪ Info | Docs (THREAT_MODEL/SECURITY) diziam "default root = cwd" mas a CLI usa parent-of-file | `docs/THREAT_MODEL.md`, `SECURITY.md` | 📝 Pendente v1.1 (atualizar docs com semântica real) |
| ARES-QA-028 | 🔵 Low | `EDY_ALLOWED_ROOT` era config morta — lida do env mas nunca consumida (falsa garantia) | `app/core/config/settings.py`, `hash_cmd.py` | ✅ CORRIGIDO (conectado como root default quando `--root` ausente + warning) |
| ARES-QA-029 | ⚪ Info | Exit codes ambíguos no `verify` (FAIL e erro ambos retornam 1) | `app/cli/hash_cmd.py`, `ADR-007` | 📝 Pendente v1.1 (decidir contrato 0/1/2 para scripts) |

**Total Sprint 2:** 0 Critical · 0 High · 0 Medium · 3 Low · 2 Info — **nenhum achado anterior reaberto.**

### 10.2 Veredito por área

| Área | Veredito | Justificativa |
|---|---|---|
| CLI (`hash_cmd.py`) | ✅ APROVADO COM AJUSTES | Fronteira funcional e segura; ajustes 025/026/028 aplicados |
| Config (`settings.py`) | ✅ APROVADO COM AJUSTES | Sem vetor de injection; 028 corrigido |
| Logging (`logger.py`) | ✅ APROVADO | Política "nunca logar conteúdo" confirmada em runtime |
| Crypto (`hashing.py`) | ✅ APROVADO | `safe_compare`/whitelist/`DeprecationWarning` preservados |
| Exceptions (`domain.py`) | ✅ APROVADO | Sem vazamento de info |
| Filesystem (`safe_path.py`) | ✅ APROVADO | Lógica idêntica à movida (shim puro) |
| Docs (THREAT_MODEL/SECURITY) | ✅ APROVADO COM RESSALVAS | Precisos; 027 a atualizar na v1.1 |

### 10.3 Estado de validação final (executado por jr, Tech Lead)

| Check | Resultado |
|---|---|
| `pytest` | ✅ 105 passed, 2 skipped (symlink Windows), 7 warnings (DeprecationWarning esperados) |
| Cobertura | ✅ 99.04% (314 stmts, 3 missing na CLI — guard `__main__`, `return 1` inalcançável, edge case texto; gate 90%) |
| `mypy app` (strict) | ✅ Success: no issues found in 25 source files |
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 39 files already formatted |
| Entrypoint `edyshield` | ✅ `edyshield --version` → `edyshield 1.1.0` (ARES-QA-021 resolvido) |
| Core sem UI/CLI | ✅ Zero imports de `app.ui`/`app.cli` em `app/core` (grep) |
| QG-PROOF | ✅ Encoding 100% UTF-8 sem BOM; 4 correções documentais aplicadas (screenshots/js/app.js/`__init__.py`) |

### Veredito final Sprint 2: ✅ **APROVADO**

**Motivo:** 0 Critical, 0 High, 0 Medium. QG-ARES cumprido. Três achados Low (025/026/028) foram **corrigidos nesta rodada** pelo Tech Lead; 027 e 029 são Info documentados para v1.1. A fronteira única de paths permanece intacta (move sem regressão), política de logging seguro aplicada, `safe_compare`/whitelist/`DeprecationWarning` preservados, entrypoint CLI funcional. Documentação reflete o código real (PROOF validado após correções).

> Re-review Sprint 2: ARES · 01/08/2026 — **VEREDITO: APROVADO** (após ajustes 025/026/028)
> QG-PROOF Sprint 2: 100% UTF-8 sem BOM, zero U+FFFD, zero mojibake, acentos corretos — **PRONTO** (após correções documentais)

---

## 11. Fechamento da Sprint 3 — v1.1 (01/08/2026)

> **Escopo:** revisão final após implementação de todas as pendências de robustez da v1.1
> (ARES-QA-008, 019, 020, 022, 027, 029) + bug de import detectado pelo mypy.

### 11.1 Achados da v1.1 (novos / reabertos)

| ID | Sev. | Descrição | Status |
|----|------|-----------|--------|
| — | 🔴 Bug | `HashError` não importado no `hash_checker.py` após TOCTOU (mypy detectou) | ✅ CORRIGIDO (import adicionado) |
| — | 🔵 Low | Testes de CLI esperavam exit 1 para erros; novo contrato usa exit 2 | ✅ CORRIGIDO (6 testes atualizados) |
| — | ⚪ Info | `EDY_SHIELD_COMPLETO.md` (artefato de transferência) no escopo do ruff | ✅ CORRIGIDO (excluído do ruff) |

### 11.2 Pendências originais — status final

| ID | Sev. | Descrição | Status |
|----|------|-----------|--------|
| ARES-QA-008 | 🔵 Low | TOCTOU hardening (os.open + O_NOFOLLOW + fstat no handle) | ✅ FECHADO |
| ARES-QA-019 | 🔵 Low | `exists()` redundante em `compute()` | ✅ FECHADO |
| ARES-QA-020 | 🔵 Low | `validate_allowed_root` sem `is_dir()` | ✅ FECHADO |
| ARES-QA-022 | 🔵 Low | Dev deps sem pinning | ✅ FECHADO (pins exatos) |
| ARES-QA-027 | ⚪ Info | Docs CLI semantics (THREAT_MODEL/SECURITY) | ✅ FECHADO |
| ARES-QA-029 | ⚪ Info | Exit codes verify 0/1/2 | ✅ FECHADO (ADR-007) |
| ADR-001..005 | ⚪ Info | ADRs referenciados sem documento | ✅ FECHADO (materializados) |

### 11.3 Validação completa (executada por jr, Tech Lead)

| Check | Resultado |
|-------|-----------|
| `pytest` | ✅ 196 passed, 2 skipped (symlink Windows), 7 warnings esperados |
| Cobertura | ✅ 92.90% (887 stmts; gate 90%) |
| `mypy app` (strict) | ✅ Success: no issues found in 38 source files |
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 57 files already formatted |
| QG-PROOF | ✅ Encoding UTF-8 válido (validação anterior mantida) |

### 11.4 Checklist de Quality Gate (QG-ARES) — re-executado

| Item | Status |
|------|--------|
| OWASP Top 10 verificado | ✅ Passou |
| SAST/DAST / análise estática | ✅ Passou (mypy strict + ruff) |
| LGPD/GDPR compliance checked | ✅ Passou (módulo não processa dados pessoais) |
| Threat model criado | ✅ Passou (THREAT_MODEL atualizado) |
| Sem critical/high issues abertas | ✅ Passou — 0 Critical, 0 High |
| Path traversal mitigado | ✅ Passou |
| TOCTOU hardening aplicado | ✅ Passou (os.open + O_NOFOLLOW + fstat) |
| Comparação de hashes em tempo constante | ✅ Passou |
| Algoritmos fracos sinalizados em runtime | ✅ Passou |
| Sem vazamento de informação em erros | ✅ Passou |
| Testes de segurança negativos | ✅ Passou |

### Veredito final Sprint 3 / v1.1: ✅ **APROVADO**

**Motivo:** 0 Critical, 0 High, 0 Medium abertos. Todas as pendências da v1.1 foram
fechadas com evidência em runtime. O bug de import (HashError) foi detectado e corrigido
na própria validação final. A suíte passou de 105 (Sprint 2) para 196 testes com cobertura
92.90% (acima do gate de 90%), mypy strict 0 issues em 38 arquivos e ruff 100% limpo. A
documentação (ADR-001..005, THREAT_MODEL, SECURITY, CHANGELOG, RELEASE_NOTES) está
sincronizada com o código real. **A Sprint 3 pode ser oficialmente encerrada.**

> Fechamento v1.1: jr (Tech Lead) + ARES · 01/08/2026 — **VEREDITO: APROVADO — SPRINT 3 ENCERRADA**

---

## 12. Sprint 4 / v1.2 — QA & Segurança (Batch Hashing, Checksum Files, CLI, E2E)

| Campo | Valor |
|---|---|
| **Escopo** | `app/core/algorithms/batch.py`, `app/core/checksums/`, `app/cli/hash_cmd.py`, `app/core/filesystem/opener.py`, `tests/e2e/` |
| **Versão do produto** | 1.2.0 |
| **Analista** | ARES (Cybersecurity Sênior) — revisão da implementação Sprint 4 |
| **Data** | 02/08/2026 |
| **Suíte de testes** | 248 passed, 2 skipped (`pytest`, ~13s) |
| **Cobertura** | 90.29% (1164 stmts, gate 90%) |
| **mypy strict** | 0 issues em 42 arquivos |
| **ruff** | check limpo; format 71 arquivos OK |
| **CI (GitHub Actions)** | runs #10, #11, #12 — success |

### 12.1 Revisão de segurança dos novos módulos

| Área | Avaliação |
|---|---|
| Batch Hashing — path safety | ✅ `allowed_root` derivado do diretório pai (ARES-QA-028); `compute_file` reutiliza a fronteira única do Core |
| Batch Hashing — erros em lote | ✅ Falha individual capturada como `BatchResult = (None, Exception)` — não interrompe o lote; validação de algoritmo na entrada |
| Checksum Files — parser | ✅ Determinístico; ignora vazias/comentários; rejeita malformadas com `ChecksumError`; valida digest hex e comprimento (64/40/32) |
| Checksum Files — path traversal | ✅ Filenames validados por `resolve_safe_path` com raiz = diretório do checksum; `../` e absolutos fora da raiz → `invalid` (testado) |
| Checksum Files — comparação | ✅ `safe_compare` (hmac.compare_digest, tempo constante) |
| Checksum Files — auto-referência | ✅ Arquivos de checksum excluídos da própria varredura |
| CLI — exit codes | ✅ 0 sucesso / 1 mismatch / 2 erro (ARES-QA-029), preservados nos comandos existentes |
| CLI — separação stdout/stderr | ✅ Digests no stdout; erros e resumo no stderr |
| E2E — comportamento real | ✅ Subprocess `python -m app.cli.hash_cmd` valida stdout, stderr e exit code em todos os fluxos |
| TOCTOU | ✅ `open_regular_file` centraliza `os.open + O_NOFOLLOW + fstat` (ARES-QA-008) — pronto para reuso |

### 12.2 Achados Sprint 4

| ID | Sev. | Descrição | Status |
|---|---|---|---|
| ARES-QA-031 | Info | Cobertura caiu de 92.90% (v1.1) para 90.29% (v1.2) — módulos novos com lógica de apresentação na CLI (subprocess) não são cobertos por unit tests | Aceito — gate 90% mantido; módulos Core novos têm unit tests dedicados |
| ARES-QA-032 | Info | `create_checksum_file` exclui automaticamente arquivos com sufixos de checksum da varredura (comportamento documentado) | Aceito — evita auto-referência |

### 12.3 Quality Gate (QG-ARES) — Sprint 4

| Item | Status |
|---|---|
| OWASP Top 10 verificado | ✅ Passou |
| SAST/análise estática (mypy strict + ruff) | ✅ Passou |
| LGPD/GDPR compliance | ✅ Passou (sem dados pessoais) |
| Path traversal mitigado | ✅ Passou (checksum files + batch) |
| TOCTOU hardening | ✅ Passou (opener reutilizável) |
| Comparação em tempo constante | ✅ Passou |
| Sem critical/high issues abertas | ✅ Passou (0 Critical, 0 High) |
| Testes de segurança negativos | ✅ Passou (path traversal, malformed, mismatch) |

### Veredito Sprint 4 / v1.2: ✅ **APROVADO — RELEASE READY**

**Motivo:** 0 Critical, 0 High abertos. Batch Hashing e Checksum Files reutilizam o Core
sem duplicação; fronteira de paths e comparação constante preservadas; testes E2E validam o
comportamento real da CLI; CI verde nos 3 runs. Suíte evoluiu de 196 → 248 testes com
cobertura 90.29%, mypy strict 0 issues e ruff limpo.

> Fechamento v1.2: jr (Tech Lead) + ARES — 02/08/2026 — **VEREDITO: APROVADO — v1.2 RELEASE READY**

---

# 13. Sprint 5 — File Integrity Monitor (FIM v2.0.0)

## 13.1 Escopo

| Campo | Valor |
|---|---|
| **Módulo** | `app/core/fim/` + plugin `file_integrity` + CLI + Report MD + UI FIM |
| **Arquivos novos** | `core/fim/{models,ids,scanner,baseline,store}.py`, `plugins/builtin/file_integrity_plugin.py` |
| **Arquivos modificados** | `core/exceptions/{domain,__init__}.py`, `filesystem/opener.py`, `services/report_engine.py`, `ui/server.py`, `cli/hash_cmd.py`, `ui/static/{index.html,app.js}` |
| **Testes novos** | `test_fim_core.py`, `test_fim_plugin.py`, `test_fim_report.py`, `test_opener.py`, `test_server.py` + casos FIM em UI/E2E |
| **Versão do produto** | 2.0.0 (`app/__init__.py` + `pyproject.toml`) |

## 13.2 Achados Sprint 5

| ID | Sev. | Descrição | Status |
|---|---|---|---|
| ARES-QA-033 | Info | `baseline_id` tem granularidade de segundos — duas baselines criadas no mesmo segundo colidem no `FimStore` (a segunda sobrescreve a primeira) | Aceito — formato definido pela spec FIM; teste `compare` aguarda 1s; anotado para v2.1 (SQLite) |
| ARES-QA-034 | Info | `_walk_target` não segue symlinks (ADR-FIM-003) — registrados como `ignored` e reportados como INFO na UI | Aceito — comportamento determinístico e seguro |

## 13.3 Análise de segurança do FIM

| Ameaça | Mitigação | Status |
|---|---|---|
| Path traversal no `baseline_id` | Charset seguro `[A-Za-z0-9_.-]` + regex canônica (`FimStore._path_for`) | ✅ Mitigado |
| Baseline corrompida/temperada | Round-trip validado na leitura → `BaselineCorruptionError` (nunca baseline parcial) | ✅ Mitigado |
| Symlink escapando da raiz | `os.scandir` + `entry.is_symlink()` não-follow; `O_NOFOLLOW` no `compute_file` | ✅ Mitigado |
| TOCTOU na varredura | Reutiliza `compute_file` (O_NOFOLLOW + fstat) e `resolve_safe_path` | ✅ Mitigado |
| Digest como fonte de verdade | `compare_baseline_snapshot` compara apenas `hexdigest` (ADR-FIM-002) | ✅ Mitigado |
| Raiz/algoritmo divergentes | `compare_baseline_snapshot` levanta `FimError` em mismatch de root/algo | ✅ Mitigado |
| Vazamento de paths em erros | Mensagens usam `path.name` (ARES-QA-005) | ✅ Mitigado |
| XSS em relatório Markdown | Saída Markdown sem HTML cru; demais formatos escapados | ✅ Mitigado |

## 13.4 Quality Gate (QG-ARES) — Sprint 5

| Item | Status |
|---|---|
| OWASP Top 10 verificado | ✅ Passou |
| SAST/análise estática (mypy strict + ruff) | ✅ Passou (0 issues, 49 arquivos) |
| LGPD/GDPR compliance | ✅ Passou (sem dados pessoais) |
| Path traversal mitigado | ✅ Passou (baseline_id + paths relativos validados) |
| TOCTOU hardening | ✅ Passou (compute_file reutilizado) |
| Comparação em tempo constante | ✅ Passou (digest via `safe_compare`/hashlib) |
| Sem critical/high issues abertas | ✅ Passou (0 Critical, 0 High) |
| Testes de segurança negativos | ✅ Passou (corrupção, traversal no id, mismatch root/algo, digest inválido) |
| Código morto removido | ✅ `_REPORT_FORMATS` (server), `allowed_root` (scanner), `algorithm` (plugin) |

## 13.5 Métricas finais

| Métrica | Valor |
|---|---|
| Testes | **361 passed, 2 skipped** |
| Cobertura global | **91.92%** (gate ≥ 90%) |
| `app/ui/server.py` | 80% → **94%** (endpoints reais) |
| mypy strict | **0 issues** (49 arquivos) |
| ruff check / format | **limpo / 86 arquivos OK** |
| Core deps | **0** (100% stdlib) |

### Veredito Sprint 5 / v2.0.0-dev: ✅ **APROVADO — RELEASE READY**

**Motivo:** 0 Critical, 0 High abertos. FIM reutiliza o Core existente (compute_file,
resolve_safe_path, Report Engine, PluginManager) sem duplicação; round-trip validado,
fronteira de paths e TOCTOU preservados; CLI + Console SOC + 4 formatos de relatório
funcionais; testes E2E validam comportamento real (baseline → scan → detecção de mudanças).
Suíte evoluiu de 248 → 361 testes, cobertura 91.92%, mypy strict 0 issues, ruff limpo.

> Fechamento v2.0.0-dev (Sprint 5): jr (Tech Lead) + ARES — 02/08/2026 — **VEREDITO: APROVADO — SPRINT 5 RELEASE READY**

---

# 14. v2.1 — M1: SQLite Foundation

## 14.1 Escopo

| Campo | Valor |
|---|---|
| **Módulo novo** | `app/core/storage/` (SQLiteDb) |
| **Arquivos alterados** | `services/history.py`, `core/fim/store.py`, `core/fim/baseline.py`, `core/fim/ids.py`, `ui/server.py`, `cli/hash_cmd.py` |
| **ADR** | ADR-V21-001 (SQLite como backend) |
| **Versão** | 2.1.0-dev (em desenvolvimento) |

## 14.2 Análise de segurança

| Ameaça | Mitigação | Status |
|---|---|---|
| **Path traversal no db_path/id** | `_validate_id` (charset seguro) preservado nos stores | ✅ Mitigado |
| **Injeção SQL** | Apenas queries parametrizadas (`?`); nunca concatenação | ✅ Mitigado |
| **Corrupção de payload** | `ScanResult.from_dict`/round-trip validado → `HistoryError`/`BaselineCorruptionError` | ✅ Mitigado |
| **Perda de dados na migração** | Idempotência + backup (`~/.edyshield/backup/`) + fallback de leitura legada | ✅ Mitigado |
| **Colisão de baseline_id (ARES-QA-033)** | `build_unique_baseline_id` (fração de microsegundos) | ✅ Resolvido |
| **Concorrência multithread** | `threading.RLock` + conexão por operação + WAL | ✅ Mitigado |
| **Dependência externa** | `sqlite3` da stdlib — ADR-001 preservado | ✅ Passou |

## 14.3 Achados

| ID | Sev. | Descrição | Status |
|---|---|---|---|
| ARES-QA-035 | Info | SQLite é single-writer — concorrência multi-processo limitada (aceito: produto desktop/CLI single-user) | Aceito |
| ARES-QA-036 | Info | WAL mode cria arquivos `-wal`/`-shm` no diretório do DB (comportamento normal do SQLite) | Aceito — documentado |

## 14.4 Quality Gate (QG-ARES) — M1

| Item | Status |
|---|---|
| OWASP Top 10 verificado | ✅ Passou |
| SAST (mypy strict + ruff) | ✅ Passou (0 issues, 51 arquivos) |
| LGPD/GDPR | ✅ Passou (sem dados pessoais; payloads são resultados de scan) |
| Injeção SQL | ✅ Passou (queries parametrizadas) |
| Path traversal | ✅ Passou (ids validados; db_path controlado) |
| Sem critical/high issues | ✅ Passou (0 Critical, 0 High) |
| Migração segura | ✅ Passou (idempotente + backup + fallback) |

## 14.5 Métricas finais

| Métrica | Valor |
|---|---|
| Testes | **388 passed, 2 skipped** |
| Cobertura | **91.34%** (gate ≥ 90%) |
| mypy strict | **0 issues** (51 arquivos) |
| ruff check / format | **limpo / 94 arquivos OK** |
| Core deps | **0** (100% stdlib — ADR-001) |

### Veredito M1: ✅ **APROVADO**

**Motivo:** 0 Critical/High. SQLite implementado com stdlib, contratos preservados,
migração idempotente + backup + fallback, ARES-QA-033 resolvido, 388 testes verdes,
cobertura 91.34%, mypy 0, ruff limpo. Fundação sólida para M2+.

> Fechamento M1: jr (Tech Lead) + ARES — 02/08/2026 — **VEREDITO: APROVADO — M1 SQLITE FOUNDATION**
