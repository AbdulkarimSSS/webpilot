# 🚀 WebPilot Engine v2.0.12

### Enterprise Autonomous Browser Engine, Universal Form Inspector & AI Agent Web Runtime

[![Version](https://img.shields.io/badge/version-v2.0.12-blue.svg)](pyproject.toml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/playwright-v1.40%2B-green.svg)](https://playwright.dev/)
[![Architecture](https://img.shields.io/badge/architecture-3--Tier%20Multi--Process-orange.svg)](#-3-tier-multi-process-architecture)
[![Benchmark](https://img.shields.io/badge/benchmark-50%20Scenarios%20%7C%20100%25%20Solvable%20Pass-brightgreen.svg)](#-empirical-adversarial-benchmark-suite-50-scenarios)
[![False Success](https://img.shields.io/badge/false%20success-0.0%25%20(Zero)-success.svg)](#-the-truth-barrier-00-false-success-guarantee)
[![Latency](https://img.shields.io/badge/latency-1.17s%20%2F%20form%20(9x%20Boost)-purple.svg)](#-the-performance-breakthrough-9x-native-speedup)
[![Unit Tests](https://img.shields.io/badge/tests-58%2F58%20passing%20(100%25)-brightgreen.svg)](#-unit-testing--verification)
[![License](https://img.shields.io/badge/license-MIT-informational.svg)](LICENSE)

**WebPilot Engine** is a high-performance, enterprise-grade autonomous browser engine and AI agent web runtime designed to inspect, interact with, populate, and operate complex modern web applications, single-page apps (SPAs), dynamic Shadow DOMs, and enterprise ATS/ERP widgets (Workday, SAP SuccessFactors, Taleo, Oracle Cloud, custom modal flows) with **zero site-specific selectors or hardcoded scripts**.

---

## 🏛️ 3-Tier Zero-Elevation Multi-Process Architecture

To overcome the fundamental operating system limitation where terminal runners and subshells terminate background browser child processes upon command completion (such as the Windows Job Object `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`), WebPilot implements a hardened **Zero-Elevation Three-Tier Process Architecture**:

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │               WebPilot CLI & REPL Shell (webpilot / wp)                │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP REST (127.0.0.1:9333)
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │              Layer 1: Master Supervisor Host (Daemon)                  │
 │   • Ultra-Lightweight IPC Controller (~15 MB RAM)                      │
 │   • Zero Playwright Imports (Starts instantaneously)                  │
 │   • 30-Minute Inactivity Watchdog Sentinel (Automatic RAM release)     │
 │   • Detached Background Auto-Spawn via Windows WMI / POSIX double-fork │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ stdin / stdout (Isolated JSON-RPC)
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                Layer 2: Operational Worker Process                     │
 │   • Playwright Runtime + SessionCoordinator                            │
 │   • Persistent in-memory browser session maintained across CLI calls   │
 │   • Decoupled DOM Services (Field, Auth, Reactive, Inspection)         │
 │   • Multi-Stage Verification Barrier & Dynamic Section Expander        │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Process Tree Attachment
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                   Layer 3: Chromium Browser Engine                     │
 │   • Chromium Main Process + GPU Process + Sandboxed Renderers          │
 │   • Deterministic Cascading Termination (Zero Zombie Leaks)            │
 └────────────────────────────────────────────────────────────────────────┘
```

### ⚡ Architectural Pillars:
1. **Persistent Browser Session Across Disconnected CLI Invocations**: Execute multi-step sequential interactions (`open` ➔ `fill profile` ➔ `upload resume` ➔ `press submit`) without closing the browser, losing session state, or re-authenticating.
2. **Zero Administrative Elevation (Standard User)**: Operates 100% in unprivileged standard user space. **Zero Administrator / UAC escalation required**.
3. **Deterministic Cascading Termination & Auto-Healing**: Terminating Layer 2 instantly tears down the entire Chromium process tree with zero zombie process leaks. Layer 1 automatically auto-spawns a fresh Layer 2 worker in **~300ms**.
4. **Memory Watchdog Sentinel**: Automatically reclaims all browser resources and cleanly exits after 30 minutes of idle inactivity.

---

## ⚡ The Performance Breakthrough (9x Native Speedup)

In version **2.0.11 and 2.0.12**, WebPilot underwent a comprehensive timing and latency overhaul, transitioning from legacy synthetic delays to **reactive, event-driven DOM readiness**:

* **Elimination of Artificial Pauses**: Replaced blind 3,000ms pauses (`PAUSE_DOM_CONTENT_LOADED_MS`, `PAUSE_REACTIVE_STABILIZE_MS`) with deterministic condition checking and DOM event listeners.
* **Bounded Actionability Timeouts**: Added strict 1,000ms locator timeouts to prevent Playwright from hanging for 30 seconds on non-actionable or overlayed buttons (e.g. S10 overlay trap).
* **Conditional Accordion Expansion**: Section expansions only wait if closed accordions were actually detected and opened.

### 📊 Benchmark Execution Latency Comparison:

| Benchmark Metric | Legacy / Pre-v2.0.11 | WebPilot v2.0.12 | Performance Gain |
| :--- | :---: | :---: | :---: |
| **Full 50-Scenario Test Suite** | **519.9 seconds** (~8.6 mins) | **58.58 seconds** | **8.9x Faster (-88.7%)** |
| **Average Latency Per Form** | **10.40 seconds** | **1.172 seconds** | **Native Playwright Speed** |
| **Fastest Scenario Execution** | ~4.20 seconds | **0.68 seconds** | **6.2x Faster** |

---

## 🛡️ The Truth Barrier: 0.0% False Success Guarantee

A major vulnerability in AI browser agents and web automation frameworks is **False Success (Silent Failure)**: claiming an operation succeeded when inputs were silently rejected, cleared by reactive JavaScript, or blocked by invisible validation errors.

WebPilot enforces a strict **Multi-Stage Physical Truth Verification Pipeline**:

```
[Fill Attempt] ➔ [1. Inline DOM Re-read] ➔ [2. Pre-Submit Verification Barrier] ➔ [Button Click / Submit] ➔ [3. Post-Interaction Verification Barrier]
```

1. **Inline DOM Re-read (`verify_field_value`)**: Immediately reads the physical DOM property after setting an input to confirm that the value took effect.
2. **Pre-Submit Verification Barrier (`_reverify_fields`)**: Re-checks all previously confirmed fields right before triggering submit buttons to catch delayed resets.
3. **Post-Interaction Verification Barrier**: Re-verifies all fields after button clicks to detect adversarial scripts or form handlers that clear or revert values upon clicking (e.g. S29, S44).
4. **Dynamic Repeating Section Expansion (`expand_dynamic_section`)**: Automatically identifies and clicks dynamic repeater triggers (`Add`, `Add another`, `+`) when target fields do not yet exist in the DOM (e.g. S27).
5. **Categorized Telemetry Accounting**: Categorizes every field deterministically as `confirmed`, `unconfirmed`, or `failed`. If even a single field is unconfirmed, WebPilot reports operation failure rather than making speculative success claims.

---

## 🧹 Clean Architecture & SOLID Engineering (v2.0.12)

Following an extensive architectural refactoring milestone (Commit `b9dd28c`), the codebase adheres to strict enterprise software standards:

* **Strict 3-Tier Layering & Separation of Concerns**:
  - **Presentation Layer**: CLI (`cli.py`), REPL Shell (`supervisor/shell.py`).
  - **Orchestration & Supervision**: Supervisor Daemons (`master_daemon.py`, `worker_process.py`), Pipeline Orchestration (`flow_orchestrator.py`).
  - **Domain & DOM Interaction**: Unified domain services (`FieldInteractionService`, `InspectionService`, `ReactiveInteractionService`, `AuthNavigationService`).
* **DRY Consolidation**:
  - Eliminated duplicate repeating section search logic from `worker_process.py` and `form_filler_service.py`, centralizing it in `FieldInteractionService.expand_dynamic_section()`.
  - Consolidated duplicate pre-submit and post-interaction passes into `OperationalWorker._reverify_fields()`.
* **Decoupled Imports & Single Source of Truth**:
  - Severed legacy circular imports in `config/settings.py` by importing directly from `core.models` and `core.exceptions`.
  - Removed deferred inline imports in `builder.py` in compliance with PEP 8.
* **Defensive Runtime Safety**:
  - Hardened tuple unpacking and dynamic attribute resolution across mock and dynamic worker environments.

---

## 🔬 Empirical Adversarial Benchmark Suite (50 Scenarios)

The repository includes a complete, fully reproducible **50-Scenario Adversarial Benchmark Suite** under [`eval/`](eval/) containing real-world edge cases, anti-automation traps, and complex widget patterns:

### Certified Evaluation Results (v2.0.12 on Linux Cloud VPS):

| Benchmark Metric | Result / Score | Certification Note |
| :--- | :---: | :--- |
| **Total Scenarios Evaluated** | **50 Scenarios** | Full comprehensive suite |
| **Solvable Form Pass Rate** | **47 / 47 (100.0%)** | 100% of solvable forms completed |
| **Total Form Pass Rate** | **47 / 50 (94.0%)** | 3 remaining are unsolvable traps (S02, S06, S22) |
| **False Success Rate** | **0.0% (0 / 50)** | **Zero False Claims** |
| **Field Accuracy** | **159 / 161 (98.76%)** | Accurate physical DOM value binding |
| **Total Suite Wall Clock Time** | **58.58 seconds** | Sub-60-second full suite execution |
| **Average Time Per Scenario** | **1.172 seconds** | Sub-1.5s per form average |
| **Worker Crashes / Zombie Reaps** | **0 (Zero)** | 100% process stability |

### Reproducing the Benchmark:
```bash
# 1. Start the local evaluation lab server
python eval/lab/server.py --port 8900 &

# 2. Run the monitored benchmark suite
python eval/scripts/run_suite.py --tool webpilot --wp wp --runs 1 --label v2012 --out-dir eval/results
```

The benchmark fixtures, expected JSON contracts, and in-depth analytical reports are accessible in:
* [`eval/lab/scenarios.py`](eval/lab/scenarios.py) — Definitions of all 50 test scenarios.
* [`eval/docs/REPORT.md`](eval/docs/REPORT.md) — Comprehensive benchmark evaluation report.
* [`eval/docs/FALSE_SUCCESS_ANATOMY.md`](eval/docs/FALSE_SUCCESS_ANATOMY.md) — Architectural breakdown of false success prevention.
* [`eval/docs/DEFECTS.md`](eval/docs/DEFECTS.md) — Documented edge cases, trap analysis, and resolution history.

---

## 🚀 Quick Start Guide

### Installation:
```bash
# Clone the repository
git clone https://github.com/AbdulkarimSSS/webpilot.git
cd webpilot

# Install in editable mode
pip install -e .

# Install Playwright browser binaries
playwright install chromium
```

You can use either the full `webpilot` command or the shortcut **`wp`**:

### 1. Inspect Any Web Page
Extract a token-optimized, clean schema of inputs, dropdowns, and buttons:
```bash
wp inspect --url "https://example.com/portal" --output "schema.json" --screenshot "page.png"
```

### 2. Autonomous Form Filling & Submission
Fill fields using JSON data payloads or inline flags:
```bash
# Using inline arguments
wp apply --url "https://example.com/login" \
         --fill "username=demo@example.com" \
         --fill "password=MySecurePassword123!" \
         --press "Sign In" \
         --submit

# Using JSON payload file
wp apply --url "https://example.com/job-application" \
         --data "applicant_data.json" \
         --press "Submit Application"
```

### 3. Step-by-Step Multi-Turn Execution
Commands run sequentially against the **same active persistent browser session**:
```bash
# Step 1: Open target portal
wp apply --url "https://example.com/register"

# Step 2: Fill personal details
wp apply --fill "first_name=John" --fill "last_name=Doe"

# Step 3: Fill contact info
wp apply --fill "email=john.doe@example.com" --fill "phone=+1234567890"

# Step 4: Click Next, detect dynamic expansion, and complete registration
wp apply --press "Next" --submit --screenshot "complete.png"
```

### 4. Interactive REPL Shell
Launch the sub-second interactive automation shell:
```bash
wp shell
```
```text
webpilot> open https://example.com/login
webpilot> fill username=john.doe@example.com
webpilot> fill password=MyPassword123!
webpilot> press Sign In
webpilot> tabs
webpilot> screenshot dashboard.png
webpilot> exit
```

### 5. Supervisor Service Management
```bash
wp service status   # View real-time PID telemetry for Layer 1, Layer 2, and Layer 3
wp service restart  # Cascading kill of Layer 2 & 3, auto-respawns in ~300ms
wp service stop     # Cleanly terminate all processes and reclaim 100% of memory
```

---

## 🧪 Unit Testing & Verification

WebPilot includes a comprehensive test suite covering IPC wire contracts, supervisor lifecycle, redaction, and DOM interaction services:

```bash
pytest tests/
```

All **58 unit tests** execute in < 28 seconds:
```text
tests/test_contracts.py .......                                          [ 12%]
tests/test_engine_facade.py .....                                        [ 20%]
tests/test_live_session.py ...                                           [ 25%]
tests/test_orchestration.py ......                                       [ 36%]
tests/test_redaction.py ........                                         [ 50%]
tests/test_services.py ..............                                    [ 74%]
tests/test_supervisor.py ................                                [100%]

============================== 58 passed in 27.42s ==============================
```

---

## 🔒 Security & Privacy

* **Automatic Credential Redaction**: Passwords, API tokens, and sensitive inputs are automatically masked as `***REDACTED***` in CLI output, logs, and telemetry cards.
* **Standard User Security**: Requires zero Administrator / root permissions; never triggers UAC prompts or elevates tokens.
* **Local Loopback Isolation**: The Master Supervisor listens strictly on `127.0.0.1:9333`.

---

## 📄 License
This project is licensed under the MIT License — free for commercial, research, and personal use.
