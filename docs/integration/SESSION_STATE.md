# Session State — EDY Shield → EDY SIEM producer v1

> **ESTADO CANÔNICO MAIS RECENTE — 2026-08-11 23:27 BRT.** O primeiro E2E real com o
> receptor SIEM passou. Leia também `SHIELD_SIEM_HANDOFF.md` neste repositório e
> `docs/integration/E2E_SHIELD_SIEM_V1_REPORT.md` no EDYSIEM.

## Checkpoint E2E v1

- Shield: branch `codex/siem-producer-outbox-v1`, início em `0b0964a`.
- SIEM: branch `codex/shield-siem-integration-architecture`, início em `a56ee81`.
- Primeiro evento e 7 cenários reais: PASS.
- Offline: 5 pendentes, 5 recuperados, sem perdas/duplicatas lógicas.
- Idempotência, crash recovery, auth correta/ausente/inválida e batch 100+1: PASS.
- 122 eventos `sent` comparados com a inbox; 0 diferenças.
- Regressão Shield: 45 focados; 680 completos, 2 skipped; cobertura 86,78%;
  Ruff/MyPy/build PASS.
- Checkpoint E2E `82ad8a3` publicado em
  `origin/codex/siem-producer-outbox-v1`.
- Build oficial do SIEM também passou após instalar o `hatchling` declarado no projeto.
- Nenhum código de produção ou frontend foi alterado.
- Próximo passo: **UX INTEGRATION V1** — ação “Investigar no EDY SIEM” para eventos e
  alertas, abrindo diretamente a investigação correspondente.

Atualizado em: 2026-08-11

## Etapa concluída

Producer backend v1 implementado no EDY Shield, sem frontend e sem executar ainda o E2E
real entre os dois projetos. Branch: `codex/siem-producer-outbox-v1`.

## Arquitetura implementada

`fato real → EventMapper → siem_outbox no SQLite do Shield → DeliveryWorker → SiemClient → receptor v1`

- opt-in/local-first; nenhum HTTP no caminho do scan;
- UUID `instance_id` persistente e sequência monotônica;
- payload/event_id imutável durante retry;
- lease recuperável, lote 100/1 MiB, evento 64 KiB;
- retry com full jitter, `Retry-After`, pausa de auth e dead letter;
- limite 50.000 eventos/512 MiB, aviso em 80% e auditoria de enqueue recusado;
- TLS validado pela stdlib; HTTP somente em loopback; token com `repr=False`.

## Arquivos importantes

- `app/integrations/edy_siem/config.py`
- `app/integrations/edy_siem/mapper.py`
- `app/integrations/edy_siem/outbox.py`
- `app/integrations/edy_siem/client.py`
- `app/integrations/edy_siem/worker.py`
- `app/integrations/edy_siem/producer.py`
- `app/core/storage/sqlite_db.py`
- `app/plugins/builtin/file_integrity_plugin.py`
- `app/plugins/builtin/hash_checker_plugin.py`
- `app/services/alert_service.py`
- `app/ui/server.py`
- `.env.example`
- `tests/unit/test_siem_mapper.py`
- `tests/unit/test_siem_outbox.py`
- `tests/unit/test_siem_worker.py`
- `tests/integration/test_siem_producer_integration.py`

## Configuração

`EDY_SIEM_ENABLED=false` por padrão. Quando `true`, definir `EDY_SIEM_URL` e
`EDY_SIEM_TOKEN` (mínimo 32 bytes). `EDYSHIELD_DB_PATH` seleciona o mesmo banco local
usado pelos stores existentes.

## Migration

O bootstrap idempotente do `SQLiteDb` cria `siem_integration_state`, `siem_outbox` e
índices. Também acrescenta `dropped_count` e `last_enqueue_error` caso a tabela de estado
já exista sem essas colunas. Nenhum banco é compartilhado com o SIEM.

## Validação executada

- 126 testes focados de integração/relevantes aprovados na última rodada curta;
- 680 testes completos aprovados, 2 skipped, cobertura global 86,78%;
- Ruff e MyPy (88 arquivos) aprovados;
- payloads produzidos validados diretamente contra `ShieldEventV1` do EDYSIEM;
- testes cobrem 202 accepted/duplicate, 409 duplicate explícito, 401, 403, 400, 413,
  422, 429, 500, 503, timeout, connection refused, JSON inválido, aceite parcial,
  offline→online, resposta perdida, lease pós-crash e concorrência SQLite.

- build de produção aprovado: wheel e sdist `edy_shield-2.0.0` gerados fora do repo;
- warnings restantes são deprecações preexistentes de SHA-1/MD5 e metadata de licença.

## Limitações reais

- Stores legados usam conexões SQLite independentes. Baseline/alerta local e outbox não
  podem compartilhar uma única transação sem refatoração ampla. O callback ocorre
  imediatamente após a persistência local e falhas são isoladas; existe uma janela de
  crash mínima entre os dois commits.
- O worker de longa duração está ligado ao servidor. Operações que instanciam plugins
  fora dessa composição só exportam quando recebem explicitamente um `SiemProducer`.
- Retenção/purge de `sent` após 7 dias e de dead letters após 30 dias ainda não foi
  automatizada; nada é removido silenciosamente.

## Git

- Branch: `codex/siem-producer-outbox-v1`
- Commit funcional publicado: `6e25619` (`feat: add durable EDY SIEM producer outbox`).
- Remote: `origin/codex/siem-producer-outbox-v1`; sincronizado após o commit funcional.
- Handoff correspondente no EDYSIEM: commit `a56ee81`, branch
  `codex/shield-siem-integration-architecture`.
- Merge em `main`: não realizado.

## Como retomar em outra conta

1. Abrir o repositório EDY Shield e permanecer em
   `codex/siem-producer-outbox-v1`.
2. Ler este arquivo e `docs/integration/EDY_SIEM_INTEGRATION.md` integralmente.
3. No EDYSIEM, permanecer em `codex/shield-siem-integration-architecture` e ler
   `docs/integration/SHIELD_SIEM_HANDOFF.md`, `docs/integration/SESSION_STATE.md` e
   `docs/integration/EVENT_CONTRACT_V1.md`.
4. Confirmar que os dois working trees estão limpos e sincronizados antes de iniciar o
   E2E. Não fazer merge em `main` e não alterar frontend nesta próxima etapa.

## Próximo passo exato

## Checkpoint UX Integration V1 - 2026-08-12

- Branch: `codex/siem-producer-outbox-v1`.
- Commit de implementacao: `4fa8e78`.
- O detalhe do alerta consulta o estado real do evento na outbox.
- A acao **Investigar no EDY SIEM** aparece somente apos entrega confirmada.
- A URL e configurada por `EDY_SIEM_UI_URL` e usa somente o `event_id` no deep link.
- E2E real: alerta `ALT-UX-E2E-003`, evento
  `fa3f171e-bb8e-43f2-9bd3-ae716d7316da`, entregue e aberto no SIEM.
- Qualidade: 684 testes, 2 skipped, 86,67%, Ruff/MyPy/build aprovados.
- Proximo passo salvo: **PRODUCT REDESIGN V1**. Nao iniciar sem novo prompt.

Executar, em ambiente local isolado, o primeiro E2E real com EDY SIEM na branch
`codex/shield-siem-integration-architecture`: configurar tokens de laboratório nos dois
processos, iniciar o receptor, gerar um FIM real no Shield, confirmar `202`, inbox e
normalização no SIEM, derrubar/religar o SIEM para provar o replay e então documentar as
evidências. Não iniciar WAR_ROOM nem frontend antes desse gate.
