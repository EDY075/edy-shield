# EDY Shield → EDY SIEM

## Finalidade

Esta integração opcional exporta fatos reais do EDY Shield para o receptor v1 do EDY
SIEM sem transformar o SIEM em dependência do produto. O fluxo local sempre termina
antes da rede:

`FIM/hash/alerta → mapper v1 → SQLite outbox → worker → HTTPS → EDY SIEM`

O contrato canônico permanece no repositório EDYSIEM, em
`docs/integration/EVENT_CONTRACT_V1.md`. O Shield não mantém uma segunda definição do
schema.

## Receptor e configuração

Endpoint: `POST /api/v1/ingestion/sources/edy-shield/events`.

Variáveis de ambiente:

| Variável | Uso |
|---|---|
| `EDY_SIEM_ENABLED` | `true` habilita enqueue e entrega; padrão `false` |
| `EDY_SIEM_URL` | URL base do SIEM; HTTPS obrigatório fora de loopback |
| `EDY_SIEM_TOKEN` | Bearer M2M com no mínimo 32 bytes, nunca salvo no código ou banco |
| `EDYSHIELD_DB_PATH` | Banco SQLite local já usado pelo Shield |

O arquivo `.env.example` contém somente valores seguros. O projeto não carrega `.env`
automaticamente: injete as variáveis no processo.

## Identidade e outbox

Na primeira execução habilitada, o Shield cria um UUID de instalação em
`siem_integration_state.instance_id`. Ele não depende apenas do hostname e permanece
estável no mesmo banco. A chave de idempotência de evento no SIEM é
`(source.instance_id, event_id)`.

Cada payload completo recebe `event_id` e `sequence` uma vez e é persistido em
`siem_outbox` antes de qualquer tentativa HTTP. Retries reutilizam o payload e o
`event_id`. Os estados locais são `pending`, `in_flight`, `sent` e `dead_letter`.
Leases `in_flight` vencidos retornam a `pending`, inclusive após crash.

A migration é idempotente: a inicialização normal do `SQLiteDb` cria as duas tabelas,
índices e adiciona as colunas de auditoria a uma tabela de estado anterior. A fila aceita
até 50.000 registros ou 512 MiB de payloads; em 80% registra aviso. No teto, eventos já
persistidos são preservados e novos enqueues falham apenas na camada de integração, com
contador local `dropped_count`.

## Entrega, retry e modo offline

O worker daemon envia até 100 eventos e 1 MiB por lote; cada evento é limitado a 64 KiB.
Conexão e requisição usam timeouts de 2 s e 5 s. Falhas de rede e HTTP
`408/429/500/502/503/504` usam exponential backoff com full jitter, teto de 5 minutos e
`Retry-After` limitado a 15 minutos. `401/403` preservam a fila e pausam cada tentativa
por 15 minutos. Erros estruturais viram `dead_letter`.

Itens `accepted` ou `duplicate` são marcados `sent`. Um `409` somente é tratado como
concluído se a resposta identificar explicitamente todos os itens esperados como
`duplicate`; um conflito genérico continua sendo erro estrutural.

Com integração desabilitada não há banco adicional, thread ou tentativa de rede. Com o
SIEM offline, os eventos ficam duráveis e o FIM/hash/alerta retorna normalmente. O
worker é iniciado e encerrado junto com o servidor de longa duração; execuções locais
continuam independentes do receptor.

## Eventos conectados

- baseline FIM criada;
- arquivo criado, modificado ou removido;
- scan FIM concluído;
- mismatch real do Hash Checker para arquivo;
- alerta criado/deduplicado e transições de ciclo de vida.

O contrato v1 não possui `baseline_changed`; mudanças são representadas por eventos de
arquivo e pelo resumo de scan.
