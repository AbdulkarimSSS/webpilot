---
name: webpilot-automation
description: "WebPilot Engine (v2.1.1): Primary and default autonomous browser runtime, form inspector, and resilient web automator for modern SPAs, complex enterprise portals (Workday, SAP, Oracle, Taleo), and adversarial forms with a strict 0.0% false success truth barrier and 9x native Playwright speed."
---

# WebPilot Engine (v2.1.1) — Master Technical Specification & Operational Manual

## 1. Executive Overview & Primary Default Status
`WebPilot` (`wp` / `webpilot`, PyPI package: `webpilot-engine v2.1.1`) is Antigravity's **primary, default, and approved browser engine** for all autonomous web browsing, DOM introspection, complex form filling, and resilient multi-step web workflows.

### 🏛️ The Five Architectural Pillars:
1. **The Truth Barrier (Strict 0.0% False Success Guarantee)**:
   - WebPilot **never assumes success** and rejects speculative reporting.
   - Enforces a rigorous 3-Stage Physical Verification Lifecycle:
     - **Inline DOM Verification**: Re-reads the physical DOM property immediately after write to verify value binding.
     - **Pre-Submit Verification Barrier**: Re-verifies all previously confirmed inputs right before triggering submission.
     - **Post-Interaction Verification Barrier**: Re-verifies inputs after button clicks to catch reactive or adversarial JavaScript that clears or reverts fields upon clicking (e.g. S29, S44).
   - Telemetry accounts for every single field as strictly `confirmed`, `unconfirmed`, or `failed`.
2. **Sub-Second Native Playwright Velocity (9x Speedup)**:
   - Average execution latency of **1.17s per form** (down from 10.4s).
   - Full 50-scenario benchmark suite executes in **58.58 seconds** on standard Linux/Windows hardware.
   - Event-driven DOM readiness listeners and bounded 1,000ms locator actionability timeouts replace blind artificial pauses.
3. **Zero-Elevation Multi-Tier Process Architecture**:
   - **Layer 1 (Master Daemon)**: Ultra-lightweight (~15 MB RAM), zero Playwright imports, detached background auto-spawn via WMI (Windows) / double-fork (POSIX).
   - **Layer 2 (Operational Worker)**: Maintains persistent in-memory Playwright browser contexts across disconnected CLI calls.
   - **Layer 3 (Chromium)**: Sandboxed renderers with deterministic cascading process tree termination (`taskkill /F /T` or POSIX `killpg`).
   - Runs 100% in unprivileged standard user space (**zero UAC / Administrator escalation required**).
4. **Autonomous Accordion & Dynamic Section Expansion**:
   - Universal page lifecycle management (`PageLifecycleService`) settles loading overlays, spinners, and automatically deeply expands closed accordion sections across SAP SuccessFactors, Workday, Bootstrap, and HTML5 `<details>` without bespoke site hacks.
   - Automatically searches for and triggers dynamic repeaters (`Add`, `Add another`, `+`) via `expand_dynamic_section()` to spawn inputs that do not exist in the initial DOM (e.g. S27).
5. **Intelligent Second-Chance Retry Loop & Diagnostics**:
   - When initial field interactions complete, WebPilot automatically re-attempts any failed fields in a second pass. Fields unlocked or rendered actionable by earlier entries succeed without manual intervention.
   - Diagnostics report explicit failure causes: `disabled`, `readonly`, `obscured`, `not_found`, or `value_mismatch`.

---

## 2. Complete CLI Command Reference & Parameter Matrix

All commands are available globally in System `PATH` as **`wp`** or **`webpilot`**:

### Global Options (Available Across All Subcommands):
| Flag | Description | Default |
| :--- | :--- | :--- |
| `--config <path>` | Path to custom `settings.json` configuration file | `config/settings.json` |
| `--device-profile <path>` | Path to custom `device_profile.json` | `config/device_profile.json` |
| `--env-file <path>` | Path to custom `.env` file | `.env` |
| `--host <ip>` | Master Supervisor host address | `127.0.0.1` |
| `--port <port>` | Master Supervisor HTTP port | `9333` |
| `--token <token>` | Explicit Master Supervisor authentication token | Auto-read from `~/.webpilot/supervisor.token` |

---

### Command 1: Page & DOM Inspection (`wp inspect`)
Extracts a token-optimized, structured schema of inputs, dropdowns, buttons, and uploads.

```powershell
wp inspect [OPTIONS]
```

#### Dedicated Options:
- `--url <url>`: Target URL to open and inspect. (Optional if inspecting an already active live browser session).
- `--output <path>`: Save the full JSON schema to disk (e.g. `--output "schema.json"`).
- `--cookies <path>`: Load and inject session cookies from a JSON file before inspection.
- `--unpack-options`: Deeply probe and expand all dropdowns to collect available options (burns more tokens/time).
- `--summary-only`: Token conservation mode; returns a compact, high-level summary omitting exhaustive option arrays.
- `--screenshot <path>`: Save a visual PNG screenshot of the page.
- `--headed`: Run with a visible browser window (for human observation / manual CAPTCHA solving).
- `--keep-alive`: Maintain the browser session open across subsequent CLI commands (default behavior).
- `--close-session`: Terminate the active browser session and Chromium process immediately after inspection.
- `--list-tabs`: Enumerate all open tabs and windows in the active browser context.
- `--tab <index>`: Target a specific 0-based tab index in a multi-tab session.
- `--timeout-minutes <N>`: Set inactivity watchdog timeout (default: 30 minutes; `0` disables).
- `--standalone`: Execute in-process via `FlowOrchestrator` bypassing the Layer 1 Daemon.

#### Inspection Examples:
```powershell
# 1. Standard headless inspection of a new URL
wp inspect --url "https://careers.example.com/apply" --output "form_schema.json"

# 2. Inspect active live session with session cookies
wp inspect --cookies "session.json" --output "schema.json"

# 3. List all open browser tabs
wp inspect --list-tabs

# 4. Inspect specific tab in a multi-tab workflow
wp inspect --tab 1 --summary-only
```

---

### Command 2: Autonomous Form Population & Submission (`wp apply`)
Executes high-speed field population, file uploads, dynamic expansion, and button clicks with physical DOM verification.

```powershell
wp apply [OPTIONS]
```

#### Dedicated Options:
- `--url <url>`: Target URL. (Optional if interacting with the currently active page).
- `--fill "<target>=<value>"`: Input field and value to set (can be repeated indefinitely).
- `--press "<button>"`: Button or actionable element to click by text/selector (can be repeated).
- `--upload "<target>=<path>"`: File or document to upload (can be repeated indefinitely).
- `--data <path>`: Path to a JSON payload file (or `-` for streaming JSON via `stdin`).
- `--submit`: Automatically identify and click the primary form submission button after all fills and presses.
- `--cookies <path>`: Path to cookies JSON file to load into the session.
- `--no-auto-inspect`: Disable automatic post-interaction form inspection (saves latency and context tokens).
- `--full-inspect` / `--inspect-all`: Force full schema inspection output instead of targeted interaction summary.
- `--list-tabs`: List all open tabs before execution.
- `--tab <index>`: Target a specific tab index for field execution.
- `--screenshot <path>`: Capture post-execution screenshot.
- `--headed`: Run in visible browser mode.
- `--keep-alive`: Keep browser open for subsequent steps.
- `--close-session`: Cleanly terminate browser session upon command completion.
- `--timeout-minutes <N>`: Custom watchdog inactivity boundary.
- `--standalone`: Run directly in-process without daemon.

#### Form Population Examples:
```powershell
# 1. Direct multi-field form population and submission
wp apply --url "https://portal.example.com/login" `
         --fill "username=demo@example.com" `
         --fill "password=@env:PORTAL_PASSWORD" `
         --press "Sign In"

# 2. Sequential multi-turn application with resume upload
wp apply --fill "first_name=John" `
         --fill "last_name=Doe" `
         --fill "email=john.doe@example.com" `
         --fill "country=Saudi Arabia" `
         --upload "resume=C:\Docs\Resume.pdf" `
         --press "Save and Continue"

# 3. Passing JSON payload file
wp apply --data "applicant_profile.json" --submit

# 4. Streaming JSON payload via stdin pipe
Get-Content payload.json | wp apply --data - --submit

# 5. Token-optimized fast fill without post-inspection overhead
wp apply --fill "city=Riyadh" --fill "postal_code=11564" --no-auto-inspect
```

---

### Command 3: Element Finding & Deep Field Probing (`wp find` / `wp probe`)
Pinpoint elements by label, name, ID, or local selector, inspect live properties, search options, or extract raw HTML.

```powershell
wp find <target> [OPTIONS]
# Alias: wp probe <target> [OPTIONS]
```

#### Target Identifier Syntax:
- Local ID: `@fld-1`, `@btn-2`, `@sec-3`
- Field Label: `"Full Name"`, `"Country of Residence"`
- DOM Name / ID: `"applicant.email"`, `"countrySelect"`
- CSS Selector: `input[type="email"]`, `#ssn-input`

#### Dedicated Options:
- `-q`, `--query <string|regex>`: Filter long dropdown option lists by substring or regex pattern.
- `--options`: Include available picklist/select options (Default: True).
- `--no-options`: Suppress options collection for maximum speed and token savings.
- `--html`: Dump the element's physical outerHTML snippet.
- `--json`: Output raw machine-readable JSON telemetry.
- `--tab <index>`: Target a specific tab index.
- `--url <url>`: Target URL (if not already opened).
- `--cookies <path>`: Cookies JSON file.
- `--headed`: Run in headed browser mode.

#### Probe Examples:
```powershell
# 1. Inspect targeted field and its dropdown options
wp find "@fld-5"

# 2. Filter dropdown options by substring (e.g. find country)
wp find "Nationality" -q "Saudi"

# 3. Extract exact outerHTML snippet for DOM debugging
wp find "@fld-1" --html

# 4. Ultra-fast state check without fetching option arrays
wp find "Degree" --no-options --json
```

---

### Command 4: Multi-Tab & Window Management (`wp tab`)
Manage and coordinate multi-tab workflows, popup authentication windows, and external redirections.

```powershell
# 1. Enumerate all active tabs in the persistent session
wp inspect --list-tabs

# 2. Switch context to Tab 1 to complete secondary verification
wp apply --tab 1 --fill "otp_code=891024" --press "Verify"

# 3. Inspect DOM on secondary tab
wp find "@fld-1" --tab 1 --html

# 4. Return to main window (Tab 0)
wp apply --tab 0 --press "Finish"
```

---

### Command 5: Interactive REPL Shell (`wp shell`)
Launch a sub-second, interactive automation console attached directly to the persistent browser session:

```powershell
wp shell
```

#### Shell Commands:
- `url <target_url>`: Navigate to a new URL.
- `inspect`: Trigger instantaneous page inspection.
- `fill <field>=<value>`: Populate a field in the live DOM.
- `press <button_label>`: Click a button or link.
- `upload <field>=<filepath>`: Upload a file to a file input.
- `tab <index>`: Switch active tab index.
- `cookies [save|load] <path>`: Import or export session cookies.
- `status`: Display daemon, worker, and Chromium process telemetry.
- `exit` / `quit`: Disconnect shell (leaves browser session running in background).

---

### Command 6: Supervisor Service Management (`wp service`)
Inspect and manage the zero-elevation background daemon, worker processes, and memory watchdogs.

```powershell
wp service status   # View real-time PID telemetry for Layer 1, Layer 2, Layer 3 & idle timer
wp service restart  # Cascading kill of Layer 2 & 3; auto-spawns fresh worker in ~300ms
wp service stop     # Cleanly terminates all layers and reclaims 100% of memory
wp service start    # Explicitly spawn Layer 1 supervisor daemon in background
```

---

### Command 7: Browser Binaries Setup (`wp install`)
Downloads and configures the required Playwright browser engines:

```powershell
wp install          # Download required Playwright Chromium engine
wp install --all    # Download Chromium, Firefox, and WebKit
```

---

### Command 8: Agent Skill Introspection (`wp skill`)
Prints the machine-actionable AI agent skill specification directly to standard output for zero-configuration agent onboarding:

```powershell
wp skill
```

---

## 3. Field Interaction Protocols & Supported Value Syntaxes

WebPilot's DOM interaction engine (`adapters/dom/set_field.py` & `services/field_interaction_service.py`) handles virtually every HTML5, custom framework, and enterprise widget format:

### 1. Text, Email, Password, Number & Textarea Inputs:
- Direct DOM property setting with synthetic W3C event cascading: `focus` ➔ `keydown` ➔ `input` ➔ `keyup` ➔ `change` ➔ `blur`.
- Handles Shadow DOMs, `contenteditable` divs, and React/Vue synthetic event value trackers.

### 2. Checkbox Elements:
- Accepts flexible truthy and falsy values:
  - **Check / Enable**: `true`, `1`, `yes`, `checked`, `on`
  - **Uncheck / Disable**: `false`, `0`, `no`, `unchecked`, `off`
- Example:
  ```powershell
  wp apply --fill "terms_and_conditions=true" --fill "newsletter=false"
  ```

### 3. Radio Buttons:
- Targets radio groups by group name or label, selecting the specific option by text or value:
  ```powershell
  wp apply --fill "Gender=Male" --fill "Employment Status=Full-Time"
  ```

### 4. Native `<select>` Dropdowns:
- Resolves options by visible text, option value, or zero-based index:
  ```powershell
  wp apply --fill "Country=Saudi Arabia"
  ```

### 5. Enterprise Custom Picklists (SAP SuccessFactors, Workday, Salesforce, React-Select):
- Handles complex paginated picklists, search-as-you-type dropdowns, and dynamic option menus:
  - Automatically identifies list container (`[role="listbox"]`, `.rcmpaginatedselectlist`, `.globalMenu`).
  - Auto-scrolls picklist containers to bring off-screen options into view.
  - Matches by exact text, substring, or fuzzy similarity.
  - Dispatches full synthetic mouse lifecycle (`mousedown`, `focus`, `click`, `mouseup`).

### 6. Date & Time Pickers:
- Accepts ISO dates (`YYYY-MM-DD`), localized formats (`DD/MM/YYYY`, `MM/DD/YYYY`), and triggers native change listeners:
  ```powershell
  wp apply --fill "Birth Date=1995-05-15"
  ```

### 7. File & Document Uploads (`--upload`):
- Bridges file paths directly to hidden `<input type="file">` elements or file upload zones:
  ```powershell
  wp apply --upload "resume=C:\Users\User\Documents\cv.pdf"
  ```

---

## 4. Security, Secrets Hygiene & Pipeline Redirection

To maintain strict security standards and prevent plain-text credentials from leaking into shell history, process listings, or logs:

### 1. Environment Variable Binding (`@env:`):
```powershell
wp apply --fill "password=@env:PORTAL_SECRET_PASS"
```

### 2. Local Secret File Injection (`@file:`):
```powershell
wp apply --fill "cover_letter=@file:C:\Secure\cover_letter.txt"
```

### 3. Direct Standard Input Stream (`@stdin`):
```powershell
$credential | wp apply --fill "password=@stdin"
```

### 4. JSON Payload via Stdin Pipe (`--data -`):
```powershell
cat user_data.json | wp apply --data - --submit
```

### 5. Daemon Authentication Token (`~/.webpilot/supervisor.token`):
- Generated at startup using 256-bit cryptographically secure randomness.
- Secured via OS ACLs (Windows user-only inheritance-stripped permissions; POSIX `chmod 0600`).
- HTTP endpoints require `X-Supervisor-Token` or `Authorization: Bearer <token>`.

---

## 5. Diagnostic Intelligence & Verification Failure Analysis

When an interaction finishes, WebPilot categorizes all fields into deterministic buckets:
- `confirmed_fields`: Confirmed physically set in the DOM.
- `unconfirmed_fields`: Set attempt finished but post-read verification failed or was skipped.
- `failed_fields`: Could not be set.

### Failure Classification Taxonomy:
Every failed field includes an explicit machine-actionable diagnostic reason:
1. `disabled`: The element has a `disabled` attribute or `aria-disabled="true"`.
2. `readonly`: The element is locked in read-only mode (`readonly` attribute present).
3. `obscured`: Element exists in the DOM but is physically covered by a modal, dialog, or floating sticky header.
4. `not_found`: Element does not exist in the DOM hierarchy.
5. `value_mismatch`: The write was attempted, but subsequent DOM property re-read did not match the expected value.

### Autonomous Second-Chance Retry Pipeline:
1. WebPilot attempts all target fields in Phase 1.
2. If certain fields fail (e.g. because they were dependent on a prior dropdown or disabled pending earlier input), WebPilot detects this state.
3. Automatically triggers an immediate **Second-Chance Pass** for failed fields.
4. If one or more fields succeed in the second pass, the retry loop continues until state converges.

---

## 6. Token Conservation & AI Agent Optimization Guidelines

When invoking WebPilot from AI agent workflows:

1. **Default Targeted Summary vs Full Schema**:
   - By default, `wp apply` outputs a **compact targeted summary** showing only the fields you modified. This saves up to **90% of LLM context window tokens**.
   - Use `--full-inspect` only when you explicitly need to inspect the entire new page state after submission.
2. **Speed & Token Optimization via `--no-auto-inspect`**:
   - For fast intermediate form steps (e.g. Step 1 of a 4-step wizard), add `--no-auto-inspect` to skip schema generation entirely until the final step.
3. **Targeted Dropdown Inspection via `wp find -q`**:
   - Instead of running `wp inspect --unpack-options` on a page with 250 countries and 500 job categories, use:
     ```powershell
     wp find "Country" -q "Saudi"
     ```
   - This returns only matching options, preventing context window exhaustion.

---

## 7. Master ATS & Enterprise Form Automation Strategies

### Strategy A: Workday Multi-Step Application Wizard
```powershell
# Step 1: Open and inspect login/portal
wp apply --url "https://company.wd3.myworkdayjobs.com/Careers/job/123/apply"

# Step 2: Fill personal information and advance
wp apply --fill "Legal First Name=Alex" `
         --fill "Legal Last Name=Smith" `
         --fill "Phone Number=1234567890" `
         --press "Save and Continue"

# Step 3: Handle experience and education (triggers dynamic repeating sections)
wp apply --fill "Job Title=Software Engineer" `
         --fill "Company=TechCorp" `
         --upload "resume=C:\Resumes\Alex_Smith.pdf" `
         --press "Save and Continue"

# Step 4: Review and submit
wp apply --press "Submit" --submit
```

### Strategy B: SAP SuccessFactors Cascading Picklists
```powershell
# Select Country first to populate dependent State/Region picklist
wp apply --fill "country=Saudi Arabia"

# Second-chance pipeline automatically selects dependent region once loaded
wp apply --fill "cust_Region=Riyadh Region"
```

---

## 8. Python SDK & Programmatic Integration

For Python developers and native automation scripts:

```python
from webpilot import FlowOrchestrator, FormPayloadBuilder
from supervisor.client import SupervisorClient

# Method 1: Client RPC to Background Master Supervisor (Recommended)
client = SupervisorClient(base_url="http://127.0.0.1:9333")
response = client.apply_form(
    url="https://example.com/portal",
    fill_arguments=["username=user@example.com", "password=@env:PASS"],
    press_buttons=["Login"],
    submit=True
)
print("Confirmed:", response.confirmed_fields)
print("Failed:", response.failed_fields)

# Method 2: Direct In-Process FlowOrchestrator (Standalone / CI/CD)
orchestrator = FlowOrchestrator(headed=False)
result = orchestrator.execute(
    url="https://example.com/apply",
    fill_arguments=["name=John", "email=john@example.com"],
    press_buttons=["Next"],
    submit=False
)
```

---

## 9. WebPilot MCP Server Integration (`webpilot-mcp`)

WebPilot can be launched directly as a Model Context Protocol (MCP) server for Claude Desktop, Antigravity, or other AI agent harnesses:

```json
{
  "mcpServers": {
    "webpilot": {
      "command": "webpilot-mcp",
      "args": []
    }
  }
}
```

### Exposed MCP Tools:
- `inspect_page`: Introspect active or new web page schemas.
- `apply_form`: Populate fields, upload files, and click buttons.
- `probe_element`: Deeply probe element attributes, options, or HTML.
- `manage_service`: Inspect status, restart worker, or stop supervisor.
- `manage_tabs`: List, switch, and close browser tabs.
