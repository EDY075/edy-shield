"""Application-facing producer facade and runtime composition."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.alerts.models import AlertRecord
from app.core.fim.models import Baseline, FimDiff, Snapshot
from app.core.logging import get_logger
from app.core.storage import DEFAULT_DB_PATH
from app.plugins.contracts import ScanContext, ScanResult

from .client import SiemClient
from .config import SiemConfig, integration_enabled
from .mapper import EventMapper
from .outbox import EventBuilder, OutboxRepository
from .worker import DeliveryWorker

_logger = get_logger("integrations.edy_siem.producer")


class SiemProducer:
    """Persist real Shield facts to the outbox; never performs HTTP."""

    def __init__(self, repository: OutboxRepository, mapper: EventMapper) -> None:
        self.repository = repository
        self.mapper = mapper

    def enqueue_baseline(self, baseline: Baseline) -> list[str]:
        ids = self.repository.enqueue(
            [lambda sequence: self.mapper.baseline_created(baseline, sequence)]
        )
        _logger.info("Queued EDY SIEM baseline event")
        return ids

    def enqueue_fim_scan(
        self,
        baseline: Baseline,
        snapshot: Snapshot,
        diff: FimDiff,
        scan_id: str,
        duration_ms: int,
    ) -> list[str]:
        builders: list[EventBuilder] = []
        for change, paths in (
            ("added", diff.added),
            ("modified", diff.modified),
            ("removed", diff.removed),
        ):
            for path in paths:

                def build_change(
                    sequence: int,
                    change_value: str = change,
                    path_value: str = path,
                ) -> dict[str, Any]:
                    return self.mapper.file_change(
                        sequence=sequence,
                        change=change_value,
                        baseline=baseline,
                        snapshot=snapshot,
                        path=path_value,
                        scan_id=scan_id,
                    )

                builders.append(build_change)
        builders.append(
            lambda sequence: self.mapper.scan_completed(diff, scan_id, duration_ms, sequence)
        )
        ids = self.repository.enqueue(builders)
        _logger.info("Queued %d EDY SIEM FIM event(s)", len(ids))
        return ids

    def enqueue_hash_scan(self, context: ScanContext, result: ScanResult) -> list[str]:
        expected_raw = context.options.get("expected")
        if expected_raw is None or not isinstance(context.target, (str, Path)):
            return []
        expected = str(expected_raw).strip().lower()
        current = ""
        mismatch = False
        for finding in result.findings:
            if finding.metadata.get("source") == "file" and finding.metadata.get("hexdigest"):
                current = finding.metadata["hexdigest"].lower()
            if "MISMATCH" in finding.message.upper():
                mismatch = True
        if not mismatch or not current or expected == current:
            return []
        algorithm = str(context.options.get("algorithm", "SHA256"))
        ids = self.repository.enqueue(
            [
                lambda sequence: self.mapper.hash_mismatch(
                    path=str(context.target),
                    expected=expected,
                    current=current,
                    algorithm=algorithm,
                    timestamp=result.timestamp,
                    sequence=sequence,
                )
            ]
        )
        _logger.info("Queued EDY SIEM hash mismatch event")
        return ids

    def enqueue_alert(
        self, record: AlertRecord, action: str, previous_status: str | None = None
    ) -> list[str]:
        ids = self.repository.enqueue(
            [
                lambda sequence: self.mapper.security_alert(
                    record,
                    sequence,
                    action=action,
                    previous_status=previous_status,
                )
            ]
        )
        _logger.info("Queued EDY SIEM alert event")
        return ids


@dataclass(slots=True)
class IntegrationRuntime:
    producer: SiemProducer
    worker: DeliveryWorker | None

    def start(self) -> None:
        if self.worker is not None:
            self.worker.start()

    def close(self) -> None:
        if self.worker is not None:
            self.worker.stop()
        self.producer.repository.close()


def build_runtime(db_path: Path | None = None) -> IntegrationRuntime | None:
    """Build an opt-in runtime; invalid transport config never breaks Shield."""

    try:
        enabled = integration_enabled()
    except ValueError:
        _logger.error("EDY SIEM integration disabled because configuration is invalid")
        return None
    if not enabled:
        return None
    effective_db = db_path
    if effective_db is None:
        raw_db = os.getenv("EDYSHIELD_DB_PATH")
        effective_db = Path(raw_db) if raw_db else DEFAULT_DB_PATH
    repository = OutboxRepository(effective_db)
    mapper = EventMapper(repository.instance_id())
    producer = SiemProducer(repository, mapper)
    try:
        config = SiemConfig.from_env()
    except ValueError:
        _logger.error("EDY SIEM delivery is paused because URL/token configuration is invalid")
        return IntegrationRuntime(producer, None)
    worker = DeliveryWorker(repository, SiemClient(config), config)
    return IntegrationRuntime(producer, worker)


__all__ = ["IntegrationRuntime", "SiemProducer", "build_runtime"]
