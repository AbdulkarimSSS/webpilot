# Changelog

All notable changes to the **WebPilot** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.1] - 2026-10-12

### Architecture & Modularization
- **CLI Decomposition (`cli_commands/`)**: Modularized `cli.py` (down from 419 to 69 lines), isolating subcommand handlers into dedicated, single-responsibility modules (`inspect_cmd.py`, `apply_cmd.py`, `find_cmd.py`, `service_cmd.py`, `common.py`).
- **Worker Execution Handlers (`supervisor/worker_handlers.py`)**: Shrunk `worker_process.py` (from 538 to 250 lines) by extracting inspection, element probing, and multi-phase form filling into `worker_handlers.py`.
- **MCP Tool Decomposition (`mcp_tools.py`)**: Shrunk `mcp_server.py` (from 293 to 142 lines) by decoupling tool execution logic into `mcp_tools.py`.
- **Legacy Auth Elimination**: Completely removed `auth_navigation_service.py` and `adapters/dom/auth.py`, establishing `PageLifecycleService` as the unified page readiness standard.
- **Exhaustive AI Agent Skill Specification**: Upgraded `skills/webpilot-automation/SKILL.md` into a 100% comprehensive operational manual covering all commands, architecture layers, parameters, and error codes.
- **Verification & Integrity**: Full test suite passing 69/69 (100%) and live E2E inspection, probing, and submission verified.

## [2.1.0] - 2026-10-12

### Architecture & Modernization (Major Refactor)
- **DOM Script Modularization (`adapters/dom/`)**: Decomposed monolithic 1,010-line `dom_scripts.py` into focused, single-responsibility ES6 modules:
  - `lifecycle.py`: DOM loading sentinel and universal accordion expansion.
  - `navigation.py`: Portal apply button clicker and dropdown menu triggers.
  - `set_field.py`: Robust field population across text, select, picklist, radio, checkbox, and date inputs.
  - `picklist.py`: Enterprise auto-scrolling picklist resolver.
  - `verify.py`: Three-stage physical DOM verification logic.
  - `inspection.py`: Full-page DOM schema introspection and picklist option probing.
  - `probe.py`: Dynamic field-level attribute and state probing.
  - `reactive.py`: Dynamic reactive button clickers.
- **Unified Page Lifecycle Architecture (`PageLifecycleService`)**:
  - Replaced legacy auth-specific hacks with a generalized page readiness and accordion expansion service.
  - Eliminated `auth_navigation_service.py` entirely, treating authentication portals and login pages as standard web forms with zero special-casing.
- **Separation of Concerns in Services & Pipeline**:
  - Extracted `FormApplicationPipeline` (`services/form_application_pipeline.py`) from `OperationalWorker`, encapsulating the 5-phase fill lifecycle (preparation, dynamic expansion, execution, pre-submit reverification, and reactive verification).
  - Extracted `DOMDataMatcher` (`services/dom_verifier.py`) for deterministic DOM value comparison.
  - Extracted `TargetDescriptorParser` (`services/target_descriptor.py`) for parsing field selectors and values.
  - Extracted `SchemaMerger` (`services/schema_merger.py`) for schema transformations and deduplication.
  - Shrunk `field_interaction_service.py` from 608 to 248 lines and `worker_process.py` from 667 to 466 lines.
- **Tab & Window Isolation Architecture (`TabManager`)**:
  - Extracted `TabManager` (`adapters/tab_manager.py`) to manage Playwright browser contexts, tab tracking, multi-tab switching, popup handling, and route interception cleanly decoupled from `BrowserAdapter`.
  - Extracted `PlaywrightLocatorFallback` (`adapters/locator_fallbacks.py`) for locator resolution fallbacks.
- **Supervisor Decoupling & Watchdog Refactoring**:
  - Extracted `SupervisorHTTPHandler` (`supervisor/handler.py`) to handle JSON-RPC endpoint routing (`/execute`, `/restart`, `/stop`, `/status`, `/ping`).
  - Extracted `InactivityWatchdog` (`supervisor/watchdog.py`) for idle timeout management and memory auto-reclaim.
  - Extracted `CLIParserBuilder` (`cli_parser.py`) and `TelemetryReporter` (`common/telemetry.py`), reducing `cli.py` by over 170 lines.
- **Deep Modularization & Single-Responsibility Decomposition**:
  - **Modular CLI Layer (`cli_commands/`)**: Shrunk `cli.py` from 419 down to 69 lines by extracting dedicated command handlers into `cli_commands/` (`inspect_cmd`, `apply_cmd`, `find_cmd`, `service_cmd`, `common`).
  - **Worker Execution Handlers (`supervisor/worker_handlers.py`)**: Shrunk `worker_process.py` from 538 down to 250 lines by extracting IPC command execution into `worker_handlers.py` (`handle_worker_inspect`, `handle_worker_probe`, `handle_worker_apply`), isolating the IPC loop from DOM pipeline execution.
  - **MCP Declarative Layer (`mcp_tools.py`)**: Shrunk `mcp_server.py` from 293 down to 142 lines by decoupling MCP tool handlers into `mcp_tools.py`.
  - Preserved 100% test compatibility (69/69 test suite passing with zero regressions).

### Added
- **Multi-Tab Management & Switching (`wp tab`)**:
  - Added CLI and JSON-RPC multi-tab awareness to list, inspect, and switch between browser tabs cleanly.
- **Enhanced Field Inspection Probing (`--probe`)**:
  - Probes individual or grouped fields for live DOM state, disabled status, picklist options, and reactive triggers without full page overhead.
- **Targeted Field Search (`wp find`)**:
  - Direct selector search (`wp find @fld-1 --html`) for inspecting targeted elements and extracting raw HTML snippets.

---

## [2.0.14] - 2026-10-12

### Added
- **AI Agent Skill Specification Integration**: Bundled the native `SKILL.md` directly into the distributed Python wheel package under `skills/webpilot-automation/`.
- **Global `wp skill` Command**: Added dedicated CLI subcommand `wp skill` to output the full machine-actionable AI agent skill specification to standard output, enabling instant agent onboarding and zero-configuration tool discovery.

---

## [2.0.13] - 2026-10-12

### Fixed
- **Navigation Race Condition & Context Destruction**: Wrapped `Page.evaluate` calls across `ReactiveInteractionService`, `FormValidator`, and `InspectionService` with resilient try/catch and automatic `domcontentloaded` lifecycle settling. When a click triggers an immediate HTTP 302 or SPA client-side route redirection, the engine gracefully transitions without throwing unhandled `Execution context was destroyed` exceptions.
- **Omission of Automatic Section Expansion in Supervisor**: Restored missing `auth_svc.wait_for_form_ready()` and `auth_svc.expand_all_sections()` calls in `OperationalWorker._handle_inspect()`, achieving full architectural parity with `engine.py` and `flow_orchestrator.py`. Forms with initially collapsed accordion sections (SAP SuccessFactors, Workday, Bootstrap, HTML5 `<details>`) are now deeply unwrapped automatically during inspection.
- **SAP SuccessFactors & Enterprise Picklist Resolution**: Enhanced `PICKLIST_AUTO_SCROLL_SCRIPT` with intelligent list container discovery (`${inpId}:_listSelect`, `[role="listbox"]`, `.rcmpaginatedselectlist`, `.globalMenu`), and added synthetic W3C mouse lifecycle event dispatching (`mousedown`, `click`, `mouseup`) ensuring 100% reliable option selection on complex enterprise dropdowns.
- **Universal Accordion & Master Expand Selector Coverage**: Extended `EXPAND_ALL_SECTIONS_SCRIPT` to detect and trigger global master expand buttons (`Expand all sections`, `[aria-label*="Expand all" i]`) and modern CSS framework accordions (Bootstrap, Tailwind, Shadcn, HTML5 `<details>`).
- **Post-Interaction Verification on Navigation**: In `_handle_apply()`, automatically detected route changes to skip stale post-interaction DOM checks on unmounted forms.

### Platform & CLI
- **Native PowerShell Wrapper**: Added `wp.ps1` and `webpilot.ps1` wrappers in System PATH to prevent Windows `cmd.exe` quote stripping on URLs containing ampersands (`&`), ensuring direct and lossless argument forwarding.

---

## [2.0.7] - 2026-10-09

### Fixed
- **Worker Process Session Isolation on Restart**: Unified worker spawning across initial launch and `restart_worker` via `_spawn_worker()`, guaranteeing `start_new_session=True` on POSIX systems so restarted worker processes are properly isolated in their own process group.
- **Post-Fill DOM Verification Connected**: Connected `verify_field_value` in `OperationalWorker._handle_apply`, verifying set field values directly in the DOM with Playwright click fallback retry, populating `confirmed_fields`, `unconfirmed_fields`, and `failed_fields` in `SupervisorActionResponse`.

### Security & Hardening
- **Supervisor Token CLI & API Integration**: Added `--token` flag across CLI global options and all subcommands (`inspect`, `apply`, `shell`, `service`), propagating explicitly passed tokens to `SupervisorClient` and `run_master_daemon` for end-to-end token authenticated control.

---

## [2.0.6] - 2026-10-09

### Fixed & Enhanced
- **MCP Server Graceful Optional Dependency**: `mcp_server.py` now provides a clean, user-friendly terminal notification when invoked without the optional `mcp` extra, prompting `pip install "webpilot-engine[mcp]"` without throwing an unhandled `ModuleNotFoundError` traceback.
- **Documentation & Architecture Accuracy**: Removed obsolete claims of destructive DOM manipulation ("DOM surgical removal" and backdrop deletion) across all architecture docs and READMEs, accurately reflecting WebPilot's non-destructive, strictly compliant browser interaction philosophy.
- **End-to-End PyPI Verification**: Thoroughly verified installation and operations in an isolated, clean virtual environment simulating regular end-user workflows across all CLI subcommands (`wp inspect`, `wp apply`, `wp service`, `wp --help`).

---

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
- **4-Strategy Reactive Interaction Pipeline**: Non-destructive interaction cascade (Native ID -> ARIA Role/Text -> JS In-DOM Click -> W3C Escape Key Protocol) preserving DOM integrity.
- **Interactive REPL Shell**: Sub-second automation shell (`wp shell`) with live DOM inspection and tab navigation.
- **Inactivity Watchdog**: Automatic 30-minute idle watchdog to release 100% of browser memory.
