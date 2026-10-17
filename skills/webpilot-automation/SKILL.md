---
name: webpilot-automation
description: "WebPilot Engine (v2.7.3): Primary and default autonomous browser runtime, programmatic Python SDK, form inspector, and resilient web automator for modern SPAs, complex enterprise portals (Workday, SAP, Oracle, Taleo), and adversarial forms with a strict 0.0% false success truth barrier, multi-session tab lifecycle telemetry, DNS-over-HTTPS (DoH), DevTools console helpers, real-time network interception, and 9x native Playwright speed."
---

# WebPilot Engine (v2.7.3) — Master Skill Guide

`WebPilot` (`wp` / `webpilot`, PyPI: `webpilot-engine v2.7.3`, Python: `import webpilot`) is Antigravity's **primary, default, and approved browser automation engine** for all autonomous browsing, DOM inspection, enterprise form filling, precision HTML diagnostics, and resilient multi-step web workflows.

---

## 🏛️ The Five Architectural Pillars

1. **The Truth Barrier (Strict 0.0% False Success Guarantee)**:
   - 3-Stage Physical Verification Lifecycle: Inline DOM write-back verification, Pre-Submit barrier, and Post-Interaction barrier.
   - Categorizes every single field deterministically as `confirmed`, `unconfirmed`, or `failed`.
   - Rejects `maxlength` truncation false successes, requires authentic CDP trusted events for checkboxes (`isTrusted`), detects hidden/honeypot decoys, and protects against controlled-input revert races.
2. **Sub-Second Native Playwright Velocity (9x Speedup)**:
   - Average execution latency of ~1.17s per form. Full benchmark suite executes in ~58 seconds.
   - Event-driven DOM readiness and bounded 1,000ms locator actionability timeouts replace blind artificial pauses.
3. **Zero-Elevation Multi-Tier Process Architecture**:
   - Layer 1 (Master Daemon ~15 MB RAM) ➔ Layer 2 (Operational Worker with persistent in-memory Playwright contexts) ➔ Layer 3 (Sandboxed Chromium).
   - Runs 100% in unprivileged standard user space (zero Administrator escalation required).
4. **Autonomous Accordion & Dynamic Section Expansion**:
   - Universal `PageLifecycleService` automatically expands closed accordion sections (SAP, Workday, Bootstrap, `<details>`).
   - Repeater safeguarding ensures only authentic repeating row containers (`repeater`, `add-row`, `add-item`, `add-field`) trigger expansion.
5. **Precision HTML Diagnostics Pipeline & Second-Chance Retry**:
   - 5-stage HTML diagnostic pipeline (`Target & Ascent` ➔ `Search & Spine Pruning` ➔ `Structural Filtering` ➔ `Pretty-Print` ➔ `Slicing & Guard`).
   - Automatically re-attempts failed fields in a second pass once prerequisite dropdowns or parent fields unlock them.

---

## ⚡ Quick Reference Cheatsheet

| Task | Command Syntax | Description |
| :--- | :--- | :--- |
| **Inspect Page Schema & Sections** | `wp inspect` / `wp inspect --no-expand` | Detects `[OPEN]`, `[COLLAPSED]`, `@sec-N`, fields, and toggles. |
| **Direct Form Filling** | `wp apply --fill "Full Name=Alex" --fill "Email=alex@corp.com" --press "Next"` | High-speed field population with physical verification. |
| **Container Scoping** | `wp apply --fill "Employment History > Title=Engineer" --press "Education >> Add"` | Isolates fields in repeating sections (`>`, `>>`, `scope:`). |
| **Target Picklist by Option ID** | `wp apply --fill "Country=@opt-199"` | Direct option targeting avoiding text ambiguity. |
| **Strict Option Text Match** | `wp apply --fill "Degree=text:Bachelors"` | Forces exact visible text match on select/combobox. |
| **Precision HTML Diagnostics** | `wp find @fld-1 --html --up 2 --search "Salary"` | 5-stage spine pruning & diagnostic tree extraction (strict 20k default ceiling). |
| **Pruned Node Inspection** | `wp find @exc-3 --info` / `wp find @exc-3 --html` | Inspect metadata or expand pruned sibling subtrees. |
| **HTML Tag Whitelist / Blacklist** | `wp find @sec-2 --html --include "div,label,input" --exclude "svg,script"` | Eliminates tag clutter while preserving hierarchy. |
| **Line & Character Slicing** | `wp find @sec-2 --html --lines "1:40"` / `--chars ":5000"` | Safe window slicing with header/footer banner preservation. |
| **Clean Markdown Extraction** | `wp read` (or `wp read --url "https://site.com" -o "doc.md"`) | Trafilatura-powered high-density clean markdown extraction. |
| **Container-Confined Read** | `wp read --selector "main"` / `-s "#article"` | Extracts clean Markdown strictly from a target element without ads/sidebars. |
| **Pure Text Extraction** | `wp find <target> --text` / `-t` | Extracts pure visible `innerText` directly without HTML, SVG tags, or telemetry. |
| **Explicit Wait Command** | `wp wait --selector "#id" --timeout 5000` / `--network-idle` | Waits for selector (`visible`/`attached`/`detached`/`hidden`) or network idle. |
| **AJAX Combobox Typeahead Probe** | `wp probe <target> --search "Sudan"` | Simulates typing into AJAX picklist/Select2 to trigger remote searches and retrieve IDs. |
| **Persistent User Preferences** | `wp config set <key> <val>` / `wp config list` | Manages sticky flags (`strip_header`, `exclude`, `tab_timeout`, `session`, `dns`, `doh_servers`, `block_images`). |
| **DNS-over-HTTPS (DoH)** | `wp inspect --url "https://example.com" --no-dns` | Default AdGuard DoH enabled; bypass with `--no-dns` or configure custom `--doh-servers`. |
| **DevTools Console Helpers** | `wp eval "$('button.submit').click()"` / `$$('input')` / `$x('//h1')` | Automatically injects `$`, `$$`, `$x`, `$0`, and `copy()` into JavaScript evaluations. |
| **Block Images & Heavy Assets** | `wp inspect --block-images` / `wp apply --block-images` | Blazing-fast browsing and memory savings by suppressing all image resources. |
| **Pattern-Based Resource Block** | `wp block --pattern "*analytics*.js"` | Blocks arbitrary URL glob patterns in real time across the active browser context. |
| **Network API & Fetch Sniffing** | `wp sniff --types xhr,fetch` / `wp sniff --url "search"` | Live inspection and JSON preview of asynchronous background API calls. |
| **Dump Site Scripts & Assets** | `wp dump --types js --output ./site_scripts/` | Saves all website JavaScript files and assets locally for offline analysis. |
| **Capture API JSON Endpoints** | `wp capture --filter "/api/" --output ./api_data/` | Automatically extracts and writes all incoming background API responses to disk. |
| **HAR 1.2 Session Recording** | `wp network record -o session.har` | Records and exports complete browser network session traces in standard HAR 1.2 format. |
| **Multi-Session Instances** | `wp apply --session <name>` / `--session portal1` | Launches and isolates separate browser instances with distinct PIDs, profiles, and ports. |
| **Multi-Session Tabs Tree** | `wp tabs` / `wp tab list` | Enumerates all running browser instances and their child tabs with full hierarchical ownership. |
| **Tab Telemetry & Lifecycle** | `wp tab list` | Displays real-time `state` (`IDLE` / `LOADING`), `open_since`, `last_activity`, and `tab_timeout`. |
| **Tab Inactivity Auto-Close** | `wp tab timeout <index> <min>` / `wp tab new <url> --tab-timeout 15` | Configures per-tab inactivity watchdog (default: 30 min) auto-reaping idle background tabs. |
| **Regex Dropdown Search** | `wp find "@drop-1" -q "^Electrical Engineering$"` | Strict regex or substring search inside picklists. |
| **Paginated Dropdown View** | `wp find "@drop-1" --from 30 --show 20` / `--all` | Paginated or complete option inspection. |
| **File / Document Upload** | `wp apply --upload "resume=C:\Docs\CV.pdf"` | Native file upload handling. |
| **Session Cookies (Two-Way)** | `wp apply --cookies "cookies.json"` | Auto-loads cookies on start, persists refreshed cookies on exit. |
| **Export / Dump Cookies** | `wp cookies export -o "cookies.json"` / `wp cookies -d "example.com"` | Direct session cookies extraction, inspection, or filtering. |
| **Native Tab Management** | `wp tab list` / `wp tab new "url"` / `wp tab switch 1` / `wp tab close 1` | First-class multi-tab navigation and control. |
| **Live JavaScript Evaluation** | `wp eval "document.title"` / `wp eval --file "extractor.js"` | In-page JavaScript execution with circular reference sanitization and console helpers. |
| **Dynamic CSS Inspection / Tweaks**| `wp css --selector "#btn" --set "display: block !important"` | Live element styling or computed style inspection. |
| **Supervisor Service** | `wp service status` / `wp service restart` / `wp service stop` | Zero-elevation daemon lifecycle management. |

---

## 🎯 Core Grammar & Syntax Rules

- **Hierarchical Scoping**: To prevent field collisions across repeating sections, use:
  - Container Arrow: `Education > Degree=Bachelors` or `Employment >> Company=Acme`
  - Scope Prefix: `scope:Education:Degree=Bachelors`
  - Section Local ID: `@sec-7:Degree=Bachelors`
  - Scoped Button: `Employment >> Add`
- **Picklists & Values**:
  - `@opt-N` (Local Option ID) | `val:CODE` (Option Value) | `text:LABEL` (Strict Text) | `index:N` (1-based index) | `re:PATTERN` (Regex)
  - 80% Word Coverage Barrier: Guarantees no partial collision (e.g. `Aeronautical Engineering` is rejected when asking for `Electrical Engineering`).
- **Dates & Toggles**:
  - Auto-normalizes dates (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`).
  - Checkboxes accept `true`/`false`, `yes`/`no`, or comma-separated lists for multi-checkbox groups.
  - Switches (`role="switch"`) accept `on`/`off`.
- **Secrets Hygiene**:
  - `--fill "password=@env:VAR_NAME"` or `--fill "bio=@file:path.txt"` or `--fill "secret=@stdin"`.

---

## 📚 Detailed Reference Documentation Library

For exhaustive parameters, technical specifications, and advanced enterprise use cases, consult the specialized guides in `references/`:

| Topic | Reference Document | Description |
| :--- | :--- | :--- |
| **CLI Commands & Subcommands** | [references/cli-commands.md](references/cli-commands.md) | Exhaustive parameter matrix for all 12 subcommands (`inspect`, `apply`, `find`, `tab`, `read`, `cookies`, `shell`, `service`, `reload`, `eval`, `css`, `install`), with complete options and real-world ATS workflows. |
| **Scoping, Selectors & Normalization** | [references/scoping-and-selectors.md](references/scoping-and-selectors.md) | In-depth container isolation grammar, `scope:`, `>`, `>>`, `@sec-N:`, Type hints, colon-ID normalization (`[id="63:_txtFld"]`), PUA icon stripping, and DOM traversal (`--up N`). |
| **Picklists, Values & Pagination** | [references/picklists-and-values.md](references/picklists-and-values.md) | Option prefixes (`@opt-N`, `val:`, `text:`, `re:`), pagination flags (`--show`, `--from`, `--all`, `--page`), regex search (`-q`), Three-Tier Ranked Overlap Scoring, and date auto-formatting. |
| **Enterprise Safeguards & Diagnostics** | [references/enterprise-heuristics.md](references/enterprise-heuristics.md) | Dynamic row ID preservation (`getOrCreateLocalId`), cascading dependency alerts (`detectDependentParentField`), honeypots, modal dissolution, failure taxonomy, and retry loop. |
| **Python SDK & FastMCP Server** | [references/python-sdk-and-mcp.md](references/python-sdk-and-mcp.md) | Programmatic Python integration (`import webpilot`, `FlowOrchestrator`, `SupervisorClient`), and FastMCP server configuration (`webpilot-mcp`). |
