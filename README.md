# WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-v1.40%2B-green.svg)](https://playwright.dev/)
[![Architecture](https://img.shields.io/badge/architecture-3--Tier%20Multi--Process-orange.svg)](#-3-tier-multi-process-architecture)
[![Standard User](https://img.shields.io/badge/security-Zero%20Elevation%20(No%20Admin)-success.svg)](#-zero-elevation-standard-user-security)
[![Tests Passing](https://img.shields.io/badge/tests-27%2F27%20passing-brightgreen.svg)](#-testing--verification)
[![CLI](https://img.shields.io/badge/cli-webpilot%20%7C%20wp-6f42c1.svg)](#-quick-start-guide)

An enterprise-grade, general-purpose autonomous browser engine and AI agent web runtime designed to inspect, interact with, fill, and operate any website, complex Single-Page Application (SPA), or enterprise portal (such as **SAP SuccessFactors**, **Workday**, **Greenhouse**, **Oracle Taleo**, and modern web apps) with zero site-specific selectors or hardcoding.

---

## 🏗️ 3-Tier Multi-Process Architecture

To solve the fundamental Windows OS limitation where terminal and subshell runners terminate background child processes upon exit (Windows Job Object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), WebPilot implements an elevated-resilient **Zero-Elevation Three-Tier Process Architecture**:

```
 ┌──────────────────────────────────────────────────────────────┐
 │          WebPilot CLI & REPL Shell (webpilot / wp)           │
 └──────────────────────────────┬───────────────────────────────┘
                                │ HTTP REST (127.0.0.1:9333)
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │         Layer 1: Master Supervisor Host (Daemon)             │
 │   • Zero Playwright Imports (~15 MB RAM)                     │
 │   • 30-Minute Inactivity Watchdog (Automatic RAM release)    │
 │   • Windows WMI Zero-Touch Auto-Spawn (Session 0 Breakout)   │
 └──────────────────────────────┬───────────────────────────────┘
                                │ stdin / stdout (Isolated JSON-RPC)
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │           Layer 2: Operational Worker Process                │
 │   • Playwright Runtime + SessionCoordinator                  │
 │   • Persistent in-memory browser session across CLI calls    │
 │   • DOM Services (Field, Auth, Reactive, Inspection)         │
 └──────────────────────────────┬───────────────────────────────┘
                                │ Process Tree Attachment
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │              Layer 3: Chromium Browser Engine                │
 │   • Chromium Main Process + GPU + Renderers                  │
 │   • Immediate Cascading Kill (taskkill /F /T /PID)           │
 └──────────────────────────────────────────────────────────────┘
```

### ⚡ Key Architectural Advantages:
1. **Persistent Browser Session Across CLI Calls**: Run step-by-step sequential commands (`open` -> `fill username` -> `fill password` -> `press submit`) without restarting the browser or losing active DOM state.
2. **Zero-Elevation / Standard User Mode**: Runs 100% as a standard, unprivileged user. **Zero administrative or UAC prompts required** (no `asudo` or Administrator escalation).
3. **Cascading Kill & Instant Self-Healing**: Terminating Layer 2 via `taskkill /F /T /PID` instantly eliminates all child Chromium processes with **zero zombie leaks**. Layer 1 survives and automatically respawns a clean Layer 2 in **~300ms**.
4. **30-Minute Watchdog Supervisor**: Automatically reclaims 100% of browser memory if the session remains idle for 30 minutes.

---

## 🌟 Core Features

- **Universal Inspection (`inspect`)**: Navigates to any URL and outputs a token-optimized, clean schema containing text fields, picklists, radio groups, checkboxes, file uploads, and action buttons.
- **Dynamic Field Population (`apply`)**: Fills fields dynamically via JSON payloads (`--data`) or inline CLI flags (`--fill`), with automatic type detection (text, combobox, radio, select).
- **Reactive Interaction Service**:
  - Automatically observes button clicks (`--press`).
  - Detects redirects and route transitions (`[🔀 Redirect]`) and auto-inspects the resulting page.
  - Detects and switches to newly spawned browser tabs/windows (`[🌐 New Window]`).
  - Detects dynamic DOM expansions and section accordions (`[📋 Dynamic Form Expansion]`).
- **Dynamic Loader Dissolution**:
  - Automatically identifies global blocking overlays (`#loading`, `.sapUiBusy`, `.busyIndicator`, `.modal-backdrop`, `[aria-busy="true"]`) and waits dynamically for their dissolution (`state="hidden"`).
  - Distinguishes between global page-blocking veils and local dropdown loaders.
- **Modal & Reactive Interaction Pipeline**:
  - Resolves modal popups and interactive dialogs using a 4-strategy non-destructive cascade: Native ID -> ARIA Role/Text Cascade -> JS In-DOM Click -> W3C `Escape` Key Protocol, preserving full DOM integrity.
- **Enterprise Picklist Auto-scrolling**:
  - Intelligent scrolling algorithm for virtualized dropdowns (such as SAP picklists with `aria-owns` and scroll containers).
- **Interactive REPL Shell (`shell`)**:
  - Interactive automation console with real-time feedback, tab switching, and live DOM inspection.

---

## 📦 Installation & Setup

### Option A: Install from PyPI or Editable Mode
```bash
# Editable install into environment
pip install -e .

# Or install dependencies directly
pip install -r requirements.txt
playwright install chromium
```

### Option B: Standalone Portable Binary (Windows)
Download `webpilot.exe` from GitHub Releases and run directly without needing a local Python installation.

---

## 🚀 Quick Start Guide

You can use the full `webpilot` command or the ultra-fast shortcut **`wp`** (or `python cli.py`):

### 1. Check & Start Background Supervisor Service
```powershell
# Check multi-tier service status
wp service status

# Start service (automatically auto-spawns detached host via WMI)
wp service start
```

### 2. Inspect Any Web Page
```powershell
wp inspect --url "https://example.com/portal" --output "schema.json" --screenshot "page.png"
```

### 3. Step-by-Step Multi-Turn Web Automation
Execute sequential commands on the **same live persistent browser session**:

```powershell
# Step 1: Open target portal and inspect initial schema
wp apply --url "https://example.com/login" --screenshot "step1.png"

# Step 2: Fill email only on the active persistent page
wp apply --fill "username=john.doe@example.com" --screenshot "step2.png"

# Step 3: Fill password only on the active persistent page
wp apply --fill "password=MySecurePassword123!" --screenshot "step3.png"

# Step 4: Click Sign In, detect redirect, auto-inspect profile, and save cookies
wp apply --press "Sign In" --cookies "session_cookies.json" --screenshot "step4.png"
```

### 4. Interactive REPL Shell Mode
Launch the sub-second interactive REPL shell:
```powershell
wp shell
```

Inside the shell, enter commands sequentially:
```text
webpilot> open https://example.com/login
webpilot> fill username=john.doe@example.com
webpilot> fill password=MySecurePassword123!
webpilot> press Sign In
webpilot> tabs
webpilot> screenshot dashboard.png
webpilot> exit
```

---

## 🛠️ CLI Reference

### Common Global Flags
- `--host`: Supervisor host address (default: `127.0.0.1`).
- `--port`: Supervisor port (default: `9333`).
- `--standalone`: Bypasses Master Supervisor to run in-process via `FlowOrchestrator`.

### `python cli.py inspect`
Inspects a URL or active session and outputs a clean form schema:
- `--url <URL>`: Target URL (optional if connecting to existing live session).
- `--output <path>`: Save full JSON schema to disk.
- `--screenshot <path>`: Capture page screenshot.
- `--cookies <path>`: Load session cookies.
- `--unpack-options`: Probe dropdowns to sample options.
- `--tab <index>`: Inspect specific tab by index.
- `--list-tabs`: List all open tabs in active session.

### `python cli.py apply`
Fills fields, uploads files, presses buttons, and validates state:
- `--url <URL>`: Target URL (optional if operating on existing page).
- `--data <path>`: Load key-value mappings from JSON file.
- `--fill <key=val>`: Set field value (can be repeated).
- `--press <btn>`: Click button with reactive observation (can be repeated).
- `--upload <kw=file>`: Upload document to upload area (can be repeated).
- `--cookies <path>`: Save or load session cookies.
- `--submit`: Submit form after filling.
- `--screenshot <path>`: Capture post-interaction screenshot.
- `--no-auto-inspect`: Disable automatic post-interaction schema inspection.

### `python cli.py service`
Manages the Master Supervisor daemon:
- `python cli.py service status`: Query real-time PID telemetry for Layer 1, Layer 2, and Layer 3.
- `python cli.py service restart`: Trigger cascading kill of Layer 2 & Layer 3, and respawn fresh worker (~300ms).
- `python cli.py service stop`: Cleanly terminate all tiers and release all memory.
- `python cli.py service start`: Ensure Layer 1 daemon is running.

---

## 📁 Project Directory Layout

```
universal_web_applier/
├── adapters/
│   ├── browser_adapter.py          # Playwright & Chromium connection adapter
│   ├── dom_scripts.py              # Pure JavaScript DOM manipulation scripts
│   ├── live_session_manager.py     # Legacy CDP live session fallback
│   └── upload_adapter.py           # Intelligent file upload handler
├── config/
│   ├── builder.py                  # Payload & Envelope builders
│   ├── settings.py                 # 3-tier settings resolver (env -> .env -> json)
│   ├── settings.json               # Active settings
│   └── device_profile.json         # Browser fingerprint & viewport settings
├── constants/
│   ├── contracts.py                # Single Source of Truth for JSON contracts
│   └── timeouts.py                 # Centralized timeouts and pauses
├── core/
│   └── models.py                   # Dataclasses & schema models
├── orchestration/
│   ├── context.py                  # Request & session contexts
│   ├── flow_orchestrator.py        # In-process standalone workflow pipeline
│   └── session_coordinator.py      # Session lifecycle coordinator
├── services/
│   ├── auth_navigation_service.py  # Login detection & portal transitions
│   ├── field_interaction_service.py# Field value injection & verification
│   ├── inspection_service.py       # DOM inspection & schema extraction
│   ├── inspection_formatter_service.py # Lean human-readable summary formatter
│   └── reactive_interaction_service.py # Post-click reactive changes observer
├── supervisor/
│   ├── contracts.py                # Supervisor request/response contracts
│   ├── master_daemon.py            # Layer 1: Lightweight HTTP Daemon
│   ├── worker_process.py           # Layer 2: Supervised JSON-RPC Worker
│   ├── client.py                   # Zero-Touch WMI client & HTTP proxy
│   └── shell.py                    # Interactive REPL automation shell
├── tests/
│   ├── test_contracts.py           # Wire contract unit tests
│   ├── test_engine_facade.py       # Engine facade tests
│   ├── test_live_session.py        # Live session tests
│   ├── test_orchestration.py       # Pipeline orchestration tests
│   ├── test_redaction.py           # Security & credential redaction tests
│   ├── test_services.py            # DOM interaction services tests
│   └── test_supervisor.py          # Master supervisor & client unit tests
├── cli.py                          # Unified CLI entrypoint
├── requirements.txt                # Python dependencies
├── pyproject.toml                  # Modern package specifications
└── README.md                       # Master documentation
```

---

## 🧪 Testing & Verification

Run the comprehensive unit test suite:
```powershell
python -m pytest tests/
```

All 27 contract and service tests execute in < 25s:
```text
tests\test_contracts.py ....                                             [ 14%]
tests\test_engine_facade.py ...                                          [ 25%]
tests\test_live_session.py ..                                            [ 33%]
tests\test_orchestration.py ...                                          [ 44%]
tests\test_redaction.py ....                                             [ 59%]
tests\test_services.py .......                                           [ 85%]
tests\test_supervisor.py ....                                            [100%]

============================= 27 passed in 22.58s =============================
```

---

## 🔒 Security & Privacy

- **Credential Redaction**: Passwords, auth tokens, and sensitive inputs are automatically redacted in CLI outputs, telemetry cards, and logs.
- **Zero Administrative Elevation**: Does not require Administrator rights or elevated Windows tokens.
- **Local Isolation**: Master Supervisor listens exclusively on loopback `127.0.0.1:9333`.

---

## 📄 License
MIT License. Free for commercial and personal use.
