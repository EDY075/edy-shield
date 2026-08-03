# Plano de Estudos — EDY Shield em 14 Dias

Roteiro prático de aprendizado em operação Blue Team/SOC usando o EDY Shield v2.2.
Cada dia combina um objetivo, um exercício prático e um resultado esperado para validação.

Pré-requisito: instalação concluída (ver `docs/USER_GUIDE.md`, seções 3 e 4).

---

## Dia 1 — Dashboard

**Objetivo:** conhecer a interface e interpretar os indicadores principais.

**Exercício:**
- Inicie o servidor e abra `http://127.0.0.1:8000/dashboard`.
- Identifique: sidebar, topbar, pesquisa global, alternador de tema e painel de status.
- Gere um alerta de teste: `edyshield analyze arquivo_teste` ou use `/api/scan`.
- Observe os 5 KPIs (Alertas, Críticos, Altos, Pendentes, Resolvidos) e as mini-barras.

**Resultado esperado:** você consegue explicar o que cada KPI, gráfico e badge representa, e sabe onde ver a saúde do sistema.

---

## Dia 2 — Alert Center

**Objetivo:** dominar triagem de alertas: pesquisa, filtros e ações de ciclo de vida.

**Exercício:**
- Abra `#/alerts` e pesquise por um termo no campo de busca.
- Aplique filtros de severidade, status, origem e período.
- Ordene por severidade e por última ocorrência.
- Selecione um alerta e aplique na ordem: **ACK**, **Resolve**, **Suppress**, **Reopen**.
- Teste ações em lote com múltiplos alertas selecionados.

**Resultado esperado:** você sabe o efeito de cada estado (NEW, ACKNOWLEDGED, RESOLVED, SUPPRESSED) e consegue triar alertas de forma eficiente.

---

## Dia 3 — Rules

**Objetivo:** entender como o motor de alertas decide o que notificar.

**Exercício:**
- Abra `#/rules` e leia a tabela de regras ativas.
- Associe cada regra à origem (fim, string_analyzer, entropy_analyzer, log_analyzer).
- Interprete operador, valor e severidade alvo.
- Consulte pela API: `curl http://127.0.0.1:8000/api/alerts/rules`.

**Resultado esperado:** você explica por que um evento vira alerta e qual severidade recebe.

---

## Dia 4 — Assets

**Objetivo:** entender o papel do inventário de assets na operação.

**Exercício:**
- Abra `#/assets` e reconheça a estrutura: KPIs, tabela (Hostname, IP, Sistema, Último Seen, Status, Risco, Tags).
- Observe o estado vazio e reflita sobre o que seria necessário para povoar o inventário.

**Resultado esperado:** você entende o conceito de inventário de assets e identifica que a tela ainda é placeholder (sem API dedicada nesta versão).

---

## Dia 5 — Logs

**Objetivo:** compreender a visualização de eventos e níveis de severidade de log.

**Exercício:**
- Abra `#/logs` e explore o seletor de níveis (INFO, WARNING, ERROR).
- Relacione o que cada nível indicaria em uma operação real.
- Execute um scan e observe a saída no terminal para comparar com a estrutura de log.

**Resultado esperado:** você diferencia níveis de log e entende a estrutura do visualizador (ingestão em tempo real é futura).

---

## Dia 6 — IOC Manager

**Objetivo:** aprender o conceito de Indicators of Compromise e seus tipos.

**Exercício:**
- Abra `#/ioc` e revise os tipos: IP, domínio, URL, hash e e-mail.
- Identifique KPIs estruturados por tipo.
- Reconheça o estado vazio e o aviso de que a API de IOC ainda não existe.

**Resultado esperado:** você sabe o que é um IOC e por que esta tela é placeholder nesta versão.

---

## Dia 7 — System Health

**Objetivo:** diagnosticar a saúde do ambiente.

**Exercício:**
- Abra `#/health` e revise: API, Database, Analyzers, Uptime.
- Verifique a lista de plugins/analisadores ativos.
- Rode `curl http://127.0.0.1:8000/api/health` e compare com a tela.
- Identifique como um componente degradado aparece (badge vermelho).

**Resultado esperado:** você monitora proativamente a saúde do sistema e sabe onde investigar falhas.

---

## Dia 8 — Settings e Tema

**Objetivo:** configurar a experiência de uso.

**Exercício:**
- Abra `#/settings` e alterne o tema Escuro/Claro; recarregue a página e confirme a persistência.
- Teste o alternador da topbar.
- Identifique quais campos são funcionais e quais são placeholder (Janela de Supressão, Severidade Mínima).

**Resultado esperado:** você diferencia configuração real de ilustrativa.

---

## Dia 9 — CLI: Hash e Checksum

**Objetivo:** operar verificação de integridade pela linha de comando.

**Exercício:**
- `edyshield hash arquivo`
- `edyshield hash diretorio --batch --recursive`
- `edyshield verify arquivo --digest <hex>`
- `edyshield checksum create ./pasta` e `edyshield checksum verify SHA256SUMS`

**Resultado esperado:** você calcula e verifica hashes, e cria/valida arquivos de checksum com segurança.

---

## Dia 10 — CLI: FIM

**Objetivo:** operar File Integrity Monitor (baseline + scan).

**Exercício:**
- `edyshield fim baseline criar ./documentos`
- Modifique um arquivo do diretório (ex.: adicione uma linha).
- `edyshield fim scan ./documentos --baseline baseline.json`
- Interprete as mudanças detectadas.

**Resultado esperado:** você detecta alterações não autorizadas de integridade.

---

## Dia 11 — CLI: Alertas

**Objetivo:** gerenciar alertas pela linha de comando.

**Exercício:**
- `edyshield alerts list --severity HIGH --limit 10`
- `edyshield alerts stats`
- `edyshield alerts ack <id> --by analista --note "validando"`
- `edyshield alerts resolve <id> --note "falso positivo"`
- `edyshield alerts suppress <id> --reason "ruido conhecido"`
- `edyshield alerts reopen <id> --reason "reincidente"`

**Resultado esperado:** você aplica todo o ciclo de vida dos alertas sem abrir o navegador.

---

## Dia 12 — API REST

**Objetivo:** automatizar consultas e ações via API.

**Exercício:**
- `curl http://127.0.0.1:8000/api/health`
- `curl "http://127.0.0.1:8000/api/alerts?severity=CRITICAL&limit=10"`
- `curl http://127.0.0.1:8000/api/alerts/stats`
- `curl http://127.0.0.1:8000/api/alerts/rules`
- Poste um comentário: `curl -X POST .../api/alerts/{id}/comment -d '{"body":"observacao"}'`
- Exporte: `curl http://127.0.0.1:8000/api/alerts/{id}/export/md`

**Resultado esperado:** você integra o EDY Shield a scripts e fluxos automatizados.

---

## Dia 13 — Investigation Workspace

**Objetivo:** conduzir uma investigação completa de um alerta.

**Exercício:**
- No Alert Center, abra o drawer de um alerta.
- Percorra as abas: **Summary** (alvo, origem, regra, MITRE, usuário, processo), **Timeline**, **Evidence** (chips de hashes/IPs/URLs/IOCs), **Comments** (adicione uma nota) e **History**.
- Exporte o alerta em JSON pelo botão do drawer.

**Resultado esperado:** você documenta uma investigação de ponta a ponta com trilha de auditoria.

---

## Dia 14 — Fluxo Completo SOC

**Objetivo:** executar o ciclo operacional completo.

**Exercício (desafio final):**
1. Crie uma baseline FIM de um diretório.
2. Altere um arquivo monitorado para gerar detecção.
3. Rode um scan e confirme a alteração via CLI e API.
4. Gere um alerta (analyze/scan) e trie no Alert Center: pesquise, filtre, ACK, adicione comentário investigativo, Resolve.
5. Confira o History e exporte o alerta em JSON e Markdown.
6. Verifique o System Health antes e depois do fluxo.

**Resultado esperado:** você executa Monitoramento → Detecção → Triagem → Investigação → Resposta → Documentação, integrando UI, CLI e API.

---

## Quadro-resumo

| Dia | Tópico | Habilidade |
|---|---|---|
| 1 | Dashboard | Leitura de KPIs e saúde |
| 2 | Alert Center | Triagem e ciclo de vida |
| 3 | Rules | Motor de alertas |
| 4 | Assets | Inventário |
| 5 | Logs | Eventos e níveis |
| 6 | IOC Manager | Indicadores de comprometimento |
| 7 | System Health | Diagnóstico |
| 8 | Settings | Configuração e tema |
| 9 | CLI Hash | Integridade de arquivos |
| 10 | CLI FIM | Monitoramento de integridade |
| 11 | CLI Alertas | Gestão de alertas |
| 12 | API REST | Automação |
| 13 | Investigation | Investigação e documentação |
| 14 | Fluxo SOC | Operação completa |
