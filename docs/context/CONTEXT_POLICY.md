# Context Policy v1.0 — Índice Mestre JR_MEMORY.md

## Regra de Ouro
**Nunca carregar contexto total. Sempre carregar incremental.**

## Camadas de Contexto

| Camada | Arquivo | Quando carregar | Tamanho máximo |
|--------|---------|-----------------|----------------|
| Fixa (1) | Identidade JR, regras permanentes | Sempre | 800 tokens |
| Projeto (2) | **JR_MEMORY.md** (índice mestre) | **Toda tarefa (primeiro)** | **300 tokens** |
| Projeto (2) | PROJECT_STATE.md | Quando JR_MEMORY indicar | 300 tokens |
| Tarefa (3) | SESSION_SUMMARY.md, TASK_LEDGER.md | **Sob demanda** via banner JR_MEMORY | 400 tokens |
| Tarefa (3) | Arquivos da tarefa + diff | Por tarefa | 1500 tokens |
| Demanda (4) | Restante do código | Apenas se necessário | Sob demanda |

## Fluxo de Carga Prioritário
```
Nova tarefa →
  1. Ler JR_MEMORY.md (cache quente) → 100-300 tokens
  2. Se JR_MEMORY.md indicar necessidade:
       Read PROJECT_STATE.md    (mudança de status) 
       Read TASK_LEDGER.md      (tarefas)
       Read SESSION_SUMMARY.md  (sessão anterior)
  3. Localizar apenas arquivos da tarefa (grep, não read)
  4. Executar a tarefa
  5. Atualizar JR_MEMORY.md + arquivo(s) afetado(s)
```

## Regras Específicas
- Arquivos >100 linhas: ler via offset (30-50 linhas por vez)
- Código repetido: cache em SESSION_SUMMARY.md
- QA_REPORT.md: nunca ler completo — usar grep por ID
- MEMORY_LOG.md: consultar apenas via grep, não inteiro
- AGENTS.md: extrair apenas regras ativas para o projeto atual
- JR_MEMORY.md: sempre carregar primeiro — é o cache quente do projeto