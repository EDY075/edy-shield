"""Background delivery worker with bounded retry and crash-safe leases."""

from __future__ import annotations

import random
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.logging import get_logger

from .client import InvalidResponseError, SiemClient, SiemResponse, TransportError
from .config import SiemConfig
from .outbox import LeasedBatch, OutboxRepository

_logger = get_logger("integrations.edy_siem.worker")
_RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}
_STRUCTURAL_HTTP = {400, 404, 409, 413, 415, 422}


class DeliveryWorker:
    """Poll the outbox independently from scans and local alert processing."""

    def __init__(
        self,
        repository: OutboxRepository,
        client: SiemClient,
        config: SiemConfig,
        *,
        random_source: random.Random | None = None,
    ) -> None:
        self.repository = repository
        self.client = client
        self.config = config
        self._random = random_source or random.Random()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="edy-siem-delivery",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self.config.total_timeout + 1.0)

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except Exception:
                _logger.exception("Unexpected EDY SIEM worker failure")
                worked = False
            self._stop.wait(0.0 if worked else self.config.poll_interval)

    def run_once(self, *, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        batch = self.repository.lease(
            now=current,
            lease_seconds=self.config.lease_seconds,
            limit=self.config.batch_size,
        )
        if batch is None:
            return False
        _logger.info("Sending EDY SIEM batch with %d event(s)", len(batch.items))
        try:
            response = self.client.send(batch.envelope())
        except (TransportError, InvalidResponseError) as exc:
            self._retry(batch, current, str(exc))
            _logger.warning("EDY SIEM unavailable; batch scheduled for retry")
            return True
        self._apply_response(batch, response, current)
        return True

    def _apply_response(
        self, batch: LeasedBatch, response: SiemResponse, current: datetime
    ) -> None:
        ids = [item.event_id for item in batch.items]
        if response.status == 202:
            self._apply_item_results(batch, response.payload, current)
            return
        if response.status == 409 and self._is_duplicate_ack(batch, response.payload):
            self.repository.mark_sent(ids, now=current)
            _logger.info("EDY SIEM confirmed an already delivered batch")
            return
        if response.status in {401, 403}:
            self.repository.retry_at(
                ids,
                current + timedelta(minutes=15),
                f"authentication rejected ({response.status})",
                now=current,
            )
            _logger.error("EDY SIEM rejected connector authentication; delivery paused")
            return
        if response.status in _RETRYABLE_HTTP:
            self._retry(batch, current, f"retryable HTTP {response.status}", response.retry_after)
            return
        if response.status in _STRUCTURAL_HTTP:
            self.repository.mark_dead_letter(ids, f"permanent HTTP {response.status}", now=current)
            _logger.error("EDY SIEM rejected a structural batch; moved to dead letter")
            return
        self.repository.mark_dead_letter(ids, f"unexpected HTTP {response.status}", now=current)

    @staticmethod
    def _is_duplicate_ack(batch: LeasedBatch, payload: dict[str, Any] | None) -> bool:
        """Accept a 409 only when every expected item is explicitly duplicate."""

        if payload is None or payload.get("batch_id") != batch.batch_id:
            return False
        results = payload.get("results")
        if not isinstance(results, list):
            return False
        expected = {item.event_id for item in batch.items}
        duplicates = {
            result.get("event_id")
            for result in results
            if isinstance(result, dict) and result.get("status") == "duplicate"
        }
        return len(results) == len(expected) and duplicates == expected

    def _apply_item_results(
        self,
        batch: LeasedBatch,
        payload: dict[str, Any] | None,
        current: datetime,
    ) -> None:
        if payload is None or payload.get("batch_id") != batch.batch_id:
            self._retry(batch, current, "invalid SIEM acknowledgement")
            return
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            self._retry(batch, current, "missing SIEM item results")
            return
        expected = {item.event_id for item in batch.items}
        accepted: list[str] = []
        rejected: list[str] = []
        seen: set[str] = set()
        for result in raw_results:
            if not isinstance(result, dict):
                self._retry(batch, current, "invalid SIEM item result")
                return
            event_id = result.get("event_id")
            status = result.get("status")
            if not isinstance(event_id, str) or event_id not in expected or event_id in seen:
                self._retry(batch, current, "unmatched SIEM item result")
                return
            seen.add(event_id)
            if status in {"accepted", "duplicate"}:
                accepted.append(event_id)
            elif status == "rejected":
                rejected.append(event_id)
            else:
                self._retry(batch, current, "unknown SIEM item status")
                return
        if seen != expected:
            self._retry(batch, current, "incomplete SIEM item results")
            return
        self.repository.mark_sent(accepted, now=current)
        self.repository.mark_dead_letter(rejected, "contract item rejected", now=current)
        _logger.info(
            "EDY SIEM batch acknowledged: %d delivered, %d rejected",
            len(accepted),
            len(rejected),
        )

    def _retry(
        self,
        batch: LeasedBatch,
        current: datetime,
        reason: str,
        retry_after: int | None = None,
    ) -> None:
        attempts = max(item.attempt_count for item in batch.items)
        ceiling = min(300.0, float(2 ** min(20, max(0, attempts - 1))))
        delay = float(retry_after) if retry_after is not None else self._random.uniform(0, ceiling)
        delay = min(delay, 900.0)
        self.repository.retry_at(
            [item.event_id for item in batch.items],
            current + timedelta(seconds=delay),
            reason,
            now=current,
        )


__all__ = ["DeliveryWorker"]
