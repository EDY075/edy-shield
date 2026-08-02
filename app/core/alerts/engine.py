"""Motor central de alertas (EDY Shield -- M3-T06).

O :class:`AlertEngine` e o componente central do Alert System (ADR-009).
Ele recebe :class:`~app.core.alerts.models.AlertEvent`, avalia contra
:class:`~app.core.alerts.models.AlertRule` registradas, aplica
deduplicacao por fingerprint temporal (ADR-010), supressao de alertas
e faz dispatch para os canais registrados.

100% stdlib: nao conhece SQLite nem I/O de rede. A persistencia e
responsabilidade do :class:`~app.services.alert_service.AlertService`,
que consome os alertas gerados pelo engine.

Fluxo:

1. ``process_event`` recebe evento.
2. Avalia regras via :class:`~app.core.alerts.rules.RuleRegistry`.
3. Se nenhuma regra corresponder, retorna ``None``.
4. Se regra corresponder, calcula fingerprint.
5. Verifica cache de dedup:
   - Hit dentro da janela -> incrementa count.
   - Miss ou janela expirada -> cria novo :class:`AlertRecord`.
6. Faz dispatch para canais registrados.
7. Retorna o alerta resultante.
"""

from __future__ import annotations

from typing import Any

from app.core.alerts.channels import BaseAlertChannel, CompositeChannel
from app.core.alerts.deduplicator import DedupCache, try_dedup
from app.core.alerts.models import (
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertStatus,
    Severity,
    compute_fingerprint,
    render_template,
    severity_rank,
)
from app.core.alerts.rules import RuleRegistry, default_rules

__all__ = ["AlertEngine", "EngineResult"]


class EngineResult:
    """Resultado de uma operacao do AlertEngine.

    Attributes:
        alert: Alerta resultante (``None`` se nenhum foi gerado).
        action: Acao tomada pelo engine (``"created"``, ``"updated"``,
            ``"suppressed"``, ``"no_match"``).
        rule_id: ID da regra que correspondeu (``None`` se nenhuma).
    """

    def __init__(
        self,
        alert: AlertRecord | None,
        action: str,
        rule_id: str | None = None,
    ) -> None:
        self.alert = alert
        self.action = action
        self.rule_id = rule_id


class AlertEngine:
    """Motor central de processamento de alertas.

    Thread-safe via ``DedupCache`` (RLock interno). O engine mantem
    estado em memoria apenas (regras + cache de dedup); a persistencia
    e delegada ao service layer.

    Args:
        rules: Lista de regras iniciais. Se ``None``, carrega as
            :func:`~app.core.alerts.rules.default_rules`.
        channels: Lista de canais para dispatch. Se ``None``, usa
            :class:`~app.core.alerts.channels.NullChannel` (silencioso).
        dedup_cache: Cache de dedup a reutilizar (para compartilhar
            com o service layer). Se ``None``, cria um novo.

    Attributes:
        rules: Repositorio de regras.
        channels: Canal composto de dispatch.
        dedup_cache: Cache de dedup.
    """

    def __init__(
        self,
        rules: list[AlertRule] | None = None,
        channels: list[BaseAlertChannel] | None = None,
        dedup_cache: DedupCache | None = None,
    ) -> None:
        self.rules = RuleRegistry(rules if rules is not None else default_rules())
        self._channels: list[BaseAlertChannel] = channels or []
        self._composite = CompositeChannel(list(self._channels))
        self.dedup_cache: DedupCache = dedup_cache or DedupCache()
        # Estatisticas internas
        self._stats: dict[str, int] = {
            "events_processed": 0,
            "alerts_created": 0,
            "alerts_updated": 0,
            "alerts_suppressed": 0,
            "no_match": 0,
        }

    # --- Configuracao dinamica --------------------------------------- #

    def add_rule(self, rule: AlertRule) -> None:
        """Adicionar regra ao repositorio.

        Args:
            rule: Regra a adicionar.

        Raises:
            ValueError: Se ``rule.rule_id`` ja existe.
        """
        self.rules.add(rule)

    def remove_rule(self, rule_id: str) -> bool:
        """Remover regra do repositorio.

        Args:
            rule_id: ID da regra a remover.

        Returns:
            ``True`` se removida, ``False`` se nao encontrada.
        """
        return self.rules.remove(rule_id)

    def add_channel(self, channel: BaseAlertChannel) -> None:
        """Adicionar canal de dispatch dinamicamente.

        Args:
            channel: Canal a adicionar.
        """
        self._channels.append(channel)
        self._composite.add(channel)

    # --- Processamento ----------------------------------------------- #

    def process_event(self, event: AlertEvent) -> EngineResult:
        """Processar um evento individual.

        Avalia regras, aplica dedup/supressao e faz dispatch nos canais.

        Args:
            event: Evento a processar.

        Returns:
            :class:`EngineResult` com o alerta resultante (ou ``None``)
            e a acao tomada.
        """
        self._stats["events_processed"] += 1

        # 1. Avaliar regras
        rule = self.rules.evaluate(event.source, event.event_type, event.data)
        if rule is None:
            self._stats["no_match"] += 1
            return EngineResult(None, "no_match", None)

        # 2. Calcular fingerprint
        fingerprint = compute_fingerprint(event.source, rule.rule_id, event.target)

        # 3. Tentar dedup
        dedup_result = try_dedup(
            self.dedup_cache,
            fingerprint,
            window_seconds=rule.suppression_window_seconds,
        )

        # 4. Verificar supressao (alerta SUPPRESSED no cache)
        if dedup_result.record is not None and dedup_result.record.status == AlertStatus.SUPPRESSED:
            self._stats["alerts_suppressed"] += 1
            return EngineResult(dedup_result.record, "suppressed", rule.rule_id)

        # 5a. Dedup hit -> alerta atualizado
        if dedup_result.merged and dedup_result.record is not None:
            # Atualizar severidade se a nova e maior
            if severity_rank(rule.target_severity) > severity_rank(dedup_result.record.severity):
                dedup_result.record.severity = rule.target_severity
            self._dispatch(dedup_result.record, is_update=True)
            self._stats["alerts_updated"] += 1
            return EngineResult(dedup_result.record, "updated", rule.rule_id)

        # 5b. Novo alerta
        alert = self._create_alert(event, rule, fingerprint)
        self.dedup_cache.remember(alert)
        self._dispatch(alert, is_update=False)
        self._stats["alerts_created"] += 1
        return EngineResult(alert, "created", rule.rule_id)

    def _create_alert(self, event: AlertEvent, rule: AlertRule, fingerprint: str) -> AlertRecord:
        """Criar um novo :class:`AlertRecord` a partir de evento + regra.

        Args:
            event: Evento de origem.
            rule: Regra que correspondeu.
            fingerprint: Hash pre-calculado.

        Returns:
            Novo :class:`AlertRecord` preenchido.
        """
        title = render_template(rule.title_template, event, rule)
        description = render_template(rule.description_template, event, rule)
        return AlertRecord(
            fingerprint=fingerprint,
            title=title,
            description=description,
            source=event.source,
            rule_id=rule.rule_id,
            severity=rule.target_severity,
            status=AlertStatus.NEW,
            target=event.target,
            count=1,
            first_seen_at=event.timestamp,
            last_seen_at=event.timestamp,
            details=dict(event.data),
        )

    def _dispatch(self, record: AlertRecord, is_update: bool) -> None:
        """Despachar alerta para todos os canais registrados.

        Args:
            record: Alerta a enviar.
            is_update: ``True`` se atualizacao (count++), ``False`` se novo.
        """
        self._composite.send(record, is_update=is_update)

    # --- Estatisticas ------------------------------------------------ #

    def stats(self) -> dict[str, int]:
        """Retornar estatisticas de processamento do engine.

        Returns:
            Dicionario com contadores de eventos processados, alertas
            criados, atualizados, suprimidos e sem match.
        """
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Zerar contadores de estatisticas (nao afeta o cache)."""
        for key in self._stats:
            self._stats[key] = 0

    # --- Adaptadores de ScanResult ----------------------------------- #

    def process_scan_result(
        self, source: str, target: str, evidences: list[Any], max_severity: Severity
    ) -> list[EngineResult]:
        """Aduz um ScanResult/AnalysisOutcome e gerar alertas resultantes.

        Para cada :class:`~app.plugins.contracts.Evidence` no ``ScanResult``,
        cria um :class:`AlertEvent` e processa pelo engine. Permite
        usar o engine como adaptador dos analisadores existentes sem
        acoplar diretamente as classes (Open-Closed).

        Args:
            source: Origem canonica (ex.: :attr:`~app.core.alerts.models.AlertSource.STRING_ANALYZER`).
            target: Recurso analisado (arquivo).
            evidences: Lista de evidencias (objetos com ``severity``,
                ``message``, ``source``, ``metadata``).
            max_severity: Severidade maxima do resultado.

        Returns:
            Lista de :class:`EngineResult`, um por evidencia processada.
        """
        results: list[EngineResult] = []
        for ev in evidences:
            # Extrair dados da evidencia de forma defensiva
            ev_severity = getattr(ev, "severity", max_severity)
            ev_message = getattr(ev, "message", "")
            ev_source = getattr(ev, "source", None) or ""
            ev_metadata = getattr(ev, "metadata", {}) or {}

            # Mapear categoria (se existir na metadata)
            category = (
                ev_metadata.get("category", "general")
                if isinstance(ev_metadata, dict)
                else "general"
            )

            event = AlertEvent(
                source=source,
                event_type="evidence",
                severity=ev_severity if isinstance(ev_severity, Severity) else max_severity,
                target=target,
                data={
                    "event_type": "evidence",
                    "category": category,
                    "message": ev_message,
                    "evidence_source": ev_source,
                    **(ev_metadata if isinstance(ev_metadata, dict) else {}),
                },
            )
            results.append(self.process_event(event))
        return results
