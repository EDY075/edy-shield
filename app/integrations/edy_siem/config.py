"""Environment-driven configuration for the EDY SIEM connector."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import quote, urlsplit

INGEST_PATH = "/api/v1/ingestion/sources/edy-shield/events"


def integration_enabled() -> bool:
    """Return whether telemetry enqueue/delivery is explicitly enabled."""

    raw = os.getenv("EDY_SIEM_ENABLED", "false").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError("EDY_SIEM_ENABLED must be a boolean")


def _loopback(hostname: str | None) -> bool:
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ip_address(hostname).is_loopback
    except ValueError:
        return False


def _validated_base_url(value: str, variable: str) -> str:
    base_url = value.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"{variable} must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError(f"{variable} cannot contain credentials, query or fragment")
    if parsed.scheme == "http" and not _loopback(parsed.hostname):
        raise ValueError(f"HTTP is permitted only for a loopback {variable}")
    return base_url


def investigation_url(event_id: str) -> str | None:
    """Return a safe operator deep link without exposing connector secrets."""

    try:
        if not integration_enabled():
            return None
    except ValueError:
        return None
    raw = os.getenv("EDY_SIEM_UI_URL", "").strip() or os.getenv("EDY_SIEM_URL", "").strip()
    if not raw:
        return None
    try:
        base_url = _validated_base_url(raw, "EDY_SIEM_UI_URL")
    except ValueError:
        return None
    return f"{base_url}/investigate/shield/{quote(event_id, safe='')}"


@dataclass(frozen=True, slots=True)
class SiemConfig:
    """Validated transport configuration. Secrets are never represented in logs."""

    base_url: str
    token: str = field(repr=False)
    connect_timeout: float = 2.0
    total_timeout: float = 5.0
    poll_interval: float = 5.0
    lease_seconds: int = 30
    batch_size: int = 100

    @classmethod
    def from_env(cls) -> SiemConfig:
        """Load and validate an enabled connector from environment variables."""

        if not integration_enabled():
            raise ValueError("EDY SIEM integration is disabled")
        base_url = os.getenv("EDY_SIEM_URL", "").strip()
        token = os.getenv("EDY_SIEM_TOKEN", "")
        if not base_url:
            raise ValueError("EDY_SIEM_URL is required when integration is enabled")
        if len(token.encode("utf-8")) < 32:
            raise ValueError("EDY_SIEM_TOKEN must contain at least 32 bytes")
        if any(ord(char) < 32 or ord(char) == 127 for char in token):
            raise ValueError("EDY_SIEM_TOKEN cannot contain control characters")

        base_url = _validated_base_url(base_url, "EDY_SIEM_URL")
        return cls(base_url=base_url, token=token)

    @property
    def endpoint_url(self) -> str:
        """Return the canonical v1 receiver URL."""

        return f"{self.base_url}{INGEST_PATH}"


__all__ = ["INGEST_PATH", "SiemConfig", "integration_enabled", "investigation_url"]
