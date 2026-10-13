---
name: webpilot-automation
description: "WebPilot Engine (v2.5.0): Primary and default autonomous browser runtime, programmatic Python SDK, form inspector, and resilient web automator for modern SPAs, complex enterprise portals (Workday, SAP, Oracle, Taleo), and adversarial forms with a strict 0.0% false success truth barrier and 9x native Playwright speed."
---

# WebPilot Engine (v2.5.0) — Master Skill Guide

`WebPilot` (`wp` / `webpilot`, PyPI: `webpilot-engine v2.5.0`, Python: `import webpilot`) is Antigravity's **primary, default, and approved browser automation engine** for all autonomous browsing, DOM inspection, enterprise form filling, and resilient multi-step web workflows.

---

## 🏛️ The Five Architectural Pillars

1. **The Truth Barrier (Strict 0.0% False Success Guarantee)**:
   - 3-Stage Physical Verification Lifecycle: Inline DOM write-back verification, Pre-Submit barrier, and Post-Interaction barrier.
   - Categorizes every single field deterministically as `confirmed`, `unconfirmed`, or `failed`.
2. **Sub-Second Native Playwright Velocity (9x Speedup)**:
   - Average execution latency of ~1.17s per form. Full 50-scenario benchmark suite executes in ~58 seconds.
   - Event-driven DOM readiness and bounded 1,000ms locator actionability timeouts replace blind artificial pauses.
3. **Zero-Elevation Multi-Tier Process Architecture**:
   - Layer 1 (Master Daemon ~15 MB RAM) ➔ Layer 2 (Operational Worker with persistent in-memory Playwright contexts) ➔ Layer 3 (Sandboxed Chromium).
   - Runs 100% in unprivileged standard user space (zero Administrator escalation required).
4. **Autonomous Accordion & Dynamic Section Expansion**:
   - Universal `PageLifecycleService` automatically expands closed accordion sections (SAP, Workday, Bootstrap, `<details>`).
   - Automatically searches for and triggers dynamic repeaters (`Add`, `Add another`, `+`) to spawn dynamic row inputs.
5. **Intelligent Second-Chance Retry Loop & Diagnostics**:
   - Automatically re-attempts failed fields in a second pass once prerequisite dropdowns or parent fields unlock them.
   - Explicit failure classification: `disabled`, `readonly`, `obscured`, `not_found`, or `value_mismatch`.

---

## ⚡ Quick Reference Cheatsheet

| Task | Command Syntax |
| :--- | :--- |
| **Inspect Page Schema** | `wp inspect --url "https://site.com/apply" --summary-only` |
| **Direct Form Filling** | `wp apply --fill "Full Name=Alex" --fill "Email=alex@corp.com" --press "Next"` |
| **Container Scoping** | `wp apply --fill "Employment History > Title=Engineer" --press "Education >> Add"` |
| **Target Picklist by Option ID** | `wp apply --fill "Country=@opt-199"` |
| **Strict Option Text Match** | `wp apply --fill "Degree=text:Bachelors"` |
| **Regex Dropdown Search** | `wp find "@drop-1" -q "^Electrical Engineering$"` |
| **Paginated Dropdown View** | `wp find "@drop-1" --from 30 --show 20` |
| **Inspect All Options (Full)** | `wp find "@drop-1" --all` |
| **File / Document Upload** | `wp apply --upload "resume=C:\Docs\CV.pdf"` |
| **Multi-Tab Execution** | `wp inspect --list-tabs` / `wp apply --tab 1 --press "Confirm"` |
| **Supervisor Service** | `wp service status` / `wp service restart` / `wp service stop` |

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
| **CLI Commands & Subcommands** | [references/cli-commands.md](references/cli-commands.md) | Exhaustive parameter matrix for all 11 subcommands (`inspect`, `apply`, `find`, `tab`, `shell`, `service`, `reload`, `eval`, `css`, `install`, `skill`), with complete options and real-world ATS workflows. |
| **Scoping, Selectors & Normalization** | [references/scoping-and-selectors.md](references/scoping-and-selectors.md) | In-depth container isolation grammar, `scope:`, `>`, `>>`, `@sec-N:`, Type hints, colon-ID normalization (`[id="63:_txtFld"]`), PUA icon stripping, and DOM traversal (`--up N`). |
| **Picklists, Values & Pagination** | [references/picklists-and-values.md](references/picklists-and-values.md) | Option prefixes (`@opt-N`, `val:`, `text:`, `re:`), pagination flags (`--show`, `--from`, `--all`, `--page`), regex search (`-q`), Three-Tier Ranked Overlap Scoring, and date auto-formatting. |
| **Enterprise Safeguards & Diagnostics** | [references/enterprise-heuristics.md](references/enterprise-heuristics.md) | Dynamic row ID preservation (`getOrCreateLocalId`), cascading dependency alerts (`detectDependentParentField`), honeypots, modal dissolution, failure taxonomy, and retry loop. |
| **Python SDK & FastMCP Server** | [references/python-sdk-and-mcp.md](references/python-sdk-and-mcp.md) | Programmatic Python integration (`import webpilot`, `FlowOrchestrator`, `SupervisorClient`), and FastMCP server configuration (`webpilot-mcp`). |
