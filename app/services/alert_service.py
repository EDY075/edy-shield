"""Service Layer do Alert Engine (EDY Shield -- M3-T08).

Orquestra o :class:`~app.core.alerts.engine.AlertEngine` (Core, 100%
stdlib) com a persistencia :class:`~app.services.alert_store.AlertStore`
(SQLite). Gerencia o ciclo de vida completo dos alertas:

* **process_and_store** -- recebe evento, processa no engine, persiste
  resultado (novo ou atualizado), hidrata cache de dedup.
* **acknowledge_alert** -- marca alerta como ``ACKNOWLEDGED``.
* **resolve_alert** -- marca como ``RESOLVED``.
* **suppress_alert** -- marca como ``SUPPRESSED`` (e remove do cache de
  dedup para parar de contar).
* **reopen_alert** -- marca como ``NEW`` novamente.
* **list_alerts** -- consulta com filtros/paginacao.
* **get_alert** -- busca por ID.
* **stats** -- agregacoes do store + engine.

A logica de negocio vive aqui (ADR-002): CLI, API e outros consumers
apenas chamam este service.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.core.alerts.channels import BaseAlertChannel, ConsoleChannel
from app.core.alerts.deduplicator import DedupCache
from app.core.alerts.engine import AlertEngine
from app.core.alerts.models import (
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertStatus,
    Severity,
)
from app.core.logging import get_logger
from app.services.alert_store import AlertStore

__all__ = ["AlertService", "AlertServiceError"]


class AlertServiceError(Exception):
    """Erro de dominio do AlertService."""


_logger = get_logger("edyshield.alerts.service")


class AlertService:
    """Service de aplicacao para gestao de alertas com persistencia SQLite.

    Facade que integra o :class:`AlertEngine` (regras, dedup, dispatch)
    com o :class:`AlertStore` (SQLite). Mantem o cache de dedup em
    sincronia com o banco.

    Args:
        db_path: Caminho do banco SQLite. ``None`` usa o padrao.
        rules: Regras iniciais para o engine. ``None`` usa as defaults.
        channels: Canais para dispatch. ``None`` usa ConsoleChannel.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        rules: list[AlertRule] | None = None,
        channels: list[BaseAlertChannel] | None = None,
    ) -> None:
        # Respeitar env var EDYSHIELD_DB_PATH se db_path nao foi explicitado
        if db_path is None:
            env_db = os.environ.get("EDYSHIELD_DB_PATH")
            if env_db:
                db_path = Path(env_db)
        self._store = AlertStore(db_path=db_path)
        self._engine = AlertEngine(
            rules=rules,
            channels=channels if channels is not None else [ConsoleChannel()],
        )
        # Hidratar cache de dedup com alertas ativos do banco
        self._hydrate_dedup_cache()

    # --- Propriedades ----------------------------------------------- #

    @property
    def engine(self) -> AlertEngine:
        """Instancia do AlertEngine subjacente."""
        return self._engine

    @property
    def store(self) -> AlertStore:
        """Instancia do AlertStore subjacente."""
        return self._store

    @property
    def dedup_cache(self) -> DedupCache:
        """Cache de dedup compartilhado com o engine."""
        return self._engine.dedup_cache

    def close(self) -> None:
        """Fechar recursos (conexao SQLite)."""
        self._store.close()

    # --- Processamento --------------------------------------------- #

    def process_and_store(self, event: AlertEvent) -> AlertRecord | None:
        """Processar evento no engine e persistir se gerou/-atualizou alerta.

        Args:
            event: Evento a processar.

        Returns:
            :class:`AlertRecord` resultante (novo ou atualizado), ou
            ``None`` se nenhuma regra corresponder.
        """
        result = self._engine.process_event(event)
        if result.alert is None:
            return None

        if result.action == "created":
            # Novo alerta: persistir
            self._store.save(result.alert)
            _logger.debug(
                "Alerta criado: %s (%s/%s)",
                result.alert.alert_id,
                result.alert.source,
                result.alert.rule_id,
            )
        elif result.action == "updated":
            # Dedup: atualizar contador e last_seen no banco
            self._store.update_count(
                result.alert.alert_id,
                result.alert.count,
                result.alert.last_seen_at,
            )
            # Atualizar severidade se mudou
            self._store.save(result.alert)
            _logger.debug(
                "Alerta atualizado: %s (count=%d)",
                result.alert.alert_id,
                result.alert.count,
            )

        return result.alert

    def process_scan_evidences(
        self,
        source: str,
        target: str,
        evidences: list[Any],
        max_severity: Severity,
    ) -> list[AlertRecord]:
        """Aduz evidencias de um ScanResult e gerar alertas.

        Wrapper de conveniencia para integrar com o AnalysisService
        sem acoplar diretamente as classes de plugin.

        Args:
            source: Origem canonica (ex.: ``AlertSource.STRING_ANALYZER``).
            target: Recurso analisado.
            evidences: Lista de evidencias.
            max_severity: Severidade maxima do resultado.

        Returns:
            Lista de alertas gerados (ignora ``None``).
        """
        results = self._engine.process_scan_result(source, target, evidences, max_severity)
        alerts: list[AlertRecord] = []
        for r in results:
            if r.alert is not None:
                if r.action == "created" or r.action == "updated":
                    self._store.save(r.alert)
                alerts.append(r.alert)
        return alerts

    # --- Ciclo de vida --------------------------------------------- #

    def acknowledge_alert(
        self, alert_id: str, acked_by: str = "system", note: str = ""
    ) -> AlertRecord:
        """Marcar alerta como ACKNOWLEDGED.

        Args:
            alert_id: ID do alerta.
            acked_by: Identificador de quem reconheceu.
            note: Nota opcional (registrada em ``resolution_note``).

        Returns:
            Alerta atualizado.

        Raises:
            AlertServiceError: Se alerta nao encontrado ou transicao invalida.
        """
        record = self._store.get(alert_id)
        if record is None:
            raise AlertServiceError(f"Alerta nao encontrado: {alert_id}")

        if record.status not in (AlertStatus.NEW,):
            raise AlertServiceError(f"Transicao invalida: {record.status.value} -> ACKNOWLEDGED")

        from app.core.alerts.models import now_iso

        record.status = AlertStatus.ACKNOWLEDGED
        record.acknowledged_at = now_iso()
        record.acknowledged_by = acked_by
        if note:
            record.resolution_note = note
        self._store.save(record)
        self._engine.dedup_cache.update(record)
        _logger.info("Alerta %s reconhecido por %s", alert_id, acked_by)
        return record

    def resolve_alert(
        self,
        alert_id: str,
        resolved_by: str = "system",
        resolution_note: str = "",
    ) -> AlertRecord:
        """Marcar alerta como RESOLVED.

        Args:
            alert_id: ID do alerta.
            resolved_by: Identificador de quem resolveu.
            resolution_note: Nota de resolucao.

        Returns:
            Alerta atualizado.

        Raises:
            AlertServiceError: Se alerta nao encontrado ou transicao invalida.
        """
        record = self._store.get(alert_id)
        if record is None:
            raise AlertServiceError(f"Alerta nao encontrado: {alert_id}")

        if record.status not in (AlertStatus.NEW, AlertStatus.ACKNOWLEDGED):
            raise AlertServiceError(f"Transicao invalida: {record.status.value} -> RESOLVED")

        from app.core.alerts.models import now_iso

        record.status = AlertStatus.RESOLVED
        record.resolved_at = now_iso()
        record.resolved_by = resolved_by
        if resolution_note:
            record.resolution_note = resolution_note
        self._store.save(record)
        # Remover do cache de dedup (alerta resolvido nao acumula mais)
        self._engine.dedup_cache.forget(record.fingerprint)
        _logger.info("Alerta %s resolvido por %s", alert_id, resolved_by)
        return record

    def suppress_alert(self, alert_id: str, reason: str = "") -> AlertRecord:
        """Marcar alerta como SUPPRESSED.

        Alertas suprimidos nao sao reabertos nem acumulam novos eventos
        com o mesmo fingerprint.

        Args:
            alert_id: ID do alerta.
            reason: Motivo da supressao.

        Returns:
            Alerta atualizado.

        Raises:
            AlertServiceError: Se alerta nao encontrado.
        """
        record = self._store.get(alert_id)
        if record is None:
            raise AlertServiceError(f"Alerta nao encontrado: {alert_id}")

        record.status = AlertStatus.SUPPRESSED
        if reason:
            record.resolution_note = reason
        self._store.save(record)
        # Remover do cache de dedup (alerta suprimido para de contar)
        self._engine.dedup_cache.forget(record.fingerprint)
        _logger.info("Alerta %s suprimido: %s", alert_id, reason)
        return record

    def reopen_alert(self, alert_id: str, reason: str = "") -> AlertRecord:
        """Reabrir alerta (status -> NEW).

        Permite reabrir um alerta ``RESOLVED`` ou ``SUPPRESSED``.

        Args:
            alert_id: ID do alerta.
            reason: Motivo da reabertura (opcional).

        Returns:
            Alerta atualizado.

        Raises:
            AlertServiceError: Se alerta nao encontrado.
        """
        record = self._store.get(alert_id)
        if record is None:
            raise AlertServiceError(f"Alerta nao encontrado: {alert_id}")

        if record.status not in (AlertStatus.RESOLVED, AlertStatus.SUPPRESSED):
            raise AlertServiceError(f"Transicao invalida: {record.status.value} -> NEW (reopen)")

        from app.core.alerts.models import now_iso

        record.status = AlertStatus.NEW
        record.resolved_at = None
        record.resolved_by = None
        record.acknowledged_at = None
        record.acknowledged_by = None
        if reason:
            record.resolution_note = reason
        record.last_seen_at = now_iso()
        record.count = 1
        self._store.save(record)
        # Re-adicionar ao cache de dedup
        self._engine.dedup_cache.remember(record)
        _logger.info("Alerta %s reaberto", alert_id)
        return record

    # --- Consultas ------------------------------------------------- #

    def get_alert(self, alert_id: str) -> AlertRecord | None:
        """Buscar alerta por ID.

        Args:
            alert_id: ID do alerta.

        Returns:
            :class:`AlertRecord` ou ``None``.
        """
        return self._store.get(alert_id)

    def list_alerts(
        self,
        *,
        severity: Severity | None = None,
        status: AlertStatus | None = None,
        source: str | None = None,
        rule_id: str | None = None,
        since: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AlertRecord]:
        """Listar alertas com filtros e paginacao.

        Args:
            severity: Filtrar por severidade.
            status: Filtrar por status.
            source: Filtrar por origem.
            rule_id: Filtrar por regra.
            since: Filtrar por ``last_seen_at >=``.
            limit: Max resultados (default 50).
            offset: Paginacao (default 0).

        Returns:
            Lista ordenada por ``last_seen_at DESC``.
        """
        return self._store.list_alerts(
            severity=severity,
            status=status,
            source=source,
            rule_id=rule_id,
            since=since,
            limit=limit,
            offset=offset,
        )

    def stats(self) -> dict[str, Any]:
        """Retornar estatisticas combinadas (store + engine).

        Returns:
            Dicionario com ``store`` (SQLite) e ``engine`` (processamento).
        """
        return {
            "store": self._store.stats(),
            "engine": self._engine.stats(),
            "dedup_cache_size": len(self._engine.dedup_cache),
        }

    # --- Regras ---------------------------------------------------- #

    def add_rule(self, rule: AlertRule) -> None:
        """Adicionar regra ao engine.

        Args:
            rule: Regra a adicionar.

        Raises:
            ValueError: Se ``rule.rule_id`` ja existe.
        """
        self._engine.add_rule(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remover regra do engine.

        Args:
            rule_id: ID da regra.

        Returns:
            ``True`` se removida, ``False`` se nao encontrada.
        """
        return self._engine.remove_rule(rule_id)

    def list_rules(self) -> list[AlertRule]:
        """Retornar regras ativas do engine."""
        return self._engine.rules.list_rules()

    def clear(self) -> int:
        """Remover todos os alertas (store + cache).

        Returns:
            Quantidade removida do store.
        """
        count = self._store.clear()
        self._engine.dedup_cache.clear()
        return count

    # --- Investigação (M4.4) ---

    def add_comment(self, alert_id: str, author: str, body: str) -> dict[str, Any]:
        """Adicionar comentário de investigação a um alerta."""
        comment = self._store.add_comment(alert_id, author, body)
        return comment.to_dict()

    def get_comments(self, alert_id: str) -> list[dict[str, Any]]:
        """Listar comentários de investigação de um alerta."""
        return [c.to_dict() for c in self._store.get_comments(alert_id)]

    def list_related_alerts(
        self, fingerprint: str, exclude_id: str | None = None
    ) -> list[AlertRecord]:
        """Listar alertas com o mesmo fingerprint (eventos correlacionados)."""
        return self._store.get_by_fingerprint(fingerprint, exclude_id=exclude_id)

    # --- Internos -------------------------------------------------- #

    def _hydrate_dedup_cache(self) -> None:
        """Hidratar cache de dedup com alertas ativos do banco.

        Carrega todos os alertas em status ``NEW`` ou ``ACKNOWLEDGED``
        para o cache do engine, permitindo dedup warming-up apos restart.
        """
        active = self._store.list_alerts(status=AlertStatus.NEW, limit=10000)
        for record in active:
            self._engine.dedup_cache.remember(record)
        active_ack = self._store.list_alerts(status=AlertStatus.ACKNOWLEDGED, limit=10000)
        for record in active_ack:
            self._engine.dedup_cache.remember(record)
        total = len(active) + len(active_ack)
        if total > 0:
            _logger.info("Cache de dedup hidratado com %d alertas ativos", total)
