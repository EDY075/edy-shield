"""Regression coverage for the shared visual baseline introduced in Sprint D."""

from __future__ import annotations

from pathlib import Path


def test_dashboard_preserves_endpoint_identity_and_accessible_motion_defaults() -> None:
    """Keep the Shield's endpoint-integrity visual language intentional and accessible."""
    root = Path(__file__).resolve().parents[2]
    styles = (root / "app" / "ui" / "static" / "dashboard" / "css" / "dashboard.css").read_text(
        encoding="utf-8"
    )

    for marker in (
        "--accent-primary: #1fb58a",
        "--accent-primary-hover: #42d1aa",
        "--accent-gradient: linear-gradient(135deg, #1fb58a, #0b7663)",
        "--font-sans: Inter, ui-sans-serif, system-ui",
        '--font-mono: "JetBrains Mono"',
        ":focus-visible",
        "@media (prefers-reduced-motion: reduce)",
    ):
        assert marker in styles
