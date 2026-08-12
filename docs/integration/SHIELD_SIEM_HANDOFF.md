# Handoff — EDY Shield → EDY SIEM v1

Atualizado em: 2026-08-12 — Sprint A1 concluída

## Estado atual

O producer/outbox do Shield e o receptor/inbox/normalizador do SIEM estão implementados.
O primeiro E2E real local foi concluído com PASS, sem alteração de frontend ou código de
produção nesta etapa.

- Shield: branch `codex/siem-producer-outbox-v1`, início em `0b0964a`.
- SIEM: branch `codex/shield-siem-integration-architecture`, início em `a56ee81`.
- Relatório canônico: no EDYSIEM,
  `docs/integration/E2E_SHIELD_SIEM_V1_REPORT.md`.
- Contrato canônico: no EDYSIEM, `docs/integration/EVENT_CONTRACT_V1.md`.

## Evidência resumida

- primeiro evento `shield.fim.file.added`: outbox → worker → HTTP → inbox →
  CanonicalEvent → `sent`;
- 7 cenários aprovados;
- SIEM offline: 5 eventos duráveis; recuperação automática 5/5;
- perdas: 0; duplicatas lógicas: 0;
- idempotência, crash recovery e auth correta/ausente/inválida: PASS;
- batch real: 101 eventos divididos em 100+1;
- 122 eventos entregues comparados com a inbox, sem divergência;
- logs sem token, Bearer ou traceback.

## Arquivos críticos do Shield

- `app/integrations/edy_siem/config.py`
- `app/integrations/edy_siem/mapper.py`
- `app/integrations/edy_siem/outbox.py`
- `app/integrations/edy_siem/client.py`
- `app/integrations/edy_siem/worker.py`
- `app/integrations/edy_siem/producer.py`
- `app/plugins/builtin/file_integrity_plugin.py`
- `app/plugins/builtin/hash_checker_plugin.py`
- `app/services/alert_service.py`
- `app/ui/server.py`
- `docs/integration/EDY_SIEM_INTEGRATION.md`

## Validação

- focados: 45 passed;
- suíte completa: 680 passed, 2 skipped;
- cobertura: 86,78%;
- Ruff, MyPy, build e `git diff --check`: PASS.

O SIEM obteve 928 testes e 95,15% de cobertura, com Ruff/MyPy aprovados. O build oficial
também passou após instalar o `hatchling` declarado em `[build-system]`, gerando wheel e
sdist 0.2.0.

## Decisões e limitações

- bancos não são compartilhados;
- HTTP somente em loopback neste teste; fora dele, usar HTTPS;
- secrets permanecem apenas em variáveis de ambiente;
- segurança local do Shield não depende da disponibilidade do SIEM;
- inbox downstream, retenção automática, WAR_ROOM e frontend continuam fora do escopo.

## Próximo passo exato

**UX INTEGRATION V1**:

1. No Shield, adicionar a ação “Investigar no EDY SIEM” ao evento/alerta.
2. No SIEM, abrir diretamente a investigação correspondente.
3. Exibir origem EDY Shield, ativo, evidências, hashes, timeline, MITRE quando aplicável
   e permitir criação de caso.

Não fazer merge em `main`, não implementar WAR_ROOM e não iniciar o worker downstream
da inbox sem nova etapa aprovada.

## Handoff - UX Integration V1 concluida (2026-08-12)

Commit de implementacao Shield: `4fa8e78` na branch
`codex/siem-producer-outbox-v1`.

O detalhe do alerta agora exibe estado de integracao em linguagem operacional e so
oferece **Investigar no EDY SIEM** quando a outbox registra entrega confirmada. O
resolver local e `GET /api/integrations/edy-siem/alerts/{alert_id}`. O deep link usa
`EDY_SIEM_UI_URL` e `/investigate/shield/{event_id}`; nenhum token ou evidencia entra
na URL.

Arquivos centrais: `app/ui/server.py`,
`app/ui/static/dashboard/js/pages/alerts.js`,
`app/ui/static/dashboard/css/dashboard.css`, `app/integrations/edy_siem/config.py`,
`app/integrations/edy_siem/outbox.py` e `app/integrations/edy_siem/mapper.py`.

O E2E real confirmou o alerta `ALT-UX-E2E-003`, evento
`fa3f171e-bb8e-43f2-9bd3-ae716d7316da`, entrega e abertura contextual no SIEM. Proximo
passo: **PRODUCT REDESIGN V1**. Nao iniciar ainda.

## Revalidacao de retomada - 2026-08-12

Nenhuma alteracao parcial foi encontrada no worktree. A UX Integration V1 foi
revalidada com 11 testes focados e 684 testes completos (2 ignorados, 86,67%),
Ruff, MyPy, build e verificacao de diff. A acao continua condicionada ao estado
`delivered` da outbox e o deep link continua sem token ou evidencia na URL.

## Handoff - Product Redesign V1 (auditoria, sem implementacao)

O Shield foi revisado em Dashboard, Alert Center, detalhe de alerta e Assets. A proposta
e reposiciona-lo como **Endpoint Integrity & Defense**, nao um SOC generico: a Home deve
orientar por host, postura/baseline, mudancas criticas e proxima acao. Manter a tabela,
o painel de evidencia e o gate de entrega SIEM; reduzir cartoes de telemetria repetidos e
acoes rapidas concorrentes. A Sprint A depende de aprovacao explicita do plano.

## Handoff — Sprint A1 Endpoint Integrity Center concluída (2026-08-12)

### Contexto

A primeira entrega do Product Redesign V1 foi implementada somente no EDY Shield. A
Home genérica foi substituída por um centro de decisão de integridade do endpoint, sem
alterar contratos do SIEM ou iniciar a Sprint A2.

### Artefatos principais

- `app/ui/static/dashboard/js/pages/dashboard.js`: composição real da postura,
  prioridade e próxima ação;
- `app/ui/static/dashboard/css/dashboard.css`: layout responsivo da A1;
- `app/ui/static/dashboard/index.html`: identidade Endpoint Integrity & Defense;
- `app/ui/static/dashboard/js/components/components.js`: reparo visual limitado aos
  textos legados conhecidos, sempre antes do escape HTML;
- `app/ui/static/dashboard/js/pages/alerts.js`: abertura automática do alerta exato
  selecionado na Home;
- `app/ui/server.py`: hostname no health e correção do rótulo de falha temporária;
- `tests/integration/test_m42_endpoints.py`: contrato estático/HTTP da nova Home e
  hardening do ID do alerta.

### Decisões preservadas

- a ação **Investigar no EDY SIEM** continua disponível somente quando a outbox confirma
  `delivered`;
- o deep link continua em `/investigate/shield/{event_id}`, sem token, hashes ou
  evidências na URL;
- indisponibilidade do SIEM não afeta o fluxo local do Shield;
- dados dinâmicos são escapados; IDs de alerta não são interpolados como código;
- a A1 não cria score, cobertura, SLA ou automação sem fonte real.

### Qualidade

- 52 testes focados aprovados;
- 686 testes completos aprovados, 2 ignorados, cobertura 86,67%;
- Ruff, MyPy, build, JavaScript syntax check e `git diff --check` aprovados;
- revisão real em 1920x1080, 1366x768 e 390x844 sem overflow horizontal;
- um alerta entregue exibiu o CTA SIEM; um alerta não entregue manteve apenas o estado
  operacional, como esperado.

### Pendências / próximo responsável

Próximo escopo permitido: **Sprint A2 — FIM / Baseline / Scan Experience** no EDY
Shield. Criar a experiência dedicada de baseline/scan sem antecipar mudanças no EDY
SIEM, nas Sprints B/C/D ou em `main`.
