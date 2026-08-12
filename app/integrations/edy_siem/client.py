"""Small stdlib HTTPS client for the EDY SIEM v1 receiver."""

from __future__ import annotations

import http.client
import json
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from .config import SiemConfig
from .outbox import MAX_BATCH_BYTES


class TransportError(Exception):
    """Retryable DNS, connection or timeout failure."""


class InvalidResponseError(Exception):
    """The SIEM returned an unsafe or malformed acknowledgement."""


@dataclass(frozen=True, slots=True)
class SiemResponse:
    status: int
    payload: dict[str, Any] | None
    retry_after: int | None


class SiemClient:
    """Send one canonical batch without redirects or TLS downgrades."""

    def __init__(self, config: SiemConfig) -> None:
        self.config = config

    def send(self, envelope: dict[str, object]) -> SiemResponse:
        body = json.dumps(
            envelope,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        if len(body) > MAX_BATCH_BYTES:
            raise ValueError("batch exceeds 1 MiB")
        parsed = urlsplit(self.config.endpoint_url)
        hostname = parsed.hostname
        if hostname is None:
            raise ValueError("EDY SIEM endpoint has no hostname")
        connection: http.client.HTTPConnection
        if parsed.scheme == "https":
            connection = http.client.HTTPSConnection(
                hostname,
                parsed.port,
                timeout=self.config.connect_timeout,
                context=ssl.create_default_context(),
            )
        else:
            connection = http.client.HTTPConnection(
                hostname,
                parsed.port,
                timeout=self.config.connect_timeout,
            )
        started = time.monotonic()
        try:
            connection.connect()
            remaining = max(0.1, self.config.total_timeout - (time.monotonic() - started))
            if connection.sock is not None:
                connection.sock.settimeout(remaining)
            path = parsed.path or "/"
            connection.request(
                "POST",
                path,
                body=body,
                headers={
                    "Authorization": f"Bearer {self.config.token}",
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                    "Idempotency-Key": str(envelope["batch_id"]),
                    "User-Agent": "EDY-Shield/2",
                },
            )
            response = connection.getresponse()
            raw = response.read(MAX_BATCH_BYTES + 1)
            if len(raw) > MAX_BATCH_BYTES:
                raise InvalidResponseError("SIEM response exceeds 1 MiB")
            retry_after = self._retry_after(response.getheader("Retry-After"))
            payload = self._decode_payload(raw) if raw else None
            return SiemResponse(response.status, payload, retry_after)
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise TransportError("EDY SIEM is unreachable") from exc
        finally:
            connection.close()

    @staticmethod
    def _retry_after(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return min(900, max(0, int(value)))
        except ValueError:
            return None

    @staticmethod
    def _decode_payload(raw: bytes) -> dict[str, Any]:
        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidResponseError("SIEM response is not valid UTF-8 JSON") from exc
        if not isinstance(decoded, dict):
            raise InvalidResponseError("SIEM response must be a JSON object")
        return decoded


__all__ = [
    "InvalidResponseError",
    "SiemClient",
    "SiemResponse",
    "TransportError",
]
