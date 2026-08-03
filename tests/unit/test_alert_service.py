"""Testes do AlertService e AlertStore (M3) -- persistencia e ciclo de vida.

Suites:

* :class:`TestAlertStore` -- CRUD SQLite, filtros, stats.
* :class:`TestAlertService` -- process_and_store, ack/resolve/suppress/reopen,
  list, regras, hidratacao de cache.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.core.alerts.channels import NullChannel
from app.core.alerts.models import (
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertStatus,
    Severity,
)
from app.core.alerts.rules import default_rules
from app.services.alert_service import AlertService
from app.services.alert_store import AlertStore

# ============================================================================
# AlertStore
# ============================================================================


@pytest.fixture
def temp_db() -> Path:
    """Banco SQLite temporario (excluido no final)."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = Path(f.name)
    yield path
    if path.exists():
        path.unlink()
    # Limpar WAL/SHM se existirem
    for suffix in ("-wal", "-shm"):
        p = path.with_name(path.name + suffix)
        if p.exists():
            p.unlink()


class TestAlertStore:
    def test_save_and_get(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        record = AlertRecord(
            alert_id="ALT-STORE001",
            fingerprint="fp001",
            title="Test Store",
            description="Teste de persistencia",
            source="fim",
            rule_id="FIM_MODIFIED",
            severity=Severity.HIGH,
            status=AlertStatus.NEW,
            target="/etc/test",
            count=1,
            details={"key": "value"},
        )
        saved_id = store.save(record)
        assert saved_id == "ALT-STORE001"
        loaded = store.get("ALT-STORE001")
        assert loaded is not None
        assert loaded.alert_id == "ALT-STORE001"
        assert loaded.severity == Severity.HIGH
        assert loaded.details["key"] == "value"
        store.close()

    def test_get_nonexistent(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        assert store.get("NONEXISTENT") is None
        store.close()

    def test_list_alerts(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        for i in range(5):
            record = AlertRecord(
                alert_id=f"ALT-LIST{i:03d}",
                fingerprint=f"fp{i:03d}",
                title=f"Alerta {i}",
                description="",
                source="fim",
                rule_id="FIM_MODIFIED",
                severity=Severity.HIGH if i % 2 == 0 else Severity.LOW,
                status=AlertStatus.NEW if i < 3 else AlertStatus.ACKNOWLEDGED,
                target="/tmp/test",
            )
            store.save(record)
        # Sem filtros
        all_alerts = store.list_alerts(limit=10)
        assert len(all_alerts) == 5
        # Filtro por severidade
        high = store.list_alerts(severity=Severity.HIGH)
        assert len(high) == 3
        # Filtro por status
        new = store.list_alerts(status=AlertStatus.NEW)
        assert len(new) == 3
        # Paginacao
        p1 = store.list_alerts(limit=2, offset=0)
        p2 = store.list_alerts(limit=2, offset=2)
        assert len(p1) == 2
        assert len(p2) == 2
        # Nao devem se sobrepor
        ids1 = {a.alert_id for a in p1}
        ids2 = {a.alert_id for a in p2}
        assert ids1.isdisjoint(ids2)
        store.close()

    def test_update_status(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        record = AlertRecord(
            alert_id="ALT-UP001",
            fingerprint="fp",
            title="Up",
            description="",
            source="fim",
            rule_id="FIM",
            severity=Severity.HIGH,
            target="/tmp/x",
        )
        store.save(record)
        # Ack
        store.update_status("ALT-UP001", AlertStatus.ACKNOWLEDGED, acknowledged_by="admin")
        loaded = store.get("ALT-UP001")
        assert loaded is not None
        assert loaded.status == AlertStatus.ACKNOWLEDGED
        assert loaded.acknowledged_by == "admin"
        # Resolve
        store.update_status("ALT-UP001", AlertStatus.RESOLVED, resolved_by="admin")
        loaded = store.get("ALT-UP001")
        assert loaded.status == AlertStatus.RESOLVED
        store.close()

    def test_update_count(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        record = AlertRecord(
            alert_id="ALT-CNT001",
            fingerprint="fp",
            title="Count",
            description="",
            source="fim",
            rule_id="FIM",
            severity=Severity.HIGH,
            target="/tmp/x",
        )
        store.save(record)
        store.update_count("ALT-CNT001", 5, "2026-08-02T20:00:00+00:00")
        loaded = store.get("ALT-CNT001")
        assert loaded is not None
        assert loaded.count == 5
        store.close()

    def test_get_by_fingerprint_active(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        record = AlertRecord(
            alert_id="ALT-FP001",
            fingerprint="fp-abc",
            title="FP",
            description="",
            source="fim",
            rule_id="FIM",
            severity=Severity.HIGH,
            target="/tmp/x",
            status=AlertStatus.NEW,
        )
        store.save(record)
        found = store.get_by_fingerprint_active("fp-abc")
        assert found is not None
        assert found.alert_id == "ALT-FP001"
        # Nao deve encontrar resolvido
        store.update_status("ALT-FP001", AlertStatus.RESOLVED)
        assert store.get_by_fingerprint_active("fp-abc") is None
        store.close()

    def test_stats(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        for i in range(3):
            store.save(
                AlertRecord(
                    alert_id=f"ALT-STA{i:03d}",
                    fingerprint=f"fp{i}",
                    title=f"S{i}",
                    description="",
                    source="fim",
                    rule_id="FIM",
                    severity=Severity.HIGH,
                    target="/tmp/x",
                )
            )
        stats = store.stats()
        assert stats["total"] == 3
        assert stats["by_status"]["NEW"] == 3
        store.close()

    def test_clear(self, temp_db: Path) -> None:
        store = AlertStore(db_path=temp_db)
        store.save(
            AlertRecord(
                alert_id="ALT-CLR001",
                fingerprint="fp",
                title="X",
                description="",
                source="fim",
                rule_id="FIM",
                severity=Severity.HIGH,
                target="/tmp/x",
            )
        )
        store.save(
            AlertRecord(
                alert_id="ALT-CLR002",
                fingerprint="fp2",
                title="Y",
                description="",
                source="fim",
                rule_id="FIM",
                severity=Severity.HIGH,
                target="/tmp/x",
            )
        )
        assert store.count() == 2
        removed = store.clear()
        assert removed == 2
        assert store.count() == 0
        store.close()


# ============================================================================
# AlertService
# ============================================================================


@pytest.fixture
def service(temp_db: Path) -> AlertService:
    """AlertService com banco temporario e canais silenciosos."""
    svc = AlertService(
        db_path=temp_db,
        rules=default_rules(),
        channels=[NullChannel()],
    )
    yield svc
    svc.close()


class TestAlertService:
    def test_process_and_store_new(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        assert alert.alert_id is not None
        assert alert.status == AlertStatus.NEW
        # Verificar no banco
        loaded = service.get_alert(alert.alert_id)
        assert loaded is not None
        assert loaded.rule_id == "FIM_MODIFIED"

    def test_process_and_store_dedup(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/passwd",
            data={"event_type": "file_modified"},
        )
        a1 = service.process_and_store(event)
        a2 = service.process_and_store(event)
        a3 = service.process_and_store(event)
        assert a1 is not None
        assert a2 is not None
        assert a3 is not None
        assert a1.alert_id == a2.alert_id
        assert a1.alert_id == a3.alert_id
        # Verificar persistencia do count
        loaded = service.get_alert(a1.alert_id)
        assert loaded is not None
        assert loaded.count == 3

    def test_process_no_match(self, service: AlertService) -> None:
        event = AlertEvent(
            source="unknown",
            event_type="weird",
            severity=Severity.INFO,
            target="/tmp/x",
            data={"event_type": "weird"},
        )
        alert = service.process_and_store(event)
        assert alert is not None  # catch-all
        assert alert.rule_id == "DEFAULT_CATCH_ALL"

    def test_acknowledge(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        acked = service.acknowledge_alert(alert.alert_id, acked_by="admin")
        assert acked.status == AlertStatus.ACKNOWLEDGED
        assert acked.acknowledged_by == "admin"

    def test_acknowledge_invalid_transition(self, service: AlertService) -> None:
        """Ack em alerta ja resolvido deve falhar."""
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        service.resolve_alert(alert.alert_id)
        from app.services.alert_service import AlertServiceError

        with pytest.raises(AlertServiceError, match="Transicao invalida"):
            service.acknowledge_alert(alert.alert_id)

    def test_resolve(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        resolved = service.resolve_alert(alert.alert_id, resolved_by="admin", resolution_note="OK")
        assert resolved.status == AlertStatus.RESOLVED
        assert resolved.resolved_by == "admin"

    def test_suppress(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        suppressed = service.suppress_alert(alert.alert_id, reason="Noise")
        assert suppressed.status == AlertStatus.SUPPRESSED
        # Cache de dedup nao deve conter o fingerprint
        assert alert.fingerprint not in service.dedup_cache

    def test_reopen(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = service.process_and_store(event)
        assert alert is not None
        service.resolve_alert(alert.alert_id)
        reopened = service.reopen_alert(alert.alert_id, reason="Falso positivo")
        assert reopened.status == AlertStatus.NEW
        assert reopened.count == 1  # Resetado
        # Deve estar de volta no cache
        assert reopened.fingerprint in service.dedup_cache

    def test_list_filters(self, service: AlertService) -> None:
        # Criar alguns alertas com variacao
        for i in range(3):
            event = AlertEvent(
                source="fim",
                event_type="file_modified",
                severity=Severity.HIGH,
                target=f"/tmp/file{i}",
                data={"event_type": "file_modified"},
            )
            service.process_and_store(event)
        for i in range(2):
            event = AlertEvent(
                source="string_analyzer",
                event_type="evidence",
                severity=Severity.LOW,
                target=f"/tmp/log{i}",
                data={"category": "url", "event_type": "evidence"},
            )
            service.process_and_store(event)
        # Filtro por source
        fim_alerts = service.list_alerts(source="fim")
        assert len(fim_alerts) == 3
        str_alerts = service.list_alerts(source="string_analyzer")
        assert len(str_alerts) == 2
        # Todos
        all_alerts = service.list_alerts(limit=10)
        assert len(all_alerts) >= 5

    def test_stats(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        service.process_and_store(event)
        stats = service.stats()
        assert stats["store"]["total"] >= 1
        assert stats["engine"]["alerts_created"] >= 1

    def test_add_rule(self, service: AlertService) -> None:
        rule = AlertRule(
            rule_id="CLI_CUSTOM",
            name="CLI",
            source="*",
            condition_key="custom",
            operator="eq",
            condition_value="trigger",
            target_severity=Severity.CRITICAL,
            title_template="CLI: {target}",
            description_template="CLI desc",
            priority=1,
        )
        service.add_rule(rule)
        rules = service.list_rules()
        ids = [r.rule_id for r in rules]
        assert "CLI_CUSTOM" in ids

    def test_clear(self, service: AlertService) -> None:
        event = AlertEvent(
            source="fim",
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        service.process_and_store(event)
        assert service.stats()["store"]["total"] >= 1
        service.clear()
        assert service.stats()["store"]["total"] == 0
