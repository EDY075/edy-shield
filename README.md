<div align="center">

# EDY Shield

Modern defensive security toolkit for file integrity, hash analysis and incident investigation.

![EDY Shield Banner](brand/banner_github.svg)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Release](https://img.shields.io/badge/Release-v2.2.0--rc-blue)](https://github.com/EDY075/edy-shield/releases)
[![Tests](https://img.shields.io/badge/Tests-635%20passed-brightgreen)]()
[![Coverage](https://img.shields.io/badge/Coverage-91.92%25-success)]()
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)]()

</div>

---

## Overview

EDY Shield is a modular defensive security platform written in **Python 3.12** with a **100% standard-library core** (zero runtime dependencies). It combines file integrity monitoring, hash analysis, log analysis and a configurable alert engine behind a professional SOC-style web dashboard.

It solves a practical problem: small security teams and blue-team operators need a lightweight, self-contained toolkit — no cloud, no agents, no license fees — to monitor critical files, triage alerts and investigate indicators of compromise on their own infrastructure.

**Capabilities**

- File Integrity Monitoring with baseline and scan
- Hash verification (MD5, SHA-1, SHA-256, SHA-512)
- Log analysis and entropy/string analysis plugins
- Configurable alert engine with deduplication
- SOC dashboard with dark/light themes
- REST API for automation and integration

---

## Features

**Dashboard** — Real-time KPIs, health monitoring, severity charts and activity timeline.

**Alert Center** — Triage table with filters, sorting, pagination and batch actions (ACK, resolve, suppress, reopen).

**Investigation Workspace** — Slide-out panel with Summary, Timeline, Evidence, Comments and History tabs.

**Rules** — View active alert engine rules with severity and thresholds.

**Assets** — Inventory view of monitored assets.

**IOC Manager** — Interface for indicator-of-compromise workflows.

**Logs** — System log viewer with level filtering.

**System Health** — API, database, analyzer and uptime KPIs with plugin list.

**Export** — Alert investigation export to Markdown and JSON.

**REST API** — JSON API for alerts, health, history, analysis and FIM baselines.

**Dark / Light** — Full theme support persisted in browser.

**Responsive** — Optimized layout for desktop, tablet and mobile.

---

## Screenshots

| | |
|---|---|
| ![Dashboard](docs/screenshots/dashboard.png) | ![Alert Center](docs/screenshots/alert-center.png) |
| ![System Health](docs/screenshots/system-health.png) | ![Rules](docs/screenshots/rules.png) |
| ![Settings](docs/screenshots/settings.png) | ![Assets](docs/screenshots/assets.png) |
| ![Logs](docs/screenshots/logs.png) | ![IOC Manager](docs/screenshots/ioc-manager.png) |

---

## Architecture

The application is layered with a strict one-way dependency rule: **UI → Services → Core**. The core never imports from UI or services.

```mermaid
flowchart LR
    UI[Dashboard / CLI] --> SVC[Services]
    SVC --> PLG[Plugin Manager]
    PLG --> CORE[Core]
    SVC --> STORE[(SQLite Storage)]
    PLG --> AN["Analyzers<br/>string · entropy · log"]
    PLG --> FIM["FIM<br/>baseline · scan"]
    CORE --> ALG[Algorithms]
    CORE --> CRYPTO[Cryptography]
    UI --> API[REST API]
    API --> SVC
```

**Frontend** — Vanilla HTML/CSS/JS single-page application (no frameworks). Served directly by the built-in HTTP server.

**Backend** — `http.server`-based REST API (Python standard library). Routes for alerts, health, history, analysis, FIM and plugins.

**Services** — Business orchestration: alert service, alert store, history, report engine, analysis.

**Storage** — SQLite via the standard library. Default database path overridable through `EDYSHIELD_DB_PATH`.

**Plugins** — Contract-based plugin system: `log_analyzer`, `hash_checker`, `file_integrity`, `string_analyzer`, `entropy_analyzer`.

**API** — JSON endpoints under `/api/*` (see `docs/API_STABILITY.md`).

---

## Project Structure

```
edy-shield/
├── app/
│   ├── cli/          # Command-line interface (edyshield)
│   ├── core/         # Algorithms, crypto, filesystem, validators, config
│   ├── plugins/      # Plugin contracts, registry and manager
│   ├── services/     # Alerts, analysis, history, reports, storage
│   └── ui/           # HTTP server + static dashboard
├── docs/             # Architecture, ADRs, threat model, screenshots
├── tests/            # Unit, integration and e2e tests
├── website/          # Marketing landing page
├── brand/            # Logos and visual assets
├── pyproject.toml    # Project metadata and tooling config
└── CHANGELOG.md
```

---

## Installation

### Requirements

- Python 3.12+

### Windows

```powershell
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

### Linux

```bash
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### macOS

```bash
git clone https://github.com/EDY075/edy-shield.git
cd edy-shield
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Running

Start the web dashboard:

```bash
python -m app.ui.server
```

Then open <http://127.0.0.1:8000/dashboard>.

The REST API is available on the same host: <http://127.0.0.1:8000/api/health>.

CLI usage:

```bash
edyshield hash --help
edyshield fim baseline --help
edyshield fim scan --help
```

---

## Configuration

Configuration is environment-driven (prefix `EDY_`):

| Variable | Description | Default |
|---|---|---|
| `EDYSHIELD_DB_PATH` | SQLite database file path | `~/.edyshield/edy_shield.db` |
| `EDYSHIELD_LOG_LEVEL` | Logging verbosity | `INFO` |

**SQLite** — All persistence (alerts, history, analysis, FIM baselines) lives in a single SQLite database.

**Plugins** — Enabled through the plugin registry; each analyzer implements the plugin contract (`app/plugins/contracts.py`).

**Directories** — Static assets, brand assets and documentation are organized under `app/ui/static/`, `brand/` and `docs/`.

---

## Testing

```bash
pip install -r requirements-dev.txt

pytest                       # run full suite
pytest tests/unit -q         # unit tests only
ruff check app/              # lint
ruff format --check app/     # formatting
mypy app/                    # type checking (strict)
coverage run -m pytest       # coverage
coverage report              # coverage report
```

Current gates: **635 tests passing**, **91.92% coverage**, **mypy strict clean**, **ruff clean**.

---

## Security

- **Alert Engine** — configurable rules with severity mapping and deduplication.
- **Rules** — rule conditions, operators and severity thresholds.
- **IOC handling** — indicators surfaced in the investigation workspace.
- **Logs** — structured log analysis and entropy detection.
- **Analysis** — string and entropy analyzers for suspicious content.
- **Export** — investigation reports exported as Markdown or JSON.

HTTP hardening includes Content-Security-Policy, X-Frame-Options, nosniff, Referrer-Policy and Permissions-Policy headers, plus a 1 MB request body limit. See `docs/THREAT_MODEL.md` for details.

---

## Roadmap

- v2.3 — Additional analyzer plugins, rule builder UI
- v2.4 — Native notifications and scheduled scans
- v2.5 — Multi-user roles and audit trail

---

## Contributing

Contributions are welcome. Please review the guidelines:

1. Open an issue describing the bug or feature before sending a pull request.
2. Follow the existing code style (ruff + mypy strict must pass).
3. Add or update tests; coverage must stay above the quality gate.
4. Update `CHANGELOG.md` for user-visible changes.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
