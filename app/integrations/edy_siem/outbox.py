"""Durable SQLite outbox for EDY SIEM telemetry."""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.core.storage import DEFAULT_DB_PATH, SQLiteDb

MAX_EVENT_BYTES = 64 * 1024
MAX_BATCH_BYTES = 1024 * 1024
MAX_OUTBOX_EVENTS = 50_000
MAX_OUTBOX_BYTES = 512 * 1024 * 1024
EventBuilder = Callable[[int], dict[str, Any]]
_logger = get_logger("integrations.edy_siem.outbox")


class OutboxCapacityError(Exception):
    """The durable queue is full; existing events remain untouched."""


def now_z(now: datetime | None = None) -> str:
    value = now or datetime.now(UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _safe_error(message: str) -> str:
    return " ".join(message.replace("\r", " ").replace("\n", " ").split())[:512]


@dataclass(frozen=True, slots=True)
class OutboxItem:
    event_id: str
    sequence: int
    event_type: str
    severity: str
    payload: dict[str, Any]
    attempt_count: int


@dataclass(frozen=True, slots=True)
class LeasedBatch:
    batch_id: str
    sent_at: str
    items: tuple[OutboxItem, ...]

    def envelope(self) -> dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "sent_at": self.sent_at,
            "events": [item.payload for item in self.items],
        }


class OutboxRepository:
    """Persist events before delivery and manage leases atomically."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db = SQLiteDb(db_path or DEFAULT_DB_PATH)

    @property
    def db_path(self) -> Path:
        return self._db.db_path

    def close(self) -> None:
        self._db.close()

    def instance_id(self) -> str:
        """Return the stable installation UUID, creating it once if absent."""

        def operation(conn: sqlite3.Connection) -> str:
            row = conn.execute(
                "SELECT instance_id FROM siem_integration_state WHERE state_id = 1"
            ).fetchone()
            if row is not None:
                return str(row["instance_id"])
            value = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO siem_integration_state "
                "(state_id, instance_id, next_sequence, dropped_count) "
                "VALUES (1, ?, 1, 0)",
                (value,),
            )
            return value

        return self._db.run_transaction(operation)

    def enqueue(self, builders: list[EventBuilder], *, now: datetime | None = None) -> list[str]:
        """Allocate sequences and persist mapped events in one local transaction."""

        if not builders:
            return []
        timestamp = now_z(now)

        def operation(conn: sqlite3.Connection) -> list[str] | None:
            row = conn.execute(
                "SELECT next_sequence FROM siem_integration_state WHERE state_id = 1"
            ).fetchone()
            if row is None:
                raise RuntimeError("SIEM instance identity was not initialized")
            sequence = int(row["next_sequence"])
            event_ids: list[str] = []
            prepared: list[tuple[dict[str, Any], bytes]] = []
            for builder in builders:
                payload = builder(sequence)
                encoded = _json_bytes(payload)
                prepared.append((payload, encoded))
                sequence += 1

            usage = conn.execute(
                "SELECT COUNT(*) AS event_count, COALESCE(SUM(payload_bytes), 0) AS byte_count "
                "FROM siem_outbox"
            ).fetchone()
            projected_events = int(usage["event_count"]) + len(prepared)
            projected_bytes = int(usage["byte_count"]) + sum(
                len(encoded) for _, encoded in prepared
            )
            if projected_events > MAX_OUTBOX_EVENTS or projected_bytes > MAX_OUTBOX_BYTES:
                conn.execute(
                    "UPDATE siem_integration_state "
                    "SET dropped_count = dropped_count + ?, last_enqueue_error = ? "
                    "WHERE state_id = 1",
                    (len(prepared), "outbox capacity reached"),
                )
                return None
            if projected_events >= int(MAX_OUTBOX_EVENTS * 0.8) or projected_bytes >= int(
                MAX_OUTBOX_BYTES * 0.8
            ):
                _logger.warning("EDY SIEM outbox usage is above 80%% of its local limit")

            sequence -= len(prepared)
            for payload, encoded in prepared:
                event_id = str(payload["event_id"])
                status = "pending" if len(encoded) <= MAX_EVENT_BYTES else "dead_letter"
                error = None if status == "pending" else "event exceeds 64 KiB"
                conn.execute(
                    """
                    INSERT INTO siem_outbox (
                        event_id, sequence, event_type, severity, payload, payload_bytes,
                        status, created_at, updated_at, next_attempt_at, last_error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        sequence,
                        str(payload["event_type"]),
                        str(payload["severity"]),
                        encoded.decode("utf-8"),
                        len(encoded),
                        status,
                        timestamp,
                        timestamp,
                        timestamp,
                        error,
                    ),
                )
                event_ids.append(event_id)
                sequence += 1
            conn.execute(
                "UPDATE siem_integration_state SET next_sequence = ? WHERE state_id = 1",
                (sequence,),
            )
            return event_ids

        result = self._db.run_transaction(operation)
        if result is None:
            raise OutboxCapacityError("EDY SIEM outbox capacity reached")
        return result

    def lease(
        self,
        *,
        now: datetime | None = None,
        lease_seconds: int = 30,
        limit: int = 100,
    ) -> LeasedBatch | None:
        """Recover expired leases and atomically reserve one size-limited batch."""

        current = now or datetime.now(UTC)
        current_z = now_z(current)
        lease_z = now_z(current + timedelta(seconds=lease_seconds))
        batch_id = str(uuid.uuid4())

        def operation(conn: sqlite3.Connection) -> LeasedBatch | None:
            conn.execute(
                """
                UPDATE siem_outbox
                SET status = 'pending', lease_expires_at = NULL, batch_id = NULL,
                    updated_at = ?, last_error = 'recovered expired delivery lease'
                WHERE status = 'in_flight' AND lease_expires_at <= ?
                """,
                (current_z, current_z),
            )
            rows = conn.execute(
                """
                SELECT event_id, sequence, event_type, severity, payload, payload_bytes,
                       attempt_count
                FROM siem_outbox
                WHERE status = 'pending' AND next_attempt_at <= ?
                ORDER BY CASE severity
                    WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END,
                    created_at, sequence
                LIMIT ?
                """,
                (current_z, max(1, min(limit, 100))),
            ).fetchall()
            selected: list[sqlite3.Row] = []
            for row in rows:
                candidate = [*selected, row]
                envelope = {
                    "batch_id": batch_id,
                    "sent_at": current_z,
                    "events": [json.loads(str(item["payload"])) for item in candidate],
                }
                if len(_json_bytes(envelope)) > MAX_BATCH_BYTES:
                    break
                selected = candidate
            if not selected:
                return None
            ids = [str(row["event_id"]) for row in selected]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"""
                UPDATE siem_outbox
                SET status = 'in_flight', updated_at = ?, last_attempt_at = ?,
                    lease_expires_at = ?, batch_id = ?, attempt_count = attempt_count + 1
                WHERE event_id IN ({placeholders})
                """,
                (current_z, current_z, lease_z, batch_id, *ids),
            )
            return LeasedBatch(
                batch_id=batch_id,
                sent_at=current_z,
                items=tuple(
                    OutboxItem(
                        event_id=str(row["event_id"]),
                        sequence=int(row["sequence"]),
                        event_type=str(row["event_type"]),
                        severity=str(row["severity"]),
                        payload=json.loads(str(row["payload"])),
                        attempt_count=int(row["attempt_count"]) + 1,
                    )
                    for row in selected
                ),
            )

        return self._db.run_transaction(operation)

    def mark_sent(self, event_ids: list[str], *, now: datetime | None = None) -> None:
        self._update_status(event_ids, "sent", now_z(now), None, None)

    def mark_dead_letter(
        self, event_ids: list[str], reason: str, *, now: datetime | None = None
    ) -> None:
        self._update_status(event_ids, "dead_letter", now_z(now), None, _safe_error(reason))

    def retry_at(
        self,
        event_ids: list[str],
        when: datetime,
        reason: str,
        *,
        now: datetime | None = None,
    ) -> None:
        self._update_status(event_ids, "pending", now_z(now), now_z(when), _safe_error(reason))

    def _update_status(
        self,
        event_ids: list[str],
        status: str,
        updated_at: str,
        next_attempt_at: str | None,
        error: str | None,
    ) -> None:
        if not event_ids:
            return
        placeholders = ",".join("?" for _ in event_ids)
        retry_at = next_attempt_at or updated_at
        self._db.execute(
            f"""
            UPDATE siem_outbox
            SET status = ?, updated_at = ?, next_attempt_at = ?, last_error = ?,
                lease_expires_at = NULL, batch_id = NULL
            WHERE event_id IN ({placeholders})
            """,
            (status, updated_at, retry_at, error, *event_ids),
        )

    def get(self, event_id: str) -> dict[str, Any] | None:
        row = self._db.query_one("SELECT * FROM siem_outbox WHERE event_id = ?", (event_id,))
        if row is not None:
            row["payload"] = json.loads(str(row["payload"]))
        return row

    def latest_for_alert(self, alert_id: str) -> dict[str, Any] | None:
        """Return the newest telemetry item tied to one local Shield alert."""

        rows = self._db.query(
            "SELECT * FROM siem_outbox WHERE event_type LIKE 'shield.alert.%' "
            "ORDER BY sequence DESC"
        )
        for row in rows:
            try:
                payload = json.loads(str(row["payload"]))
            except (TypeError, ValueError):
                continue
            metadata = payload.get("metadata") if isinstance(payload, dict) else None
            if isinstance(metadata, dict) and metadata.get("shield_alert_id") == alert_id:
                row["payload"] = payload
                return row
        return None

    def list_status(self, status: str) -> list[dict[str, Any]]:
        return self._db.query(
            "SELECT * FROM siem_outbox WHERE status = ? ORDER BY sequence", (status,)
        )

    def count(self, status: str | None = None) -> int:
        if status is None:
            return int(self._db.scalar("SELECT COUNT(*) FROM siem_outbox") or 0)
        return int(
            self._db.scalar("SELECT COUNT(*) FROM siem_outbox WHERE status = ?", (status,)) or 0
        )

    def integration_state(self) -> dict[str, Any]:
        """Return non-secret connector state for health/audit surfaces."""

        return (
            self._db.query_one(
                "SELECT instance_id, next_sequence, dropped_count, last_enqueue_error "
                "FROM siem_integration_state WHERE state_id = 1"
            )
            or {}
        )


__all__ = [
    "MAX_BATCH_BYTES",
    "MAX_EVENT_BYTES",
    "MAX_OUTBOX_BYTES",
    "MAX_OUTBOX_EVENTS",
    "LeasedBatch",
    "OutboxCapacityError",
    "OutboxItem",
    "OutboxRepository",
    "now_z",
]
