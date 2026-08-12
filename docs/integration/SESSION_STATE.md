# Session State — EDY Shield → EDY SIEM producer v1

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
- Commits: consultar os dois commits mais recentes desta branch (implementação e estado).
- Merge em `main`: não realizado.

## Próximo passo exato

Executar, em ambiente local isolado, o primeiro E2E real com EDY SIEM na branch
`codex/shield-siem-integration-architecture`: configurar tokens de laboratório nos dois
processos, iniciar o receptor, gerar um FIM real no Shield, confirmar `202`, inbox e
normalização no SIEM, derrubar/religar o SIEM para provar o replay e então documentar as
evidências. Não iniciar WAR_ROOM nem frontend antes desse gate.
