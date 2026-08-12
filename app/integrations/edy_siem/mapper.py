"""Map real EDY Shield facts to Event Contract v1 payloads."""

from __future__ import annotations

import platform
import socket
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app import __version__
from app.core.alerts.models import AlertRecord
from app.core.fim.models import Baseline, FimDiff, Snapshot


def utc_z(value: str | datetime) -> str:
    """Render a timezone-aware timestamp as RFC3339 UTC with ``Z``."""

    parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class EventMapper:
    """Source-specific mapper; it never performs persistence or network I/O."""

    def __init__(self, instance_id: str, hostname: str | None = None) -> None:
        self.instance_id = instance_id
        self.hostname = (hostname or socket.gethostname() or "unknown-host")[:255]
        self.asset = {
            "asset_id": f"shield:{instance_id}:{self.hostname}"[:255],
            "hostname": self.hostname,
            "os": f"{platform.system()} {platform.release()}"[:255],
        }

    def _event(
        self,
        *,
        sequence: int,
        component: str,
        event_type: str,
        severity: str,
        timestamp: str | datetime,
        evidence: dict[str, Any],
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid.uuid4()),
            "schema_version": "1.0",
            "timestamp": utc_z(timestamp),
            "sequence": sequence,
            "source": {
                "product": "edy-shield",
                "product_version": __version__,
                "instance_id": self.instance_id,
                "component": component,
            },
            "event_type": event_type,
            "severity": severity.lower(),
            "asset": dict(self.asset),
            "evidence": evidence,
            "metadata": metadata,
        }

    def baseline_created(self, baseline: Baseline, sequence: int) -> dict[str, Any]:
        return self._event(
            sequence=sequence,
            component="fim",
            event_type="shield.fim.baseline.created",
            severity="info",
            timestamp=baseline.created_at,
            evidence={
                "hash_algorithm": baseline.algorithm.lower(),
                "baseline_id": baseline.baseline_id,
                "baseline_status": "created",
                "details": {"file_count": len(baseline.entries)},
            },
            metadata={"tags": ["fim", "baseline"]},
        )

    def file_change(
        self,
        *,
        sequence: int,
        change: str,
        baseline: Baseline,
        snapshot: Snapshot,
        path: str,
        scan_id: str,
    ) -> dict[str, Any]:
        before = {entry.path: entry for entry in baseline.entries}.get(path)
        after = {entry.path: entry for entry in snapshot.entries}.get(path)
        event_types = {
            "added": "shield.fim.file.added",
            "modified": "shield.fim.file.modified",
            "removed": "shield.fim.file.removed",
        }
        severities = {"added": "low", "modified": "medium", "removed": "high"}
        evidence: dict[str, Any] = {
            "file_path": path,
            "hash_algorithm": baseline.algorithm.lower(),
            "baseline_id": baseline.baseline_id,
            "baseline_status": change,
            "scan_id": scan_id,
            "details": {},
        }
        if before is not None:
            evidence["previous_hash"] = before.hexdigest
        if after is not None:
            evidence["current_hash"] = after.hexdigest
            evidence["file_size_bytes"] = after.size_bytes
            evidence["mtime"] = utc_z(after.mtime_iso)
        elif before is not None:
            evidence["file_size_bytes"] = before.size_bytes
            evidence["mtime"] = utc_z(before.mtime_iso)
        return self._event(
            sequence=sequence,
            component="fim",
            event_type=event_types[change],
            severity=severities[change],
            timestamp=snapshot.created_at,
            evidence=evidence,
            metadata={"correlation_id": scan_id, "tags": ["fim", f"file-{change}"]},
        )

    def scan_completed(
        self,
        diff: FimDiff,
        scan_id: str,
        duration_ms: int,
        sequence: int,
    ) -> dict[str, Any]:
        return self._event(
            sequence=sequence,
            component="fim",
            event_type="shield.fim.scan.completed",
            severity="info" if diff.changed == 0 else "medium",
            timestamp=diff.scanned_at,
            evidence={
                "baseline_id": diff.baseline_id,
                "scan_id": scan_id,
                "details": {
                    "added": len(diff.added),
                    "modified": len(diff.modified),
                    "removed": len(diff.removed),
                    "unchanged": len(diff.unchanged),
                    "ignored": len(diff.ignored),
                    "duration_ms": max(0, int(duration_ms)),
                },
            },
            metadata={"correlation_id": scan_id, "tags": ["fim", "scan"]},
        )

    def hash_mismatch(
        self,
        *,
        path: str,
        expected: str,
        current: str,
        algorithm: str,
        timestamp: str | datetime,
        sequence: int,
    ) -> dict[str, Any]:
        logical_path = Path(path).name
        return self._event(
            sequence=sequence,
            component="hash_checker",
            event_type="shield.hash.mismatch",
            severity="high",
            timestamp=timestamp,
            evidence={
                "file_path": logical_path,
                "hash_algorithm": algorithm.lower(),
                "previous_hash": expected.lower(),
                "current_hash": current.lower(),
                "baseline_status": "not_applicable",
                "details": {"verification_source": "hash_checker"},
            },
            metadata={"tags": ["hash", "integrity", "mismatch"]},
        )

    def security_alert(
        self,
        record: AlertRecord,
        sequence: int,
        *,
        action: str = "created",
        previous_status: str | None = None,
    ) -> dict[str, Any]:
        details: dict[str, Any] = {
            "title": record.title[:1024],
            "description": record.description[:1024],
        }
        event_type = "shield.alert.created"
        if action == "updated":
            event_type = "shield.alert.updated"
            details.update(
                {
                    "previous_status": previous_status or "unknown",
                    "current_status": record.status.value,
                }
            )
        return self._event(
            sequence=sequence,
            component="alert_engine",
            event_type=event_type,
            severity=record.severity.value,
            timestamp=record.last_seen_at,
            evidence={"details": details},
            metadata={
                "shield_alert_id": record.alert_id,
                "rule_id": record.rule_id,
                "dedup_fingerprint": record.fingerprint,
                "tags": ["alert", record.source[:64]],
            },
        )


__all__ = ["EventMapper", "utc_z"]
