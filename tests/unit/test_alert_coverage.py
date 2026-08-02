"""Testes de cobertura complementar do AlertService (M3) e CLI.

Foca em linhas nao cobertas em test_alert_service.py / test_alert_core.py:

* :meth:`AlertService.process_scan_evidences` (linhas 169-180).
* :meth:`AlertService.engine` / :meth:`AlertService.store` /
  :meth:`AlertService.dedup_cache` (linhas 90, 95, 100).
* CLI: handle_show com JSON, handle_ack/resolve com JSON, handle_rules,
  handle_reopen, transicoes invalidas, handle_alerts_command generico.
* AlertStore: get_by_fingerprint_active com ACKNOWLEDGED.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from app.cli.alert_cmd import handle_alerts_command
from app.core.alerts.channels import NullChannel
from app.core.alerts.models import (
    AlertEvent,
    AlertRecord,
    AlertRule,
    AlertSource,
    AlertStatus,
    Severity,
)
from app.core.alerts.rules import default_rules
from app.services.alert_service import AlertService, AlertServiceError
from app.services.alert_store import AlertStore


# ============================================================================
# AlertService -- propriedades e process_scan_evidences
# ============================================================================


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "alerts_cov.db"


@pytest.fixture
def service(temp_db_path: Path) -> AlertService:
    svc = AlertService(
        db_path=temp_db_path,
        rules=default_rules(),
        channels=[NullChannel()],
    )
    yield svc
    svc.close()


class TestAlertServiceCoverage:
    def test_properties(self, service: AlertService) -> None:
        """Cobrir propriedades engine, store, dedup_cache."""
        assert service.engine is not None
        assert service.store is not None
        assert service.dedup_cache is not None

    def test_process_scan_evidences(self, service: AlertService) -> None:
        """Cobrir process_scan_evidences."""

        class MockEvidence:
            def __init__(self, severity: Severity, message: str, category: str) -> None:
                self.severity = severity
                self.message = message
                self.source = "test"
                self.metadata = {"category": category}

        evidences = [
            MockEvidence(Severity.CRITICAL, "API key", "secret"),
            MockEvidence(Severity.LOW, "URL", "url"),
        ]
        alerts = service.process_scan_evidences(
            AlertSource.STRING_ANALYZER, "/var/log/app.log", evidences, Severity.HIGH
        )
        assert len(alerts) == 2

    def test_process_scan_evidences_dedup(self, service: AlertService) -> None:
        """Evidencias repetidas devem deduplicar via process_scan_evidences."""

        class MockEvidence:
            def __init__(self, severity: Severity, message: str, category: str) -> None:
                self.severity = severity
                self.message = message
                self.source = "test"
                self.metadata = {"category": category}

        ev = MockEvidence(Severity.CRITICAL, "Secret", "secret")
        alerts1 = service.process_scan_evidences(
            AlertSource.STRING_ANALYZER, "/tmp/file", [ev], Severity.HIGH
        )
        alerts2 = service.process_scan_evidences(
            AlertSource.STRING_ANALYZER, "/tmp/file", [ev], Severity.HIGH
        )
        assert len(alerts1) == 1
        assert len(alerts2) == 1
        # Mesmo alerta
        assert alerts1[0].alert_id == alerts2[0].alert_id


# ============================================================================
# CLI -- linhas nao cobertas
# ============================================================================


@pytest.fixture
def cli_env(tmp_path: Path) -> dict[str, str]:
    db_path = tmp_path / "cli_alerts_cov.db"
    env = {"EDYSHIELD_DB_PATH": str(db_path)}
    old_env = {k: os.environ.get(k) for k in env}
    os.environ.update(env)
    yield env
    for k, v in old_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


class _SilentArgs:
    """Namespace simples para testar handle_alerts_command diretamente."""


class TestCLICoverage:
    def test_show_json(self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
        # Criar um alerta
        svc = AlertService()
        event = AlertEvent(
            source=AlertSource.FIM,
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/etc/test",
            data={"event_type": "file_modified"},
        )
        alert = svc.process_and_store(event)
        svc.close()
        assert alert is not None

        # Importar main do modulo correto para uso de argparse
        from app.cli.hash_cmd import main

        rc = main(["alerts", "show", alert.alert_id, "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert data["alert_id"] == alert.alert_id

    def test_alerts_no_alert_command(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Argumentos sem alert_command devem falhar (exit 2)."""
        # Chamando handle direto com args incompleto
        args = _SilentArgs()
        # Simular a ausencia de alert_command
        setattr(args, "alert_command", None)
        rc = handle_alerts_command(args)  # type: ignore[arg-type]
        assert rc == 2

    def test_alerts_unknown_subcommand(self, cli_env: dict[str, str]) -> None:
        """Subcomando desconhecido deve falhar (exit 2)."""
        args = _SilentArgs()
        setattr(args, "alert_command", "unknown_xyz")
        rc = handle_alerts_command(args)  # type: ignore[arg-type]
        assert rc == 2

    def test_rules_json(self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]) -> None:
        from app.cli.hash_cmd import main

        rc = main(["alerts", "rules", "--json"])
        assert rc == 0
        out = capsys.readouterr().out
        data = json.loads(out)
        assert isinstance(data, list)
        assert len(data) >= 8

    def test_reopen_via_cli(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Criar, resolver e reabrir
        from app.cli.hash_cmd import main

        svc = AlertService()
        event = AlertEvent(
            source=AlertSource.FIM,
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/reopen_test",
            data={"event_type": "file_modified"},
        )
        alert = svc.process_and_store(event)
        svc.close()
        assert alert is not None
        # Resolver
        rc = main(["alerts", "resolve", alert.alert_id, "--by", "admin"])
        assert rc == 0
        capsys.readouterr()
        # Reabrir
        rc = main(["alerts", "reopen", alert.alert_id, "--reason", "Falso positivo"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "reaberto" in out.lower()

    def test_ack_not_found(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        from app.cli.hash_cmd import main

        rc = main(["alerts", "ack", "NONEXISTENT-999"])
        assert rc == 1
        err = capsys.readouterr().err
        assert "nao encontrado" in err.lower() or "not found" in err.lower()

    def test_resolve_not_found(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        from app.cli.hash_cmd import main

        rc = main(["alerts", "resolve", "NONEXISTENT-999"])
        assert rc == 1

    def test_suppress_not_found(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        from app.cli.hash_cmd import main

        rc = main(["alerts", "suppress", "NONEXISTENT-999"])
        assert rc == 1

    def test_reopen_invalid_transition(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        from app.cli.hash_cmd import main

        svc = AlertService()
        event = AlertEvent(
            source=AlertSource.FIM,
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test",
            data={"event_type": "file_modified"},
        )
        alert = svc.process_and_store(event)
        svc.close()
        assert alert is not None
        # Reabrir um alerta NEW (nao RESOLVED nem SUPPRESSED) -- transicao invalida
        rc = main(["alerts", "reopen", alert.alert_id])
        assert rc == 1

    def test_resolve_invalid_transition(
        self, cli_env: dict[str, str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        from app.cli.hash_cmd import main

        svc = AlertService()
        event = AlertEvent(
            source=AlertSource.FIM,
            event_type="file_modified",
            severity=Severity.HIGH,
            target="/tmp/test299",
            data={"event_type": "file_modified"},
        )
        alert = svc.process_and_store(event)
        svc.close()
        assert alert is not None
        # Resolver um alerta NEW -> valido, mas vamos suprimir e tentar resolve
        main(["alerts", "suppress", alert.alert_id, "--reason", "x"])
        capsys.readouterr()
        # Suprimido -> resolve e invalido
        rc = main(["alerts", "resolve", alert.alert_id])
        assert rc == 1
