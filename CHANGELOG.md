# Changelog

All notable changes to the **WebPilot** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.5] - 2026-10-09

### Security & Hardening
- **Supervisor Token Authentication**: Generated 256-bit cryptographically secure random authentication token at startup, persisted strictly with owner-only access permissions (`chmod 0600` on POSIX, inheritance-stripped user ACL on Windows) in `~/.webpilot/supervisor.token`.
- **HTTP Endpoint Protection**: Every incoming HTTP request (`/execute`, `/restart`, `/stop`, `/status`, `/ping`) requires valid `X-Supervisor-Token` or `Authorization: Bearer` headers; unauthorized calls are rejected immediately with HTTP 401, securing logged-in browser sessions against local process hijacking.
- **Secrets Hygiene & History Protection**: Added native support for `--fill "field=@env:VAR"`, `--fill "field=@stdin"`, and `--fill "field=@file:PATH"`, eliminating plain-text passwords and credentials from shell history and process args. Also added support for streaming JSON payloads via stdin (`--data -`).

### Architecture & Portability
- **ProcessManager Abstraction**: Encapsulated all OS-specific process lifecycle logic behind `BaseProcessManager`, decoupling Windows WMI/CIM/taskkill and POSIX setsid/killpg/pgrep behind a unified interface with full testability and mock injection.
- **Cross-Platform Enterprise Portability**: Tested and verified native headless execution on Linux, macOS, and Windows.

### Testing & Verification
- **Enterprise Portal Mock Fixture & CI Integration Suite**: Added `tests/fixtures/enterprise_portal.html` and `test_enterprise_integration.py` simulating real-world SAP SuccessFactors and Workday portals (async loading spinners, modal policy dialogs, complex picklist comboboxes, and form submissions).
- **Expanded Test Suite**: Increased automated test coverage from 37 to 50 passing unit and integration tests.

---

## [2.0.4] - 2026-10-09

### Fixed
- **Critical: `common` package missing from wheel** — `common*` was absent from `[tool.setuptools.packages.find]`, causing `ModuleNotFoundError: No module named 'common'` on every fresh install.
- **Critical: JSON data files not bundled** — Added `[tool.setuptools.package-data]` so `config/settings.json` and `config/device_profile.json` are included in the wheel and accessible at runtime.
- **Classifier corrected** — Changed `Development Status :: 5 - Production/Stable` → `4 - Beta` to accurately reflect the project's current maturity.

---

## [2.0.3] - 2026-10-09


### Added
- **Project Metadata & Registry URLs**: Added official repository links (`Homepage`, `Documentation`, `Repository`, and `Bug Tracker`) to `pyproject.toml` for seamless GitHub and PyPI integration.
- **Architectural Documentation Catalog**: Added comprehensive file-by-file system map in `PROJECT_MAP.md`.

### Changed
- **Maintainer & Author Attribution**: Updated official package authorship to `Abdulkarim Salih, WebPilot Core Team`.
- **MCP Server Documentation**: Streamlined agent integration guides to universally support all AI coding assistants (Claude Desktop, Cursor, OpenCode, and AI agents).

### Verified
- Zero sensitive credentials, tokens, or temporary files across the entire codebase.
- Full test suite passing across all 37 unit, integration, and E2E test cases.

---

## [2.0.2] - 2026-10-09

### Added
- **Full Cross-Platform Portability**: Complete native support across Linux, macOS, and Windows.
- **POSIX Process Group Cascading Kill**: Implemented `os.killpg(os.getpgid(pid), signal.SIGKILL)` on Linux/macOS to guarantee 100% clean termination of child Chromium processes with zero zombie leaks.
- **POSIX Detached Daemon Spawning**: Seamless background execution using `start_new_session=True` without relying on Windows-specific `creationflags`.
- **Cross-Platform PID Resolution**: Dynamic PID tree extraction using `pgrep -P` on POSIX systems and CIM/PowerShell on Windows.

### Fixed
- Fixed `ValueError: creationflags is only supported on Windows` when executing on Linux or macOS containers.
- Fixed supervisor script path scoping in detached process execution.

---

## [2.0.1] - 2026-10-09

### Added
- **Zero-Touch Chromium Auto-Installation**: WebPilot now automatically checks for required Chromium binaries upon first execution and auto-installs them seamlessly without crashing.
- **CLI Browser Management Command**: Added `wp install` (`webpilot install [--all]`) subcommand for manual browser verification and bootstrapping.
- **User-Friendly Error Banners**: Replaced long internal Python stack tracebacks with clean, colored terminal diagnosis banners when network or installation issues occur.

---

## [2.0.0] - 2026-10-09

### Added
- **Initial Enterprise Release of WebPilot** (`webpilot-engine`).
- **3-Tier Zero-Elevation Architecture**:
  - **Layer 1 (Master Daemon)**: Lightweight HTTP host (~15MB RAM) breaking out of terminal Job Objects in Standard User mode.
  - **Layer 2 (Worker Process)**: Isolated JSON-RPC worker keeping Playwright browser sessions alive across CLI commands.
  - **Layer 3 (Chromium Engine)**: Process tree attachment with cascading termination and 300ms self-healing restart.
- **Built-in FastMCP Server** (`webpilot-mcp`): Exposes 10 standard browser automation tools for AI agents (inspect, fill form, click button, upload file, screenshot, list tabs, switch tab, save cookies, service status, restart).
- **Universal Form Inspection Engine**: Token-optimized DOM schema extraction for enterprise SPAs (SAP SuccessFactors, Workday, Greenhouse, Oracle Taleo).
- **Reactive Interaction Service**:
  - Automatic button click observation with route redirect detection.
  - Detection and seamless switching to newly spawned browser windows.
  - Detection of dynamic form accordion expansions.
- **Dynamic Loader Dissolution**: Automatic wait-and-dissolve handling for global page loaders (`#loading`, `.sapUiBusy`, `[aria-busy="true"]`).
- **4-Stage Modal & Pointer Escape Pipeline**: Natural selection -> Escape key -> Backdrop click -> Surgical DOM removal.
- **Interactive REPL Shell**: Sub-second automation shell (`wp shell`) with live DOM inspection and tab navigation.
- **Inactivity Watchdog**: Automatic 30-minute idle watchdog to release 100% of browser memory.
