# 🔒 Segurança do EDY Shield

> Política de segurança do **EDY Shield** — plataforma modular de cibersegurança defensiva em
> **Python 3.12**, com core **100% stdlib** (ADR-001). Este documento descreve o modelo de ameaças
> resumido, as práticas de segurança adotadas, as limitações conhecidas e o processo para reportar
> vulnerabilidades.

---

## 1. Modelo de ameaças resumido

| # | Ameaça | Vetor | Controle existente | Status |
|---|--------|-------|--------------------|--------|
| 1 | **Path traversal / leitura arbitrária de arquivos** | `..`, caminhos absolutos fora da raiz, symlinks que escapam | Fronteira única `resolve_safe_path()` — resolve o caminho (`Path.resolve()`, inclui symlinks) e valida contenção na raiz com `relative_to`; rejeita com `HashError` genérico | ✅ Mitigado (ARES-QA-001) |
| 2 | **Ambiguidade `str` → texto silencioso** | Typo de path hasheado como texto (falso positivo de integridade) | `_looks_like_path()` + `FileNotFoundError` quando a string parece path e o arquivo não existe; sem fallback silencioso | ✅ Mitigado (ARES-QA-002) |
| 3 | **Timing attack na verificação de digests** | Comparação não-constante (`==`) | `safe_compare()` via `hmac.compare_digest` em tempo constante | ✅ Mitigado (ARES-QA-003) |
| 4 | **Algoritmos fracos (MD5/SHA1)** | Colisão em verificação de integridade crítica | Whitelist `HashAlgorithm` + `DeprecationWarning` em runtime; **SHA-256** é o padrão | ✅ Mitigado (ARES-QA-004) |
| 5 | **Injeção de algoritmo** | Nome arbitrário repassado a `hashlib.new` | Whitelist validada **antes** de alcançar o `hashlib`; inputs não-string também rejeitados | ✅ Mitigado |
| 6 | **Vazamento de informação em erros/logs** | Paths absolutos em mensagens (OSINT/auxílio a reconhecimento) | Mensagens usam apenas `target.name` (basename); `HashError` de traversal é genérico; logging só de hashes e metadados | ✅ Mitigado (ARES-QA-005) |
| 7 | **DoS por arquivo especial** | FIFO/device/socket travando `open()` indefinidamente | `ensure_regular_file()` rejeita diretórios e arquivos não-regulares | ✅ Mitigado (ARES-QA-007) |
| 8 | **TOCTOU (time-of-check to time-of-use)** | Troca de arquivo entre checagem e leitura | Aceito como trade-off em CLI local; documentado no docstring de `_compute_file_impl`; re-verificação/hardening planejado para a camada de serviço | ⚠️ Residual (ARES-QA-008 / R1) |
| 9 | **Supply chain** | Dependência maliciosa de terceiros | Core **zero dependências de runtime** (ADR-001) — apenas stdlib | ✅ Mitigado; dev deps sem pinning (ARES-QA-022) |
| 10 | **Exfiltração de conteúdo via log** | Conteúdo do arquivo no log | Política explícita: **nunca** logar conteúdo de arquivo — apenas hashes e metadados (logger central) | ✅ Mitigado por política |

> Modelo formal detalhado (vetores MITRE, controles e risco residual): [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md).

---

## 2. Reportando vulnerabilidades

O EDY Shield leva a segurança a sério. Se você encontrou uma vulnerabilidade, **não** abra uma
issue pública antes de nos comunicar.

### Processo

1. **Contato privado:** envie um e-mail para **`security@edyshield.invalid`** (placeholder —
   substitua pelo endereço real da organização mantenedora) com o máximo de detalhes:
   - Descrição da vulnerabilidade e impacto estimado;
   - Passos de reprodução (PoC, se disponível);
   - Versão afetada (consulte `edyshield --version` ou `app/__init__.py`);
   - Plataforma/ambiente (SO, Python 3.12.x).
2. **Alternativa:** se o projeto estiver hospedado em um forge com suporte a divulgação
   coordenada, use o mecanismo privado da plataforma (ex.: "Report a vulnerability" no GitHub).
3. **Confirmação:** o mantenedor confirmará o recebimento em até **5 dias úteis**.
4. **Fix e release:** trabalharemos em um patch e publicaremos em uma release com o aviso
   correspondente antes de qualquer divulgação pública.
5. **Divulgação coordenada:** após o fix publicado, o relato pode ser divulgado publicamente
   (ex.: issue, advisory), com crédito ao reportador quando solicitado.

### Política de divulgação responsável

- 🔒 **Sem disclosure público antes do fix** — não publique o detalhe da vulnerabilidade
  (PoC, código de exploração) antes de o mantenedor disponibilizar a correção.
- 🕐 Prazo razoável de **90 dias** para tratamento, salvo acordos diferentes.
- 🏆 Reportadores serão creditados (se desejarem) no changelog/advisory.

> ⚠️ **Escopo:** este canal é para vulnerabilidades de **segurança**. Bugs funcionais comuns
> devem ser reportados como issues normais (ver [`CONTRIBUTING.md`](CONTRIBUTING.md)).

---

## 3. Práticas de segurança adotadas

- **Whitelist de algoritmos** — `HashAlgorithm` valida nomes antes de alcançar o `hashlib`
  (ARES-QA-006); nomes arbitrários geram `UnsupportedAlgorithmError`.
- **Comparação constante** — `hmac.compare_digest` em `safe_compare` (ARES-QA-003).
- **Algoritmos fracos sinalizados** — `DeprecationWarning` em runtime para MD5/SHA1
  (ARES-QA-004); default sempre SHA-256.
- **Fronteira única de paths** — `app.core.filesystem.safe_path` resolve symlinks, rejeita
  `..`/absolutos fora da raiz e arquivos especiais (ARES-QA-001/005/007).
- **Sem fallback silencioso** — string com cara de path inexistente levanta `FileNotFoundError`
  (ARES-QA-002); use `compute_text` explícito para texto com pontos/extensão (ARES-QA-024).
- **Entrada validada** — `validate_chunk_size` e `validate_expected` na fronteira
  (ARES-QA-009/010); encoding desconhecido traduzido para `ValueError` (ARES-QA-011).
- **Mensagens sanitizadas** — nenhuma mensagem de erro expõe caminhos absolutos (ARES-QA-005).
- **Logging seguro** — logger central `edy_shield`; nunca loga conteúdo de arquivo nem segredos.
- **Zero dependências runtime** — superfície de ataque de supply chain mínima (ADR-001).
- **Testes de segurança negativos** — 20 testes adicionados na re-review do ARES (ARES-QA-017),
  incluindo traversal, `None`, symlink, não-hex e tipos inválidos.

---

## 4. Limitações conhecidas

| Limitação | Impacto | Mitigação / plano |
|-----------|---------|-------------------|
| **TOCTOU local** — checagem de existência/type acontece antes do `open` | Arquivo pode ser trocado entre checagem e leitura | Aceito para CLI local (R1); hardening planejado: `os.open` + `O_NOFOLLOW` + `fstat` no handle (v1.1) |
| **MD5/SHA1 legados** — disponíveis por compatibilidade | Não resistentes a colisões | `DeprecationWarning`; uso exclusivo em integridade não-crítica |
| **Default `allowed_root=None` = diretório pai do alvo** | Em serviço público, confiaria no pai do arquivo | Fronteira de serviço (v2/v3) deve exigir `allowed_root` explícito (R3) |
| **`validate_allowed_root` agora valida root como diretório** | - | ✅ Corrigido na v1.1 (ARES-QA-020) |
| **Dev deps sem pinning** | Risco de supply chain no ambiente de desenvolvimento | Pinning/lockfile antes do primeiro release (ARES-QA-022) |
| **`compute("README")` hasheia como texto** (sem separador/extensão) | Surpresa para arquivos sem extensão | Documentado (ARES-QA-024); use `Path` explícito ou `compute_file` |
| **Checagem `exists()` duplicada em `compute`** | Redundância DRY + 2ª janela TOCTOU | Pendência v1.1 (ARES-QA-019) |
| **Testes de symlink em Windows** | 2 testes skipped (symlink não suportado por padrão) | `Path.resolve()` cobre symlinks por design; testes ativos em Linux/CI |

---

## 5. Escopo e não-escopo

- ✅ **No escopo:** falhas de segurança no core, CLI, configuração, logging e fronteira de paths.
- ❌ **Fora do escopo:** uso indevido da ferramenta (a ferramenta é **defensiva** e para uso
  autorizado); problemas em dependências de desenvolvimento não relacionadas à segurança do produto.

---

> **EDY Shield — Defenda. Verifique. Confie.** 🛡️
> Política de segurança · Core 100% stdlib · Zero deps runtime
