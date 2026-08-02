# 🏗️ EDY SHIELD — Arquitetura e Planejamento da M3 (Alert Engine)

> **Autor:** jr (Software Architect) + ATLAS + ARES — TITAN AI SQUAD  
> **Versão:** 1.0 (Planejamento)  
> **Status:** AGUARDANDO APROVAÇÃO DO PO (EDY)  
> **Data:** 02/08/2026  
> **Escopo:** Motor de Alertas Defensivo (Foco exclusivo em Engine, Regras, Supressão, Ciclo de Vida e Persistência SQLite).

---

## 1. Visão Geral e Objetivos

O objetivo da **Milestone 3 (M3 - Alert Engine)** é construir um motor de alertas defensivo, robusto, transacional e desacoplado para o **EDY Shield**. 

O **Alert Engine** atuará como a camada de inteligência e triagem da plataforma. Ele consome eventos/resultados gerados por múltiplos analisadores/plugins (**String Analyzer**, **Entropy Analyzer**, **File Integrity Monitor - FIM** e **Log Analyzer**), aplica regras de correlação/avaliação, executa deduplicação e supressão de ruídos, e gerencia o ciclo de vida dos alertas com persistência ACID no SQLite.

### 🎯 Diretrizes do Escopo M3 (O que ESTÁ incluído):
- **Core Engine (`AlertEngine`)**: Processamento, avaliação de regras, deduplicação e supressão.
- **Modelos Fortemente Tipados**: `AlertRecord`, `AlertRule`, `Severity` e `AlertStatus`.
- **Regras Configuráveis & Extensíveis (`AlertRule`)**: Avaliação baseada em condições flexíveis sobre metadados dos eventos/scans.
- **Deduplicação Inteligente**: Agrupamento de eventos idênticos em janelas de tempo atômicas com contagem de ocorrências (`fingerprint_hash`).
- **Supressão e Janela de Silenciamento**: Bloqueio de tempestade de alertas (alert fatigue) com regras temporais.
- **Gerenciamento de Ciclo de Vida**: Operações de transição de estado (`ack` / `acknowledge`, `resolve`, `suppress`, `reopen`).
- **Persistência SQLite ACID (`AlertStore`)**: Tabela `alerts` com suporte a histórico, consultas avançadas, paginação e estatísticas.
- **Canais Internos Locais**: Emissão para Console (Logger/EventPublisher) e Arquivo de Log do Alerta (`alerts.log`).
- **Integração com Analisadores Existentes**: Adutores para converter `ScanResult` e achados do FIM, String, Entropy e Log Analyzer em alertas.

### 🚫 Fora do Escopo M3 (O que NÃO ESTÁ incluído):
- ❌ Interface Gráfica / Dashboard (ficará para a M4).
- ❌ Notificações externas (E-mail, Discord, Slack, PagerDuty, Webhooks).
- ❌ Modificação das APIs públicas legadas de hash/checksums.

---

## 2. Decomposição de Módulos

A arquitetura do motor de alertas será organizada no diretório `app/core/alerts/` e `app/services/alert_service.py`, mantendo a separação entre regras de negócio do core (100% stdlib) e persistência/orquestração de serviços.

```text
app/
├── core/
│   └── alerts/
│       ├── __init__.py           # Exporta AlertEngine, AlertRecord, AlertRule, etc.
│       ├── models.py             # AlertRecord, AlertRule, Severity, AlertStatus, AlertAction
│       ├── engine.py             # AlertEngine (avaliação, dedup, supressão, dispatch)
│       ├── rules.py              # Repositório/Avaliador de regras embutidas e dinâmicas
│       ├── channels.py           # Canais internos (ConsoleChannel, FileChannel)
│       └── deduplicator.py       # Algoritmo de fingerprinting e janelas temporais de dedup
├── services/
│   ├── alert_service.py          # AlertService / AlertStore (façada, SQLite, fluxo de ciclo de vida)
│   └── alert_store.py            # Persistência na tabela `alerts` do SQLite
└── cli/
    └── alert_cmd.py              # CLI: edyshield alerts list|show|ack|resolve|stats|rules
```

---

## 3. Contratos Públicos e Interfaces

### 3.1 `AlertEngine` (Core Interface)

```python
class AlertEngine:
    """Motor central de alertas 100% stdlib (independente de I/O ou DB)."""
    
    def __init__(self, rules: list[AlertRule] | None = None, channels: list[BaseAlertChannel] | None = None) -> None:
        ...
        
    def process_event(self, source: str, event_type: str, data: dict[str, Any], severity: Severity) -> AlertRecord | None:
        """Processa um evento individual. Aplica regras, dedup e supressão."""
        ...
        
    def process_scan_result(self, scan_result: Any) -> list[AlertRecord]:
        """Aduz um ScanResult ou AnalysisOutcome e gera os alertas resultantes."""
        ...
        
    def add_rule(self, rule: AlertRule) -> None:
        ...
```

### 3.2 `AlertService` (Service Layer / Storage Façade)

```python
class AlertService:
    """Serviço de aplicação para gestão de alertas com persistência SQLite."""
    
    def __init__(self, db_path: Path | str | None = None) -> None:
        ...
        
    def process_and_store(self, source: str, event_type: str, data: dict[str, Any], severity: Severity) -> AlertRecord | None:
        """Processa o evento no engine e persiste no SQLite se gerou alerta."""
        ...
        
    def acknowledge_alert(self, alert_id: str, acked_by: str = "system", note: str = "") -> AlertRecord:
        """Marca o alerta como ACK (Reconhecido)."""
        ...
        
    def resolve_alert(self, alert_id: str, resolved_by: str = "system", resolution_note: str = "") -> AlertRecord:
        """Marca o alerta como RESOLVED (Resolvido)."""
        ...
        
    def suppress_alert(self, alert_id: str, reason: str = "") -> AlertRecord:
        """Marca o alerta como SUPPRESSED (Supresso)."""
        ...
        
    def list_alerts(
        self,
        severity: Severity | None = None,
        status: AlertStatus | None = None,
        source: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[AlertRecord]:
        """Consulta alertas com filtros e paginação."""
        ...
```

---

## 4. Modelos de Dados e Schema do Banco

### 4.1 Dataclasses (`app/core/alerts/models.py`)

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class AlertStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    SUPPRESSED = "SUPPRESSED"

@dataclass
class AlertRecord:
    alert_id: str = field(default_factory=lambda: f"ALT-{uuid.uuid4().hex[:12].upper()}")
    fingerprint: str = ""  # SHA-256 de (source + event_type + target/path + rule_id)
    title: str = ""
    description: str = ""
    source: str = ""  # Ex: "fim", "string_analyzer", "entropy_analyzer", "log_analyzer"
    rule_id: str = "DEFAULT"
    severity: Severity = Severity.MEDIUM
    status: AlertStatus = AlertStatus.NEW
    target: str = ""  # Arquivo, diretório ou recurso afetado
    
    # Métrica de contagem/dedup
    count: int = 1
    first_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_seen_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Metadados estendidos
    details: dict[str, Any] = field(default_factory=dict)
    
    # Auditoria de ciclo de vida
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    resolved_at: str | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None

@dataclass
class AlertRule:
    rule_id: str
    name: str
    source: str  # Ex: "string_analyzer", "*" para todas
    condition_key: str  # Ex: "category", "entropy", "match_count"
    operator: str  # "eq", "gt", "gte", "contains", "regex", "in"
    condition_value: Any
    target_severity: Severity
    title_template: str
    description_template: str
    enabled: bool = True
    suppression_window_seconds: int = 300  # 5 minutos de janela para supressão/dedup
```

### 4.2 Schema SQLite (`alerts` Table)

A tabela `alerts` será criada no banco de dados SQLite existente (`sqlite_db.py`):

```sql
CREATE TABLE IF NOT EXISTS alerts (
    alert_id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    target TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    details TEXT NOT NULL, -- JSON string
    acknowledged_at TEXT,
    acknowledged_by TEXT,
    resolved_at TEXT,
    resolved_by TEXT,
    resolution_note TEXT
);

CREATE INDEX IF NOT EXISTS idx_alerts_fingerprint ON alerts(fingerprint);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_source ON alerts(source);
CREATE INDEX IF NOT EXISTS idx_alerts_last_seen ON alerts(last_seen_at);
```

---

## 5. Estratégia de Deduplicação e Supressão

1. **Fingerprinting Determinístico**:
   O fingerprint de um alerta é um hash SHA-256 curto calculado sobre a tupla `(source, rule_id, target)`.
   - *Exemplo*: Se o FIM detecta alteração no mesmo arquivo `/etc/passwd` 10 vezes em 1 minuto, todas as ocorrências terão o **mesmo fingerprint**.
2. **Deduplicação por Janela Temporal**:
   Ao receber um evento:
   - O `AlertEngine` busca no repositório de estado/banco por um alerta com o mesmo `fingerprint` em estado `NEW` ou `ACKNOWLEDGED` cuja janela temporal (`last_seen_at` + `suppression_window_seconds`) ainda esteja ativa.
   - Se encontrado: Incrementa o contador `count = count + 1`, atualiza `last_seen_at` e mescla os metadados novos, **sem criar um novo alerta**.
   - Se não encontrado ou se a janela expirou: Gera um novo `AlertRecord` com `status = NEW` e `count = 1`.
3. **Supressão Ativa**:
   Alertas marcados como `SUPPRESSED` ou associados a regras desabilitadas são ignorados durante a emissão de canais e não reabrem até ação explícita do analista.

---

## 6. Registros de Decisão de Arquitetura (ADRs)

### ADR-009: Motor de Alertas Desacoplado 100% Stdlib no Core
- **Status**: APROVADO (Proposto)
- **Contexto**: O processamento e avaliação de regras de alerta devem rodar no ambiente do cliente com zero dependências externas.
- **Decisão**: O `AlertEngine`, `AlertRule` e `AlertRecord` no `app/core/alerts/` utilizarão exclusivamente a biblioteca padrão Python (dataclasses, enum, json, hashlib, re). A persistência SQLite fica isolada na camada de serviço (`app/services/alert_store.py`).

### ADR-010: Deduplicação Baseada em Fingerprint Temporal
- **Status**: APROVADO (Proposto)
- **Contexto**: Escaneamentos em lote ou monitoramentos contínuos podem disparar centenas de eventos idênticos (alert fatigue).
- **Decisão**: Utilizar `fingerprint = SHA256(source + rule_id + target)` combinado com uma janela configurável de tempo (`suppression_window_seconds`). Em vez de criar múltiplos registros, incrementa-se o campo `count` e atualiza-se `last_seen_at`.

---

## 7. Backlog de Implementação da Sprint M3

| Código | Tarefa / Item | Dependências | Estimativa |
|---|---|---|---|
| **M3-T01** | Criar modelos `Severity`, `AlertStatus`, `AlertRecord`, `AlertRule` (`app/core/alerts/models.py`) | Nenhuma | 0.5d |
| **M3-T02** | Implementar algoritmo de Fingerprinting e Deduplicação (`app/core/alerts/deduplicator.py`) | M3-T01 | 0.5d |
| **M3-T03** | Criar repositório e avaliador de Regras (`app/core/alerts/rules.py`) | M3-T01 | 0.5d |
| **M3-T04** | Implementar `AlertEngine` e Canais Internos (`ConsoleChannel`, `FileChannel`) | M3-T01..T03 | 1.0d |
| **M3-T05** | Implementar `AlertStore` e migração do Schema SQLite (`alerts` table) | M3-T01 | 0.5d |
| **M3-T06** | Implementar `AlertService` para gerenciar ciclo de vida (`ack`, `resolve`, `suppress`, `list`) | M3-T04, M3-T05 | 0.5d |
| **M3-T07** | Desenvolver Adutores/Adaptadores para FIM, String, Entropy e Log Analyzer | M3-T04, M3-T06 | 0.5d |
| **M3-T08** | Implementar Comandos CLI (`edyshield alerts list|show|ack|resolve|stats`) | M3-T06 | 0.5d |
| **M3-T09** | Bateria de Testes Unitários, Integração e E2E (com alvo de cobertura ≥ 90%) | Todos acima | 1.0d |
| **M3-T10** | Documentação e Atualização de CHANGELOG e QA Report | Todos acima | 0.5d |

---

## 8. Estratégia de Testes e Quality Gates

### 8.1 Níveis de Testes
1. **Unitários (`tests/unit/test_alert_core.py`)**:
   - Avaliação de regras (operadores `eq`, `contains`, `gte`, `regex`).
   - Geração determinística de fingerprints.
   - Incremento do contador em deduplicação.
   - Funcionamento isolado de `ConsoleChannel` e `FileChannel`.
2. **Serviço e Persistência (`tests/unit/test_alert_service.py`)**:
   - Inserção e consulta na tabela `alerts` em SQLite em memória.
   - Transições de estado do ciclo de vida (`NEW` -> `ACKNOWLEDGED` -> `RESOLVED`).
   - Supressão de alertas e filtros por severidade/status.
3. **Integração com Analisadores (`tests/integration/test_alert_integration.py`)**:
   - Executar `AnalysisService` com String/Entropy e verificar a geração automática de alertas.
   - Simular alterações do FIM e validar se alertas de severidade correta são registrados.
4. **End-to-End CLI (`tests/e2e/test_alert_cli_e2e.py`)**:
   - Executar `edyshield alerts list --json`.
   - Executar `edyshield alerts ack <ALT-ID>`.
   - Verificar exit codes e saídas formatadas.

### 8.2 Quality Gates M3
- [ ] 0 testes falhando (Suíte global mantida 100% verde).
- [ ] Cobertura de código nos novos módulos de alertas ≥ 90%.
- [ ] `mypy --strict` com 0 erros nos módulos novos e modificados.
- [ ] `ruff check` e `ruff format` limpos.
- [ ] Schema SQLite indexado e sem degradação de performance.

---

## 9. Matriz de Riscos e Mitigações

| Risco Identificado | Impacto | Mitigação Arquitetural |
|---|---|---|
| **Explosão de Alertas (Alert Fatigue)** | Alto | Implementação obrigatória de `fingerprint` hash com janela de dedup (`suppression_window_seconds`). |
| **Concorrência no SQLite em Escritas Simultâneas** | Médio | Transações atômicas controladas via `sqlite_db.py` com timeout e modo WAL ativado. |
| **Regras Genéricas Disparando Falsos Positivos** | Médio | Limiares de severidade calibrados por padrão (ex: Entropia > 6.0 bits para HIGH/CRITICAL). |
| **Degradação de Performance no Scanning** | Baixo | Processamento de regras em memória em $O(N)$ utilizando filtros stdlib otimizados. |

---

## 10. Atualização de Roadmap e Memória Compartilhada

### 📍 Roadmap M3 (Inalterado no escopo global, detalhado na execução):
- **M1 (Concluído)**: SQLite History & Foundation.
- **M2 (Concluído e Aprovado em 02/08/2026)**: String + Entropy Analyzer com suporte CLI e REST API.
- **M3 (Fase Atual)**: Alert Engine & Lifecycle Management.
- **M4 (Próxima Fase)**: Dashboard UI + CLI Visual Polish.

---

> **EDY Shield — Defenda. Verifique. Confie.**  
> Planejamento M3 · TITAN AI SQUAD · **Aguardando Aprovação Formal do PO (EDY) para Início do Desenvolvimento.**
