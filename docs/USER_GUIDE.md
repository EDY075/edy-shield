# Manual Oficial do EDY Shield v2.2

Guia técnico e operacional para estudar, instalar e utilizar o EDY Shield.
Versão de referência: **v2.2.0-rc** · Última atualização: agosto de 2026

---

## 1. Introdução

### O que é o EDY Shield

O EDY Shield é uma plataforma modular de cibersegurança defensiva escrita em **Python 3.12**, com núcleo 100% baseado na biblioteca padrão (sem dependências de runtime). Ele combina monitoramento de integridade de arquivos (FIM), análise de hashes, análise de logs e um motor de alertas configurável, entregues por uma interface web no estilo SOC (Security Operations Center).

### Para quem ele foi criado

O EDY Shield foi criado para analistas de segurança, operadores de blue team, estudantes de cibersegurança e times pequenos que precisam de uma ferramenta leve, autônoma e sem custo para:

- monitorar a integridade de arquivos críticos;
- verificar hashes e arquivos de checksum;
- detectar indicadores suspeitos em arquivos e logs;
- centralizar alertas e investigar incidentes.

### O que ele simula em uma operação Blue Team/SOC

A plataforma reproduz, em escala de laboratório, o ciclo operacional de um SOC:

1. **Monitoramento** — coleta de baselines de integridade e análise de conteúdo.
2. **Detecção** — geração de alertas a partir de regras e deduplicação.
3. **Triagem** — centro de alertas com filtros, priorização por severidade e status.
4. **Investigação** — workspace lateral com timeline, evidências, comentários e histórico.
5. **Resposta** — ações de ciclo de vida: ACK, Resolve, Suppress e Reopen.

### Limitações atuais

- A interface de **Assets** e **IOC Manager** ainda não possui API de dados dedicada no backend; exibem estado estruturado (KPIs zerados e estado vazio) como placeholder operacional.
- A página **Settings** inclui configurações visuais funcionais (tema) e campos de alert engine que são ilustrativos.
- O **Logs** exibe a estrutura de visualização; a ingestão de eventos de log em tempo real é tema de versões futuras.
- Não há autenticação multi-usuário; o papel do operador é único (Analista / Blue Team).
- O servidor é apropriado para ambientes de estudo e laboratório, não para exposição direta à internet.

---

## 2. Requisitos

| Item | Requisito |
|---|---|
| Python | 3.12 ou superior |
| Sistemas operacionais | Windows, Linux, macOS |
| Dependências de runtime | Nenhuma (núcleo 100% stdlib) |
| Dependências de desenvolvimento | pytest, mypy, ruff (arquivo `requirements-dev.txt`) |
| Porta padrão | 8000 (HTTP) |
| Permissões | Leitura/escrita no diretório do projeto e no diretório do banco SQLite |

O banco SQLite é criado automaticamente em `~/.edyshield/edy_shield.db` (configurável via `EDYSHIELD_DB_PATH`).

---

## 3. Instalação passo a passo

### Clonar o repositório

```bash
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield
```

### Criar ambiente virtual

```bash
python -m venv .venv
```

### Ativar o ambiente

**Windows (PowerShell):**

```powershell
.venv\Scripts\activate
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

### Instalar dependências

```bash
pip install -e .
```

Para desenvolvimento (testes e lint):

```bash
pip install -r requirements-dev.txt
```

### Inicializar o banco

O banco é criado automaticamente na primeira execução. Para validar:

```bash
python -c "from app.core.storage import get_connection; c = get_connection(); print(c.execute('SELECT 1').fetchone())"
```

### Validar a instalação

```bash
python -m pytest tests/ -q
edyshield --version
```

---

## 4. Como iniciar

### Iniciar o servidor

```bash
python -m app.ui.server
```

A saída deve exibir algo como:

```
EDY Shield UI em http://127.0.0.1:8000 (v2.2.0)
```

### Acessar o dashboard

Abra no navegador: **http://127.0.0.1:8000/dashboard**

### Encerrar corretamente

Pressione `Ctrl+C` no terminal do servidor. O processo encerra o `serve_forever()` e libera a porta.

### Verificar saúde da API e do banco

```bash
curl http://127.0.0.1:8000/api/health
```

Resposta esperada contém `"status": "online"`, `"sqlite": {"status": "ok", ...}` e a contagem de analisadores.

---

## 5. Visão geral da interface

**Sidebar** — Navegação principal com seções OPERAÇÕES (Dashboard, Alert Center, Rules, Assets, Logs, IOC Manager) e SISTEMA (System Health, Settings). Inclui o painel STATUS DO SISTEMA (API, Database, Analyzers, Version) no rodapé.

**Topbar** — Breadcrumb da página atual, pesquisa global, botão de atualização, alternador de tema, indicador Online e avatar do operador.

**Pesquisa global** — Campo central da topbar que encaminha para o Alert Center e inicia a busca.

**Indicadores de status** — Pill verde "Online" na topbar e o painel de status do sistema na sidebar refletem o estado real da API.

**Tema dark/light** — Alternado pelo botão na topbar ou pela página Settings. A preferência fica salva no navegador.

**Atualização dos dados** — Os painéis do dashboard e alertas atualizam automaticamente a cada 30 segundos; o botão de atualização dispara um refresh manual imediato.

---

## 6. Dashboard

**KPIs** — Cards compactos com os totais: Alertas, Críticos, Altos, Pendentes e Resolvidos. Cada card exibe uma mini-barra proporcional para comparação rápida de volume.

**Alertas por severidade** — Gráfico de barras com o volume por nível (CRITICAL, HIGH, MEDIUM, LOW, INFO).

**Alertas por status** — Gráfico de barras por estado (Novos, Reconhecidos, Resolvidos, Suprimidos).

**Saúde do sistema** — Barras com estado real: SQLite, Analisadores, Eventos Processados e Uptime.

**Status dos componentes** — Badges de API REST, Banco de Dados, Alert Engine, Analisadores e versão do Python.

**Timeline** — Últimos 10 alertas com severidade, horário e origem.

**Ações rápidas** — Atalhos para Novo Scan, Ver Alertas, Importar IOC, Abrir Logs e Atualizar Dashboard.

**Como interpretar** — Quanto maior a mini-barra do KPI, maior a participação daquele nível no total. Critérios de atenção: Críticos e Altos elevados, Pendentes acumulados e qualquer componente com badge não verde.

---

## 7. Alert Center

Passo a passo operacional:

1. **Pesquisa** — Campo na toolbar; filtra por título, regra ou asset (debounce de 300 ms).
2. **Filtros** — Severidade, Status, Origem e Período em uma única linha.
3. **Ordenação** — Clique nos cabeçalhos da tabela (Severidade, Status, Título, Regra, Origem, Alvo, Count, Última Ocorrência).
4. **Paginação** — Controles no rodapé com navegação por páginas.
5. **Seleção múltipla** — Checkboxes por linha ou "selecionar todos" da página; barra de ações em lote.
6. **ACK** — Reconhecer o alerta (estado ACKNOWLEDGED).
7. **Resolve** — Marcar como resolvido (estado RESOLVED).
8. **Suppress** — Suprimir o alerta (estado SUPPRESSED), útil para ruído conhecido.
9. **Reopen** — Reabrir alertas resolvidos/suprimidos (volta a NEW).
10. **Ações em lote** — ACK, Resolve ou Suppress aplicados a todos os selecionados.
11. **Drawer lateral** — Abre ao clicar em uma linha; workspace de investigação com abas.
12. **Timeline** — Eventos cronológicos: primeira/última ocorrência, reconhecimento e resolução.
13. **Evidências** — Chips coloridos por tipo: Hashes, Caminhos, IPs, Domínios, URLs, IOCs; payload bruto ao final.
14. **Comentários** — Exibe comentários existentes e permite adicionar novos (Enter ou botão Enviar).
15. **Histórico** — Registro de criação, reconhecimento, resolução e contagem de deduplicação.
16. **Exportação** — Botão JSON no rodapé do drawer baixa o alerta completo em JSON. A API também permite exportar em Markdown (`/api/alerts/{id}/export/md`).

---

## 8. Rules

**O que são** — Regras ativas do motor de alertas: definem condições (origem, operador, valor) e a severidade alvo do alerta gerado.

**Como visualizar** — A página Rules lista as regras em tabela com ID, Nome, Origem, Operador, Valor, Severidade e Ativo.

**Como interpretar** — A coluna Severidade exibe badge colorido; a coluna Ativo indica se a regra está habilitada.

**Como criar ou administrar** — A administração de regras é feita pelo motor/backend; a interface atual é de visualização. Não há editor visual de regras nesta versão.

---

## 9. Assets

**O que representa** — Hosts/endpoints que seriam monitorados pela plataforma.

**KPIs** — Total Assets, Monitorados (FIM), Com Mudanças e Risco Crítico.

**Tabela** — Colunas Hostname, IP, Sistema, Último Seen, Status, Risco e Tags (estrutura de inventário).

**Estado vazio** — Sem API dedicada de assets nesta versão, a página exibe KPIs zerados e o estado "Nenhum asset cadastrado".

**Como adicionar ou importar** — Não há API nem fluxo de cadastro implementado; o botão é visual.

---

## 10. Logs

**Como consultar** — A página Logs apresenta a estrutura de visualização com seletor de nível.

**Filtros** — Seletor de nível (Todos, INFO, WARNING, ERROR).

**Exportação** — Botão Exportar disponível na interface (estrutura).

**Estado vazio** — Sem ingestão de logs em tempo real nesta versão, exibe "Nenhum log disponível".

**Como interpretar** — Os eventos de log seriam classificados por nível; o visualizador usa fonte monoespaçada para leitura técnica.

---

## 11. IOC Manager

**O que é IOC** — Indicator of Compromise: artefato observável (IP, domínio, URL, hash, e-mail) que indica possível atividade maliciosa.

**Tipos** — IP, domínio, URL, hash e e-mail.

**Como importar** — Botão "Importar IOCs" disponível na interface.

**Como pesquisar** — Campo de filtro na lista.

**Como interpretar resultados** — KPIs estruturados por tipo (IPs Maliciosos, Hashes, Domínios).

**Estado vazio** — **Importante:** nesta versão ainda não existe API completa de IOC no backend; a página exibe KPIs zerados e "Nenhum IOC cadastrado" como placeholder operacional.

---

## 12. System Health

**API** — Status online/degradado do serviço REST.

**SQLite** — Estado do banco (Saudável/Erro) e caminho do arquivo.

**Alert Engine** — Eventos processados, alertas criados, deduplicados e tamanho do cache.

**Analisadores / Plugins** — Contagem de plugins ativos e lista individual com indicador verde.

**CPU, memória, disco e uptime** — O uptime é exibido em dias/horas/minutos/segundos. Métricas de CPU/memória/disco não são expostas pela API nesta versão.

**Como identificar componente degradado** — Badges vermelhos/amarelos e barras críticas indicam problema; o painel STATUS DO SISTEMA na sidebar também reflete API, Database e Analyzers.

---

## 13. Settings

**Tema** — Escuro/Claro, com persistência no navegador.

**Preferências** — Auto-refresh (indicador de preferência; a atualização real ocorre a cada 30 s).

**Configurações disponíveis** — Janela de Supressão (s) e Severidade Mínima.

**O que é visual/placeholder** — Os campos do Alert Engine e os botões Salvar/Cancelar são ilustrativos nesta versão; o comportamento funcional de persistência dessas configurações ainda não está implementado.

---

## 14. CLI

Comando principal: `edyshield`. Uso:

```bash
edyshield --help
edyshield --version
```

### 14.1 `edyshield hash`

- **Sintaxe:** `edyshield hash <source> [--batch] [--recursive] [--algorithm ALG] [--root DIR]`
- **Finalidade:** calcular o hash de um arquivo, texto ou diretório.
- **Exemplo:** `edyshield hash arquivo.bin`
- **Resultado esperado:** exibe o digest calculado; com `--batch`, processa o diretório.

### 14.2 `edyshield verify`

- **Sintaxe:** `edyshield verify <source> --digest HEX [--algorithm ALG] [--root DIR]`
- **Finalidade:** verificar o hash de um arquivo contra um digest esperado.
- **Exemplo:** `edyshield verify arquivo.bin --digest abc123...`
- **Resultado esperado:** mensagem de confirmação ou divergência.

### 14.3 `edyshield checksum`

- **Sintaxe:** `edyshield checksum create <dir> [--algorithm ALG] [--output FILE] [--recursive]` e `edyshield checksum verify <file>`
- **Finalidade:** criar e verificar arquivos de checksum (`.sha256`, `.sha1`, `.md5`).
- **Exemplo:** `edyshield checksum create ./binarios` e `edyshield checksum verify SHA256SUMS`
- **Resultado esperado:** relatório com total, ok, mismatch, missing e invalid.

### 14.4 `edyshield fim`

- **Sintaxe:** `edyshield fim baseline criar <target> [--algorithm ALG] [--no-recursive] [--output FILE]` e `edyshield fim scan <target> --baseline <ID|arquivo.json> [--no-recursive]`
- **Finalidade:** File Integrity Monitor — criar baseline de integridade e varrer comparando com a baseline.
- **Exemplo:** `edyshield fim baseline criar ./docs` e `edyshield fim scan ./docs --baseline baseline.json`
- **Resultado esperado:** baseline JSON criada; scan reporta mudanças detectadas.

### 14.5 `edyshield string analyze`

- **Sintaxe:** `edyshield string analyze <target>`
- **Finalidade:** String Analyzer — detecta indicadores suspeitos em texto (URLs, IPs, hashes, tokens, comandos, credenciais).
- **Exemplo:** `edyshield string analyze script.ps1`
- **Resultado esperado:** lista de indicadores encontrados.

### 14.6 `edyshield analyze`

- **Sintaxe:** `edyshield analyze <target>`
- **Finalidade:** análise integrada String + Entropy Analyzer.
- **Exemplo:** `edyshield analyze arquivo`
- **Resultado esperado:** relatório consolidado de análise.

### 14.7 `edyshield history`

- **Sintaxe:** `edyshield history`
- **Finalidade:** listar o histórico de varreduras executadas.
- **Resultado esperado:** lista de entradas com IDs para consulta.

### 14.8 `edyshield alerts`

Subcomandos de gerenciamento de alertas:

- `edyshield alerts list [--severity S] [--status S] [--source S] [--limit N] [--offset N] [--json]`
- `edyshield alerts show <id> [--json]`
- `edyshield alerts ack <id> [--by USUARIO] [--note TEXTO]`
- `edyshield alerts resolve <id> [--by USUARIO] [--note TEXTO]`
- `edyshield alerts suppress <id> [--reason TEXTO]`
- `edyshield alerts reopen <id> [--reason TEXTO]`
- `edyshield alerts stats [--json]`
- `edyshield alerts rules`

**Finalidade:** listar, detalhar e aplicar ações de ciclo de vida aos alertas (ACK, resolve, suppress, reopen), além de estatísticas e regras.

**Exemplo:** `edyshield alerts ack alert-0001 --by analista --note "validando"`

**Resultado esperado:** confirmação da ação e novo estado do alerta.

> **Nota sobre exportação:** a exportação de alertas é realizada pela interface (botão JSON no drawer) ou pela API REST (`/api/alerts/{id}/export/md|json`). Não há subcomando CLI dedicado de exportação nesta versão.

---

## 15. API

Resumo dos endpoints reais. Base: `http://127.0.0.1:8000`

### GET

| Endpoint | Descrição |
|---|---|
| `/api/plugins` | Lista plugins registrados e versão |
| `/api/history` | Histórico de varreduras |
| `/api/history/{id}` | Carrega um ScanResult salvo |
| `/api/analyze/history` | Histórico de análises |
| `/api/analyze/{id}` | Carrega uma análise salva |
| `/api/alerts` | Lista alertas (filtros: `severity`, `status`, `source`, `since`, `q`, `limit`, `offset`) |
| `/api/alerts/stats` | Estatísticas agregadas (total, por severidade, por status, por origem) |
| `/api/alerts/rules` | Regras ativas do motor |
| `/api/alerts/{id}` | Detalhe do alerta |
| `/api/alerts/{id}/comments` | Comentários do alerta |
| `/api/alerts/{id}/related` | Alertas relacionados (mesmo fingerprint) |
| `/api/alerts/{id}/export/md` | Exporta investigação em Markdown |
| `/api/alerts/{id}/export/json` | Exporta o alerta em JSON |
| `/api/health` | Saúde do sistema (status, SQLite, analisadores, uptime) |
| `/api/fim/baselines` | Lista baselines do FIM |
| `/api/fim/baselines/{id}` | Detalhe da baseline |
| `/api/report/{id}?fmt=` | Relatório de varredura (`json`, `txt`, `html`, `md`) |

### POST

| Endpoint | Descrição |
|---|---|
| `/api/scan` | Executa um plugin (body: `{"plugin", "target", "options"}`) |
| `/api/analyze` | Executa análise integrada |
| `/api/analyze/string` | Executa String Analyzer |
| `/api/analyze/entropy` | Executa Entropy Analyzer |
| `/api/alerts/batch` | Ação em lote (body: `{"alert_ids", "action", "by", "note"}`) |
| `/api/alerts/{id}/comment` | Adiciona comentário (body: `{"author", "body"}`) |
| `/api/alerts/{id}/{action}` | Ação individual (`ack`, `resolve`, `suppress`, `reopen`) |

### Exemplo rápido

```bash
# Listar alertas críticos
curl "http://127.0.0.1:8000/api/alerts?severity=CRITICAL&limit=10"

# Verificar saúde
curl "http://127.0.0.1:8000/api/health"

# Reconhecer um alerta
curl -X POST http://127.0.0.1:8000/api/alerts/alert-0001/ack \
  -H "Content-Type: application/json" \
  -d '{"by": "analista", "note": "validando em horario comercial"}'
```

---

## Glossário rápido

- **ACK** — Acknowledge; reconhecer que o alerta está sendo tratado.
- **Baseline** — Fotografia de integridade (hashes) de um conjunto de arquivos.
- **FIM** — File Integrity Monitor; monitoramento de integridade de arquivos.
- **Fingerprint** — Identificador de deduplicação; alertas iguais compartilham fingerprint.
- **IOC** — Indicator of Compromise; indicador de comprometimento.
- **SOC** — Security Operations Center; centro de operações de segurança.
