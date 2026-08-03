"""Testes unitarios do Core de Alertas (M3) -- models, dedup, channels, rules, engine.

Suites:

* :class:`TestAlertModels` -- Severity, AlertStatus, AlertRecord, AlertRule,
  compute_fingerprint, now_iso, to_dict/from_dict, formatacao segura.
* :class:`TestDedupCache` -- cache thread-safe, increment, lookup, forget.
* :class:`TestAlertChannels` -- Console, File, Composite, Null channels.
* :class:`TestRuleEvaluator` -- operadores eq, ne, gt, gte, lt, lte, contains,
  regex, in, exists.
* :class:`TestRuleRegistry` -- registro, remocao, avaliacao, default_rules.
* :class:`TestAlertEngine` -- process_event, dedup, supressao, dispatch,
  process_scan_result, stats.
"""

from __future__ import annotations

import logging
import os
import tempfile
import threading

import pytest

from app.core.alerts.channels import (
    BaseAlertChannel,
    CompositeChannel,
    ConsoleChannel,
    FileChannel,
    NullChannel,
)
from app.core.alerts.deduplicator import DedupCache
from app.core.alerts.engine import AlertEngine
from app.core.alerts.models import (
    AlertAction,
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertSource,
    AlertStatus,
    Severity,
    compute_fingerprint,
    now_iso,
    render_template,
    severity_rank,
)
from app.core.alerts.rules import RuleRegistry, default_rules, evaluate_condition

# ============================================================================
# M3-T01: Models
# ============================================================================


class TestAlertModels:
    def test_severity_values(self) -> None:
        assert Severity.INFO.value == "INFO"
        assert Severity.LOW.value == "LOW"
        assert Severity.MEDIUM.value == "MEDIUM"
        assert Severity.HIGH.value == "HIGH"
        assert Severity.CRITICAL.value == "CRITICAL"

    def test_severity_rank(self) -> None:
        assert severity_rank(Severity.INFO) == 0
        assert severity_rank(Severity.CRITICAL) == 4

    def test_alert_status_transitions(self) -> None:
        assert AlertStatus.NEW.value == "NEW"
        assert AlertStatus.ACKNOWLEDGED.value == "ACKNOWLEDGED"
        assert AlertStatus.RESOLVED.value == "RESOLVED"
        assert AlertStatus.SUPPRESSED.value == "SUPPRESSED"

    def test_alert_action_values(self) -> None:
        assert AlertAction.ACKNOWLEDGE.value == "acknowledge"
        assert AlertAction.RESOLVE.value == "resolve"
        assert AlertAction.SUPPRESS.value == "suppress"
        assert AlertAction.REOPEN.value == "reopen"

    def test_alert_source_constants(self) -> None:
        assert AlertSource.FIM == "fim"
        assert AlertSource.STRING_ANALYZER == "string_analyzer"
        assert AlertSource.ENTROPY_ANALYZER == "entropy_analyzer"
        assert AlertSource.LOG_ANALYZER == "log_analyzer"
        assert AlertSource.MANUAL == "manual"

    def test_now_iso_format(self) -> None:
        ts = now_iso()
        assert ts.endswith("+00:00") or ts.endswith("Z")
        assert "T" in ts

    def test_compute_fingerprint_deterministic(self) -> None:
        fp1 = compute_fingerprint("fim", "FIM_MODIFIED", "/etc/passwd")
        fp2 = compute_fingerprint("fim", "FIM_MODIFIED", "/etc/passwd")
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_compute_fingerprint_different(self) -> None:
        fp1 = compute_fingerprint("fim", "FIM_MODIFIED", "/etc/passwd")
        fp2 = compute_fingerprint("string_analyzer", "STRING_SECRET", "/etc/passwd")
        assert fp1 != fp2

    def test_alert_record_defaults(self) -> None:
        record = AlertRecord()
        assert record.alert_id.startswith("ALT-")
        assert record.status == AlertStatus.NEW
        assert record.severity == Severity.MEDIUM
        assert record.count == 1
        assert record.details == {}

    def test_alert_record_to_dict(self) -> None:
        record = AlertRecord(
            alert_id="ALT-TEST001",
            fingerprint="abc123",
            title="Teste",
            description="Descricao teste",
            source="fim",
            rule_id="FIM_MODIFIED",
            severity=Severity.HIGH,
            status=AlertStatus.NEW,
            target="/etc/test",
            count=3,
        )
        d = record.to_dict()
        assert d["alert_id"] == "ALT-TEST001"
        assert d["severity"] == "HIGH"
        assert d["status"] == "NEW"
        assert d["count"] == 3

    def test_alert_record_from_dict(self) -> None:
        original = AlertRecord(
            alert_id="ALT-FROM001",
            fingerprint="def456",
            title="From dict",
            description="Teste de deserializacao",
            source="string_analyzer",
            rule_id="STRING_SECRET",
            severity=Severity.CRITICAL,
            status=AlertStatus.ACKNOWLEDGED,
            target="/var/log/test.log",
            count=5,
            details={"category": "secret", "match": "api_key"},
            acknowledged_by="admin",
        )
        d = original.to_dict()
        restored = AlertRecord.from_dict(d)
        assert restored.alert_id == original.alert_id
        assert restored.severity == Severity.CRITICAL
        assert restored.status == AlertStatus.ACKNOWLEDGED
        assert restored.details["category"] == "secret"
        assert restored.acknowledged_by == "admin"

    def test_alert_rule_defaults(self) -> None:
        rule = AlertRule(
            rule_id="TEST_RULE",
            name="Regra de teste",
            source="*",
            condition_key="event_type",
            operator="eq",
            condition_value="file_modified",
            target_severity=Severity.HIGH,
            title_template="Arquivo {target} modificado",
            description_template="O arquivo {target} foi modificado.",
        )
        assert rule.enabled is True
        assert rule.suppression_window_seconds == 300
        assert rule.priority == 100

    def test_render_template_safe(self) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
        )
        rule = AlertRule(
            rule_id="FIM_MODIFIED",
            name="Test",
            source="*",
            condition_key="event_type",
            operator="eq",
            condition_value="file_modified",
            target_severity=Severity.HIGH,
            title_template="Arquivo {target} - {event_type}",
            description_template="Alerta {severity} no alvo {target}",
        )
        title = render_template(rule.title_template, event, rule)
        assert "Arquivo" in title
        assert "/etc/passwd" in title
        assert "file_modified" in title

    def test_render_template_missing_key(self) -> None:
        """Chaves ausentes no template nao causam KeyError."""
        event = AlertEvent(source="fim", event_type="test", severity=Severity.INFO, target="/tmp/x")
        rule = AlertRule(
            rule_id="X",
            name="X",
            source="*",
            condition_key="event_type",
            operator="eq",
            condition_value="test",
            target_severity=Severity.INFO,
            title_template="Teste {missing_key} {target}",
            description_template="Desc {target}",
        )
        title = render_template(rule.title_template, event, rule)
        assert "{missing_key}" in title
        assert "/tmp/x" in title


# ============================================================================
# M3-T02: DedupCache
# ============================================================================


class TestDedupCache:
    def test_lookup_empty(self) -> None:
        cache = DedupCache()
        assert cache.lookup("nonexistent") is None

    def test_remember_and_lookup(self) -> None:
        cache = DedupCache()
        record = AlertRecord(
            fingerprint="abc123", title="Teste", source="fim", rule_id="FIM_MODIFIED"
        )
        cache.remember(record)
        found = cache.lookup("abc123")
        assert found is not None
        assert found.alert_id == record.alert_id

    def test_increment(self) -> None:
        cache = DedupCache()
        record = AlertRecord(fingerprint="xyz789", source="fim", rule_id="FIM_MODIFIED", count=1)
        cache.remember(record)
        cache.increment(record)
        assert record.count == 2

    def test_forget(self) -> None:
        cache = DedupCache()
        record = AlertRecord(fingerprint="forget-me", source="fim", rule_id="FIM_MODIFIED")
        cache.remember(record)
        assert len(cache) == 1
        cache.forget("forget-me")
        assert len(cache) == 0

    def test_clear(self) -> None:
        cache = DedupCache()
        cache.remember(AlertRecord(fingerprint="a", source="fim", rule_id="FIM"))
        cache.remember(AlertRecord(fingerprint="b", source="fim", rule_id="FIM"))
        assert len(cache) == 2
        cache.clear()
        assert len(cache) == 0

    def test_contains(self) -> None:
        cache = DedupCache()
        record = AlertRecord(fingerprint="abc", source="fim", rule_id="FIM")
        cache.remember(record)
        assert "abc" in cache
        assert "def" not in cache

    def test_thread_safety(self) -> None:
        """Acesso concorrente nao deve causar erros."""
        cache = DedupCache()
        errors: list[Exception] = []

        def worker(worker_id: int) -> None:
            try:
                for i in range(100):
                    fp = f"fp-{worker_id}-{i}"
                    r = AlertRecord(fingerprint=fp, source="test", rule_id=f"R{worker_id}")
                    cache.remember(r)
                    _ = cache.lookup(fp)
                    cache.increment(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(tid,)) for tid in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert len(cache) == 1000


# ============================================================================
# M3-T03: Canais
# ============================================================================


class TestAlertChannels:
    def test_null_channel(self) -> None:
        channel = NullChannel()
        record = AlertRecord(title="Teste", source="fim", rule_id="FIM")
        # Nao deve levantar excecao
        channel.send(record)
        channel.send(record, is_update=True)

    def test_console_channel(self, caplog: pytest.LogCaptureFixture) -> None:
        """ConsoleChannel deve logar no logger apropriado."""
        caplog.set_level(logging.INFO)
        channel = ConsoleChannel(logger_name="edyshield.alerts.test")
        record = AlertRecord(
            title="Alerta console", source="fim", rule_id="FIM", severity=Severity.HIGH
        )
        channel.send(record)
        assert "Alerta console" in caplog.text

    def test_file_channel(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, encoding="utf-8"
        ) as tmp:
            log_path = tmp.name
        try:
            channel = FileChannel(path=log_path)
            record = AlertRecord(
                title="Teste file channel",
                source="string_analyzer",
                rule_id="STRING_SECRET",
                severity=Severity.CRITICAL,
            )
            channel.send(record)
            channel.send(record, is_update=True)
            with open(log_path, encoding="utf-8") as f:
                content = f.read()
            assert "Teste file channel" in content
            assert "[NEW]" in content or "[UPDATE]" in content
        finally:
            if os.path.exists(log_path):
                os.unlink(log_path)

    def test_composite_channel(self) -> None:
        sent_new: list[bool] = []
        sent_update: list[bool] = []

        class TrackingChannel(BaseAlertChannel):
            def send(self, record: AlertRecord, is_update: bool = False) -> None:
                sent_new.append(True)
                sent_update.append(is_update)

        composite = CompositeChannel([TrackingChannel(), TrackingChannel()])
        record = AlertRecord(title="Teste", source="fim", rule_id="FIM")
        composite.send(record, is_update=False)
        assert len(sent_new) == 2
        assert sent_update == [False, False]


# ============================================================================
# M3-T04: Rule Evaluation
# ============================================================================


class TestRuleEvaluation:
    def test_eq(self) -> None:
        rule = AlertRule(
            rule_id="R1",
            name="R1",
            source="*",
            condition_key="event_type",
            operator="eq",
            condition_value="file_modified",
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"event_type": "file_modified"}) is True
        assert evaluate_condition(rule, {"event_type": "other"}) is False

    def test_ne(self) -> None:
        rule = AlertRule(
            rule_id="R2",
            name="R2",
            source="*",
            condition_key="event_type",
            operator="ne",
            condition_value="ignored",
            target_severity=Severity.LOW,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"event_type": "critical"}) is True
        assert evaluate_condition(rule, {"event_type": "ignored"}) is False

    def test_gt(self) -> None:
        rule = AlertRule(
            rule_id="R3",
            name="R3",
            source="*",
            condition_key="entropy",
            operator="gt",
            condition_value=6.0,
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"entropy": 7.5}) is True
        assert evaluate_condition(rule, {"entropy": 6.0}) is False
        assert evaluate_condition(rule, {"entropy": 5.0}) is False

    def test_gte(self) -> None:
        rule = AlertRule(
            rule_id="R4",
            name="R4",
            source="*",
            condition_key="entropy",
            operator="gte",
            condition_value=6.0,
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"entropy": 6.0}) is True
        assert evaluate_condition(rule, {"entropy": 5.9}) is False

    def test_lt(self) -> None:
        rule = AlertRule(
            rule_id="R5",
            name="R5",
            source="*",
            condition_key="score",
            operator="lt",
            condition_value=50,
            target_severity=Severity.LOW,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"score": 30}) is True
        assert evaluate_condition(rule, {"score": 50}) is False

    def test_lte(self) -> None:
        rule = AlertRule(
            rule_id="R6",
            name="R6",
            source="*",
            condition_key="score",
            operator="lte",
            condition_value=50,
            target_severity=Severity.LOW,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"score": 50}) is True
        assert evaluate_condition(rule, {"score": 51}) is False

    def test_contains(self) -> None:
        rule = AlertRule(
            rule_id="R7",
            name="R7",
            source="*",
            condition_key="category",
            operator="contains",
            condition_value="secret",
            target_severity=Severity.CRITICAL,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"category": "my_secret_key"}) is True
        assert evaluate_condition(rule, {"category": "url"}) is False

    def test_regex(self) -> None:
        rule = AlertRule(
            rule_id="R8",
            name="R8",
            source="*",
            condition_key="message",
            operator="regex",
            condition_value=r"AKIA[0-9A-Z]{16}",
            target_severity=Severity.CRITICAL,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"message": "Found AKIA1234567890123456"}) is True
        assert evaluate_condition(rule, {"message": "No secrets here"}) is False

    def test_in_operator(self) -> None:
        rule = AlertRule(
            rule_id="R9",
            name="R9",
            source="*",
            condition_key="level",
            operator="in",
            condition_value=["HIGH", "CRITICAL"],
            target_severity=Severity.CRITICAL,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"level": "HIGH"}) is True
        assert evaluate_condition(rule, {"level": "LOW"}) is False

    def test_exists(self) -> None:
        rule = AlertRule(
            rule_id="R10",
            name="R10",
            source="*",
            condition_key="event_type",
            operator="exists",
            condition_value=True,
            target_severity=Severity.INFO,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"event_type": "anything"}) is True
        assert evaluate_condition(rule, {"other": "x"}) is False

    def test_missing_key(self) -> None:
        """Chave ausente nao deve causar excecao (exceto 'exists')."""
        rule = AlertRule(
            rule_id="R11",
            name="R11",
            source="*",
            condition_key="nonexistent",
            operator="eq",
            condition_value="x",
            target_severity=Severity.LOW,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"other": "x"}) is False

    def test_numeric_string_conversion(self) -> None:
        """Strings numericas devem ser convertiveis para comparacao."""
        rule = AlertRule(
            rule_id="R12",
            name="R12",
            source="*",
            condition_key="score",
            operator="gt",
            condition_value="50",
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        assert evaluate_condition(rule, {"score": "100"}) is True


# ============================================================================
# M3-T05: RuleRegistry
# ============================================================================


class TestRuleRegistry:
    def test_default_rules(self) -> None:
        rules = default_rules()
        assert len(rules) >= 8  # 7 default + 1 catch-all
        ids = {r.rule_id for r in rules}
        assert "FIM_MODIFIED" in ids
        assert "STRING_SECRET" in ids
        assert "ENTROPY_HIGH" in ids
        assert "DEFAULT_CATCH_ALL" in ids

    def test_add_rule(self) -> None:
        registry = RuleRegistry()
        rule = AlertRule(
            rule_id="NEW_RULE",
            name="Nova",
            source="*",
            condition_key="x",
            operator="eq",
            condition_value="y",
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        registry.add(rule)
        assert len(registry) == 1

    def test_add_duplicate_raises(self) -> None:
        registry = RuleRegistry()
        rule = AlertRule(
            rule_id="DUP",
            name="Dup",
            source="*",
            condition_key="x",
            operator="eq",
            condition_value="y",
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
        )
        registry.add(rule)
        with pytest.raises(ValueError, match="ja existe"):
            registry.add(rule)

    def test_remove_rule(self) -> None:
        registry = RuleRegistry(default_rules())
        assert registry.remove("NONEXISTENT") is False
        assert registry.remove("FIM_MODIFIED") is True

    def test_get_rule(self) -> None:
        registry = RuleRegistry(default_rules())
        rule = registry.get("FIM_MODIFIED")
        assert rule is not None
        assert rule.name == "Arquivo modificado"
        assert registry.get("NONEXISTENT") is None

    def test_evaluate_match(self) -> None:
        registry = RuleRegistry(default_rules())
        rule = registry.evaluate("fim", "file_modified", {"event_type": "file_modified"})
        assert rule is not None
        assert rule.rule_id == "FIM_MODIFIED"

    def test_evaluate_no_match(self) -> None:
        registry = RuleRegistry(
            [
                AlertRule(
                    rule_id="R",
                    name="R",
                    source="a",
                    condition_key="x",
                    operator="eq",
                    condition_value="a",
                    target_severity=Severity.INFO,
                    title_template="T",
                    description_template="D",
                )
            ]
        )
        rule = registry.evaluate("b", "x", {"x": "a"})
        assert rule is None  # source nao corresponde

    def test_catch_all_fallback(self) -> None:
        registry = RuleRegistry(default_rules())
        # Evento de origem/evento desconhecido deve cair no DEFAULT_CATCH_ALL
        rule = registry.evaluate("unknown_source", "any_event", {"event_type": "any_event"})
        assert rule is not None
        assert rule.rule_id == "DEFAULT_CATCH_ALL"

    def test_disabled_rule_skipped(self) -> None:
        enabled_rule = AlertRule(
            rule_id="ENABLED",
            name="Enabled",
            source="*",
            condition_key="x",
            operator="eq",
            condition_value="y",
            target_severity=Severity.HIGH,
            title_template="T",
            description_template="D",
            enabled=True,
            priority=10,
        )
        disabled_rule = AlertRule(
            rule_id="DISABLED",
            name="Disabled",
            source="*",
            condition_key="x",
            operator="eq",
            condition_value="y",
            target_severity=Severity.CRITICAL,
            title_template="T",
            description_template="D",
            enabled=False,
            priority=1,
        )
        registry = RuleRegistry([disabled_rule, enabled_rule])
        rule = registry.evaluate("any", "e", {"x": "y"})
        assert rule is not None
        assert rule.rule_id == "ENABLED"  # disabled pulado


# ============================================================================
# M3-T06: AlertEngine
# ============================================================================


class TestAlertEngine:
    def test_no_match(self) -> None:
        """Sem regras registradas no engine, nenhum evento deve corresponder."""
        engine = AlertEngine(rules=[], channels=[NullChannel()])
        event = AlertEvent(
            source="unknown",
            event_type="anything",
            severity=Severity.INFO,
            target="/tmp/x",
            data={"event_type": "anything"},
        )
        result = engine.process_event(event)
        assert result.action == "no_match"
        assert result.alert is None

    def test_new_alert_created(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
            data={"event_type": "file_modified"},
        )
        result = engine.process_event(event)
        assert result.action == "created"
        assert result.alert is not None
        assert result.alert.source == "fim"
        assert result.alert.rule_id == "FIM_MODIFIED"
        assert result.alert.count == 1
        assert result.alert.fingerprint

    def test_dedup_same_event(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
            data={"event_type": "file_modified"},
        )
        r1 = engine.process_event(event)
        r2 = engine.process_event(event)
        r3 = engine.process_event(event)
        assert r1.action == "created"
        assert r2.action == "updated"
        assert r3.action == "updated"
        assert r1.alert.alert_id == r2.alert.alert_id
        assert r1.alert.count == 3
        assert r2.alert.count == 3
        assert r3.alert.count == 3

    def test_diff_fingerprints(self) -> None:
        """Eventos differentes (target diferente) = alertas diferentes."""
        engine = AlertEngine(channels=[NullChannel()])
        e1 = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
            data={"event_type": "file_modified"},
        )
        e2 = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/shadow",
            data={"event_type": "file_modified"},
        )
        r1 = engine.process_event(e1)
        r2 = engine.process_event(e2)
        assert r1.alert.alert_id != r2.alert.alert_id

    def test_catch_all(self) -> None:
        engine = AlertEngine(rules=None, channels=[NullChannel()])
        event = AlertEvent(
            source="crazy_plugin",
            event_type="signal",
            severity=Severity.INFO,
            target="/dev/null",
            data={"event_type": "signal"},
        )
        result = engine.process_event(event)
        assert result.action == "created"
        assert result.alert is not None
        assert result.rule_id == "DEFAULT_CATCH_ALL"

    def test_suppressed_alert_not_counted(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        # Criar alerta
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        r1 = engine.process_event(event)
        assert r1.alert is not None
        alert_id = r1.alert.alert_id
        # Simular supressao manual no cache
        alert = engine.dedup_cache.lookup(r1.alert.fingerprint)
        if alert:
            from app.core.alerts.models import AlertStatus

            alert.status = AlertStatus.SUPPRESSED
        # Novo evento com mesmo fingerprint deve ser ignorado
        r2 = engine.process_event(event)
        assert r2.action == "suppressed"

    def test_stats(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        assert engine.stats()["events_processed"] == 0
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/file",
            data={"event_type": "file_modified"},
        )
        engine.process_event(event)
        engine.process_event(event)
        engine.process_event(event)
        s = engine.stats()
        assert s["events_processed"] == 3
        assert s["alerts_created"] == 1
        assert s["alerts_updated"] == 2

    def test_reset_stats(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/x",
            data={"event_type": "file_modified"},
        )
        engine.process_event(event)
        assert engine.stats()["events_processed"] == 1
        engine.reset_stats()
        assert engine.stats()["events_processed"] == 0

    def test_add_rule_dynamic(self) -> None:
        engine = AlertEngine(channels=[NullChannel()])
        new_rule = AlertRule(
            rule_id="CUSTOM",
            name="Custom",
            source="*",
            condition_key="custom_field",
            operator="eq",
            condition_value="trigger",
            target_severity=Severity.CRITICAL,
            title_template="Custom: {target}",
            description_template="Desc",
            priority=1,
        )
        engine.add_rule(new_rule)
        event = AlertEvent(
            source="custom",
            event_type="test",
            severity=Severity.LOW,
            target="/custom/file",
            data={"custom_field": "trigger", "event_type": "test"},
        )
        result = engine.process_event(event)
        assert result.action == "created"
        assert result.rule_id == "CUSTOM"

    def test_remove_rule(self) -> None:
        engine = AlertEngine(
            rules=[
                AlertRule(
                    rule_id="TEMP",
                    name="Temp",
                    source="*",
                    condition_key="x",
                    operator="eq",
                    condition_value="y",
                    target_severity=Severity.HIGH,
                    title_template="T",
                    description_template="D",
                )
            ],
            channels=[NullChannel()],
        )
        event = AlertEvent(
            source="any",
            event_type="t",
            severity=Severity.HIGH,
            target="/tmp/x",
            data={"x": "y", "event_type": "t"},
        )
        assert engine.process_event(event).action == "created"
        engine.remove_rule("TEMP")
        # Agora deve cair no catch-all (se existir) ou no_match
        # Como so tem a regra TEMP, deve ser no_match
        event2 = AlertEvent(
            source="any",
            event_type="t",
            severity=Severity.HIGH,
            target="/tmp/x",
            data={"x": "y", "event_type": "t"},
        )
        result = engine.process_event(event2)
        assert result.action == "no_match" or result.rule_id == "DEFAULT_CATCH_ALL"

    def test_process_scan_result(self) -> None:
        """Testar adaptador de evidencias do ScanResult."""
        engine = AlertEngine(channels=[NullChannel()])

        class MockEvidence:
            def __init__(self, severity: Severity, message: str, category: str) -> None:
                self.severity = severity
                self.message = message
                self.source = "test"
                self.metadata = {"category": category, "line": 42}

        evidences = [
            MockEvidence(Severity.CRITICAL, "API key found", "secret"),
            MockEvidence(Severity.LOW, "URL found", "url"),
        ]
        results = engine.process_scan_result(
            AlertSource.STRING_ANALYZER, "/var/log/app.log", evidences, Severity.HIGH
        )
        assert len(results) == 2
        assert results[0].action in ("created", "updated")
        assert results[1].action in ("created", "updated")
