# Changelog

All notable changes to the **WebPilot** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.5.1] - 2026-10-15

### Core DOM Fixes, Native Tab Management & Complete References Packaging

#### 1. DOM Coordinate Calculation in Honeypot Pruning (Bug 1)
- **Document vs Viewport Offsets (`adapters/dom/universal_core.py`)**: Incorporated `window.pageXOffset` / `window.pageYOffset` into `isHoneypotOrHidden(el)` to compute absolute document coordinates (`docX`, `docY`).
- **Elimination of False Section Pruning**: Fixed critical regression where scrolling down and expanding accordion panes (`PageLifecycleService.expand_all_sections()`) gave upper sections negative viewport coordinates (`rect.bottom < 0`), falsely marking them as honeypots and pruning them from inspection schemas.

#### 2. Colon-Escaped IDs in Cascading Dependency Detection (Bug 2)
- **Defensive ID Escaping (`universal_core.py`, `inspection.py`)**: Sanitized compound IDs with colons (e.g. SAP SuccessFactors `id="57:_input"`, `id="250:_input"`) via `CSS.escape()` and defensive `try/catch` guards across all label and dependency lookups, preventing `DOMException: '<id>' is not a valid selector` from aborting field enumeration.

#### 3. Navigation Context Destruction Recovery (Bug 3)
- **Page Transition Click Resilience (`reactive_interaction_service.py`)**: Treated Playwright `Execution context was destroyed` exceptions during button clicks (`loc.first.click()`) as successful interactions (`clicked = True`), correctly acknowledging form submissions and navigation buttons without false failures.

#### 4. Regex & Prefix Stripping in Readback Verification (Bug 4)
- **Prefix Normalization (`services/dom_verifier.py`)**: Stripped option targeting prefixes (`re:`, `regex:`, `text:`, `val:`) before comparing expected values against actual DOM state in `DOMDataMatcher.match()`.
- **Full Regex Pattern Evaluation**: Added native regex evaluation (`bool(re.search(regex_pattern, actual_value, re.IGNORECASE))`) across select dropdowns, custom picklists, text, textarea, and plain string readbacks.

#### 5. Tab Index Honoring in Inspection (Bug 5)
- **Tab Targeting (`supervisor/worker_handlers.py`)**: Added `req.tab_index` check at the start of `handle_worker_inspect`, ensuring `wp inspect --tab <index>` switches to and inspects the requested tab rather than always inspecting the default tab.

#### 6. Infinite Recursion Safeguards in JavaScript Eval (Bug 6)
- **Circular Reference Protection (`supervisor/worker_process.py`)**: Added safe evaluation wrapper and recursive Python payload sanitizer (`_sanitize_eval_result`), preventing circular objects (e.g., `Window`, DOM nodes) from triggering `Worker loop fatal error: maximum recursion depth exceeded`.

#### 7. Native First-Class Tab Management (`wp tab`)
- **CLI Subcommand (`cli_commands/tab_cmd.py`, `cli_parser.py`)**: Added `wp tab` CLI interface with `list`, `new [URL]`, `switch <INDEX>`, and `close [INDEX]`.
- **Supervisor IPC Contracts (`supervisor/contracts.py`, `supervisor/worker_process.py`)**: Implemented IPC actions `new_tab`, `close_tab`, `list_tabs`, and `switch_tab`.
- **Adapter Implementations (`adapters/tab_manager.py`, `adapters/browser_adapter.py`)**: Implemented `create_new_tab()` and `close_tab()` ensuring at least one tab or `about:blank` remains open to prevent browser crashes.
- **Programmatic Python SDK (`webpilot/client.py`)**: Added `wp.new_tab()`, `wp.close_tab()`, `wp.switch_tab()`, and `wp.list_tabs()`.

#### 8. Documentation Suite & Wheel Packaging (`pyproject.toml`)
- **Complete References Suite**: Added and verified all 5 markdown reference files under `skills/webpilot-automation/references/`.
- **Package Data Distribution**: Updated `pyproject.toml` `package-data` to bundle all skill and reference markdown files into the published wheel distribution.
- **Self-Contained Skill Documentation**: Updated `skills/webpilot-automation/SKILL.md` with documentation for `tab`, `reload`, `eval`, `css`, `--strip-header`, `--data`, `--submit`, and `--cookies`.

## [2.5.0] - 2026-10-13

### Cascading Dependencies, Ranked Overlap Scoring & Advanced Option Pagination

#### 1. Dynamic Row Addition & Sequential Local ID Preservation
- **Local ID Preservation (`inspection.py`)**: Implemented `getOrCreateLocalId` to strictly preserve existing `data-wp-id` tags across DOM re-renders, preventing ID mutation when users or scripts click `+ Add` / `Add new row`.
- **Cumulative High-Water Mark Allocation**: Added pre-scanning of active DOM nodes for highest utilized counters (`maxFld`, `maxDrop`, `maxOpt`, `maxBtn`, `maxUp`), assigning subsequent sequential IDs to newly generated rows (`@fld-16`, `@fld-17`) without shifting earlier indexes.
- **Delta Capture Telemetry**: Added `result.new_elements_captured` array to inspection payloads, alerting upstream orchestrators to newly materialized DOM fields.

#### 2. Automatic Cascading Dependent Parent Field Detection
- **Multi-Heuristic Dependency Engine (`universal_core.py`)**: Implemented `detectDependentParentField(el)` resolving locked dependent children (e.g. `University` or `State` awaiting `Country` selection):
  - **Explicit Attribute Resolution**: Inspects `data-parent`, `data-depends-on`, `data-cascade-from`, and inverted `aria-controls`.
  - **DOM Row & Fieldset Proximity**: Scans preceding sibling elements within shared container blocks (`.rcmFormField`, `tr`, `fieldset`).
  - **Semantic Pairing Heuristics**: Recognizes standard hierarchical relationships (`Country` ➔ `University`/`City`/`State`, `Category` ➔ `Subcategory`).
- **Terminal & Agent Dependency Alerts (`find_cmd.py`, `probe.py`)**: Exposes structured `dependency` metadata and outputs immediate visual warnings (`⚠️ DEPENDENCY ALERT: Field is locked/empty awaiting parent selection`).

#### 3. 3-Tier Ranked Overlap Scoring with 80% Safety Threshold
- **Elimination of Speculative Partial Matches (`picklist.py`, `set_field.py`)**: Replaced naive linear substring matching with a hierarchical scoring engine:
  - **Tier 1 (Exact Match)**: 100% case-insensitive match on text, value, or option ID.
  - **Tier 2 (Continuous Phrase Match)**: Unbroken phrase matching prioritized by minimum length delta.
  - **Tier 3 (Strict Token Coverage & Jaccard Overlap)**: Splits target into token bags, computing token coverage ratio. Enforces a strict **80% Safety Threshold** (e.g. immediately rejecting `Aeronautical and Astronautical Engineering` at 50% coverage when requesting `Electrical Engineering`).

#### 4. Advanced Picklist Pagination, Slicing & Token Management (`wp find`)
- **Granular Slice Controls**: Added `--show <N>` / `--limit <N>` to adjust slice limits beyond the default 30 items.
- **Offset Navigation**: Added `--from <N>` / `--offset <N>` (0-based) to browse subsequent option slices.
- **Complete Option Dumps**: Added `--all` / `--full` to output all available picklist options without truncation.
- **Page-Based Pagination**: Added `--page <N>` (1-based) and `--page-size <N>` (default: 20) for page-by-page browsing.
- **Dynamic Interactive Header**: Displays total options count, active page/slice info, and a responsive footer hint indicating remaining items and suggested flags.

#### 5. Full In-Browser Regex Query Filtering (`-q / --query`)
- **Advanced Pattern Matching**: Upgraded browser-side option probing to support full ECMAScript Regular Expressions:
  - Anchors: `^B`, `Services$`
  - Alternation: `Banking|Healthcare`
  - Inline Flags: `/(oil|gas|chemical)/i`
- **Safe Substring Fallback**: Automatically falls back to standard substring matching if regex compilation fails or for plain strings.

#### 6. Certified Test Suite Expansion
- Added comprehensive unit and integration tests in `tests/test_find_and_unicode.py`, elevating the certified test suite to **91 passed tests (100%)** in 49.95 seconds.

## [2.4.0] - 2026-10-13

### Enterprise DatePickers, Shadow DOM Core & Full Agent Toolkit Overhaul

#### 1. Universal DOM Core & Deep Shadow DOM Penetration (`universal_core.py`)
- **Recursive Shadow Root Traversal**: Implemented `deepQuerySelector(root, selector)` in `adapters/dom/universal_core.py` to recursively pierce through nested and compound Shadow DOM boundaries.
- **Colon-Escaped Enterprise IDs**: Added automatic normalization for IDs with colons and special characters (e.g. SAP-UI5 `div#250:_datepicker`, `[id="250:_datepicker"]`), eliminating `SyntaxError` and locator resolution failures.
- **Unified Engine Integration**: Connected `universal_core.py` across DOM inspection (`inspection.py`), probing (`probe.py`), setting (`set_field.py`), and verification (`verify.py`).

#### 2. Explicit Selectors & XPath Interaction Support
- **Prefix-Based Selector Parsing**: Enhanced `services/target_descriptor.py` and `adapters/locator_fallbacks.py` to support explicit selector prefixes:
  - `--fill "selector:div#250:_datepicker=01/06/2024"`
  - `--fill "css:input[name='date']=2024-06-01"`
  - `--press "xpath://button[contains(., 'Submit')]"`
- **Intelligent Fallback Cascade**: Automatic differentiation between plain labels, local identifiers (`@fld-N`), CSS selectors, and XPath expressions.

#### 3. Decoupled Physical State Sensor & Semantic Judge
- **In-Browser Physical Sensor (`verify.py`)**: Dedicated JavaScript sensor reading raw physical properties, child text nodes, and validity flags from DOM and Shadow DOM roots.
- **Semantic Normalization Judge (`dom_verifier.py`)**: Independent Python-side matcher normalizing date format variations (e.g. `2024-06-01` vs `01/06/2024`), phone masks, and whitespace, enforcing the strict **0.0% False Success Truth Barrier**.

#### 4. Type-to-Reveal Combobox & Dynamic Options Engine
- **Sequential Keystroke Activation**: In `services/reactive_interaction_service.py` and `adapters/dom/set_field.py`, enabled automatic input focusing, sequential typing, and option popup waiting for AJAX-driven dynamic picklists.

#### 5. Anti-Bot Natural Human Simulation
- **Micro-Jitter Pointer Trajectory**: Simulated natural mouse movement curves with micro-jitter noise and authentic event sequences (`pointermove` ➔ `mousedown` ➔ `focus` ➔ `mouseup` ➔ `click`) to bypass aggressive bot detection systems (Cloudflare Turnstile, DataDome, PerimeterX).

#### 6. New CLI Tools & Inspection Capabilities
- **Ancestor Traversal (`--up <N>` / `--ascend <N>` / `--ancestor <N>`)**: Added container traversal in `wp find` to extract wrapper HTML up to $N$ ancestor levels for surrounding context and labels.
- **Targeted Element Crop Screenshot (`-s / --screenshot <path>`)**: Enabled bounding-box visual crop screenshots of specific elements in `wp find` for multimodal vision agents without capturing full pages.
- **Token-Saving Header Mode (`--strip-header` / `--no-header`)**: Global flag stripping diagnostic headers and ASCII banners across all CLI commands to conserve LLM context tokens.
- **Direct JavaScript Execution Engine (`wp eval` / `wp js` / `wp exec`)**: Complete new subcommand for executing arbitrary JavaScript, inspecting SPA state (`window.__INITIAL_STATE__`), mutating DOM nodes, and running script files (`--file`).
- **CSS Style Engine (`wp css` / `wp style`)**: Complete new subcommand for reading computed CSS properties (`-p`), applying inline style modifications (`--set`), and injecting global page stylesheets.

#### 7. Certified Test Suite
- Comprehensive test suite expanded in `tests/test_find_and_unicode.py` and `tests/test_enterprise_integration.py` to **86 passed tests (100%)** in 30.17 seconds.

## [2.3.0] - 2026-10-13

### The Truth Barrier & Enterprise Resilience Overhaul (12 Root-Cause Architectural Fixes)

#### 1. Supervisor Background Daemon Boot Fix (`WinError 10061`)
- **Root-Cause Entrypoint**: Added missing `if __name__ == "__main__": run_master_daemon()` entrypoint to `supervisor/master_daemon.py`, resolving background auto-spawn socket connection failures when invoked via `SupervisorClient.ensure_running()`.

#### 2. Strict Invalidation & Truth Barrier Hardening (`aria-invalid="true"`)
- **Comprehensive Element Validity Inspection**: Implemented `checkValidity(el)` in `adapters/dom/verify.py` inspecting `aria-invalid`, `data-invalid`, `data-error`, standard HTML5 `el.validity.valid`, and framework error classes (`invalidInput`, `is-invalid`, `ng-invalid-server`, `Mui-error`, `ant-input-status-error`, `v-input--error`, `is-error`, `field-error`, `input-error`) with escaped regex word boundaries (`\\b`).
- **Deterministic Rejection**: Updated `DOMDataMatcher.match()` in `services/dom_verifier.py` to immediately reject any field with `actual.get("is_invalid") is True`.
- **Light DOM Scope Confinement**: Restricted sections 1–4 in `verify.py` so exact element matches (`exactEl` via `@fld-N` or `id`) never leak or search across unrelated page elements.
- **Shadow DOM Bypass Elimination**: Confined Shadow DOM fallback in `services/field_interaction_service.py` to execute exclusively when elements are absent from the Light DOM, completely preventing Shadow DOM value reads from overriding Light DOM invalidation flags.
- **Event-Driven Blur & Selection Verification**: Enforced `el.blur()` with a 200ms settling delay prior to physical verification in `field_interaction_service.py`, requiring `pick_res.get("success") == True` before confirming picklist values.

#### 3. Complex Enterprise Picklists, Dynamic Pagination & Typeahead
- **Linked Dropdown Resolution (`aria-owns` / `aria-controls`)**: Extracted and prioritized `owns_id` in `adapters/dom/inspection.py`, `services/inspection_service.py`, `adapters/dom/probe.py`, and `adapters/dom/picklist.py`, targeting linked picklist containers (e.g. `58:_listSelect` for `57:_input` in SAP SuccessFactors JUIC) and preventing random listbox selection.
- **Server-Paginated Container Scrolling & Debounce**: Configured `scrollParent` and `searchRoot` in `picklist.py` and `probe.py` to target the scrollable container (`.globalMenu, .sf-combo-listselect, [onscroll]`), adding an async debounce delay (up to 900ms) at bottom scroll to allow AJAX pagination batches (`92:0`, `92:1`, etc.) to load.
- **Server Live Filter Triggering**: Replaced instant value fills with sequential typing (`press_sequentially(..., delay=25)`) in `field_interaction_service.py` to reliably fire `onkeyup` events that activate server-side filtering (`setFilter("contains", value)`).
- **Clean Single-Click Selection**: Replaced duplicate synthetic click dispatches with targeted `data-wp-pick-target="1"` selection in `picklist.py`.

#### 4. Scoped Interactions & Dynamic Repeaters
- **Guarded Dynamic Section Expansion**: Prevented speculative `+ Add` button clicks and empty required row generation in `services/field_interaction_service.py` and `services/form_application_pipeline.py` when target fields already exist in the DOM or local IDs (`@fld-N`, `@drop-N`) are provided.
- **Two-Stage Exact Button Matching**: Separated button resolution in `services/reactive_interaction_service.py` and `adapters/dom/reactive.py` into Strategy B1 (exact text match via `button:text-is`) and Strategy B2 (partial match fallback), eliminating collisions like `Save` vs `Saved Applications (1)`.
- **Scoped Button Dispatch & Icon Stripping**: Added support for hierarchical scoped button clicking (`--press "Section >> Button"`), local button IDs (`@btn-N`), and automatic PUA Unicode icon stripping (`[\uE000-\uF8FF]`).

#### 5. Schema Deduplication, Error Detection & Server State Reload
- **AJAX Re-render Deduplication**: Implemented `(local_id, label)` tracking in `services/schema_merger.py` to prune stale pre-render entries when SAP/SPAs regenerate field IDs on save.
- **Visible Error Filtering**: Enhanced `validators/form_validator.py` with physical visibility checks (`isVis`) and semantic error text filtering, ignoring hidden notices, loading spinners, and upload success banners.
- **Post-Action Accordion Expansion**: Added automatic section re-expansion (`expand_all_sections()`) in `supervisor/worker_handlers.py` following button presses and submissions.
- **Full Server State Reload (`wp reload` / `--reload`)**: Introduced dedicated `wp reload` subcommand and `--reload` flag across CLI, contracts, context, and worker handlers with `wait_until="load"` and field readiness loops.

#### 6. Test Suite Expansion & Validation
- Added automated test cases for invalidity rejection, schema deduplication, and reload contracts in `tests/test_verification_settle.py` and `tests/test_find_and_unicode.py`, elevating the certified test suite to **79 passing tests (100%)**.

## [2.2.0] - 2026-10-12

### Added
- **First-Class Programmatic Python SDK (`webpilot` & `webpilot_engine`)**:
  - Published the official `webpilot` package exposing high-level ergonomic client `WebPilot`.
  - Added seamless methods: `wp.inspect()`, `wp.apply()`, `wp.find()`, `wp.click()`, `wp.list_tabs()`, `wp.switch_tab()`, `wp.service_status()`, `wp.service_restart()`.
  - Dual-naming support: `import webpilot` and `import webpilot_engine` work identically.
  - Zero-touch auto-spawn: automatically connects to background supervisor or starts it detached via ProcessManager.
  - Context manager support (`with WebPilot() as wp:`).
  - Comprehensive unit test suite in `tests/test_python_sdk.py` (total test suite elevated to 77 passing tests).

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
