# Handoff — EDY Shield → EDY SIEM v1

Atualizado em: 2026-08-11 23:27 BRT

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
