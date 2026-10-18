# WebPilot CLI Subcommands & Options Reference

Complete reference for all 19 CLI subcommands in WebPilot Engine (v2.7.3).
Binary alias: `wp` or `webpilot` in global system `PATH`.

---

## 1. Global Options (Available Across All Subcommands)

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--config <path>` | Path to custom `settings.json` configuration file | `config/settings.json` |
| `--device-profile <path>` | Path to custom `device_profile.json` | `config/device_profile.json` |
| `--env-file <path>` | Path to custom `.env` file | `.env` |
| `--host <ip>` | Master Supervisor host address | `127.0.0.1` |
| `--port <port>` | Master Supervisor HTTP port | `9333` |
| `--token <token>` | Explicit Master Supervisor authentication token | Auto-read from `~/.webpilot/supervisor.token` |
| `--strip-header`, `--no-header` | Suppress verbose telemetry banners and headers from tool output to conserve tokens | `False` |
| `--with-header`, `--no-strip-header` | Invert persistent `strip_header` configuration and display full telemetry banners | `False` |
| `--session <name>` | Target named, isolated browser session instance (e.g. `--session portal1`) | `default` |
| `--no-dns` | Disable DNS-over-HTTPS (DoH) and use system DNS resolver | `False` |
| `--doh-servers <urls>` | Custom DNS-over-HTTPS resolvers (comma or space separated) | AdGuard DoH |
| `--block-images` | Block image downloads (.png, .jpg, .webp, .svg, etc.) to accelerate browsing | `False` |
| `--block-pattern <glob>` | Abort network requests matching glob pattern (e.g. `*analytics*.js`) | `None` |

---

## 2. Command 1: Page & DOM Inspection (`wp inspect`)

Extracts a token-optimized, structured schema of inputs, dropdowns, buttons, and uploads.

```powershell
wp inspect [OPTIONS]
```

### Options:
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
- `--reload`, `--refresh`: Hard-reload active page from server before inspecting.
- `--standalone`: Execute in-process via `FlowOrchestrator` bypassing the Layer 1 Daemon.

### Inspection Examples:
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

## 3. Command 2: Autonomous Form Population & Submission (`wp apply`)

Executes high-speed field population, file uploads, dynamic expansion, and button clicks with physical DOM verification.

```powershell
wp apply [OPTIONS]
```

### Options:
- `--url <url>`: Target URL. (Optional if interacting with the currently active page).
- `--fill "<target>=<value>"`: Input field and value to set (can be repeated indefinitely).
- `--press "<button>"`: Button or actionable element to click by text/selector (can be repeated).
- `--upload "<target>=<path>"`: File or document to upload (can be repeated indefinitely).
- `--data <path>`: Path to a JSON payload file (or `-` for streaming JSON via `stdin`).
- `--submit`: Automatically identify and click the primary form submission button after all fills and presses.
- `--cookies <path>`: Path to cookies JSON file to load into the session.
- `--reload`, `--refresh`: Hard-reload active page from server after actions.
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

### Population Examples:
```powershell
# 1. Direct multi-field form population and submission
wp apply --url "https://portal.example.com/login" `
         --fill "username=demo@example.com" `
         --fill "password=@env:PORTAL_PASSWORD" `
         --press "Sign In"

# 2. Sequential multi-turn application with resume upload & scoping
wp apply --fill "First Name=John" `
         --fill "Last Name=Doe" `
         --fill "Education > Degree=Bachelors" `
         --fill "Education > Country=Saudi Arabia" `
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

## 4. Command 3: Element Finding & Deep Field Probing (`wp find` / `wp probe`)

Pinpoint elements by label, name, ID, or local selector, inspect live properties, search options, or extract raw HTML.

```powershell
wp find <target> [OPTIONS]
# Alias: wp probe <target> [OPTIONS]
```

### Target Identifier Syntax:
- Local ID: `@fld-1`, `@btn-2`, `@sec-3`, `@drop-4`
- Field Label: `"Full Name"`, `"Country of Residence"`
- DOM Name / ID: `"applicant.email"`, `"63:_txtFld"`
- CSS Selector / Prefix: `css=input[type="email"]`, `css:#ssn-input`, `input[type="email"]`
- XPath Selector / Prefix: `xpath=//button[contains(., "Submit")]`, `//input[@name="title"]`
- Hierarchical Scoped Target: `"Educational Background > Degree"`, `"scope:Education:GPA"`

### Options:
- `--selector`, `--css`, `--xpath`, `-sel`: Search by arbitrary CSS selector or XPath.
- `-q`, `--query <string|regex>`: Filter long dropdown option lists by substring or regex pattern.
- `--search <string>`: Simulates human typing into AJAX comboboxes / Select2 fields to trigger remote background search APIs and discover unloaded option IDs.
- `--text`, `-t`: Extracts pure visible `innerText` directly without HTML, SVG tags, or telemetry banners.
- `--show <N>`, `--limit <N>`, `-n <N>`: Maximum number of options to display (Default: 30).
- `--from <N>`, `--offset <N>`, `--start <N>`: Starting offset index (0-based).
- `--all`, `--full`: Display all options without cutoff.
- `--page <N>`: 1-based page number.
- `--page-size <N>`: Page size when using `--page` (Default: 20).
- `--options`: Include available picklist/select options (Default: True).
- `--no-options`: Suppress options collection for maximum speed and token savings.
- `--rules`, `--constraints`: Display field input constraints and accepted formats (max/min length, pattern, inputmode, accept).
- `--error`, `--errors`: Display direct field-level validation error state and error messages (aria-invalid, describedby).
- `--deps`, `--dependencies`: Display field parent dependencies and cascading triggers.
- `--context`, `--frame`: Display containment environment (Main Document, Iframe, Shadow DOM).
- `--smart`, `--meta`: Consolidated shortcut to display all intelligent diagnostic cards (rules, error, deps, context) together.
- `--html`: Dump element's outerHTML snippet with 5-stage precision diagnostics.
- `--up <N>`, `--ascend <N>`, `--ancestor <N>`: Ascend N levels up the DOM hierarchy.
- `-s`, `--screenshot [path]`: Capture a visual bounding-box crop of the target element.
- `--json`: Output raw machine-readable JSON telemetry.
- `--tab <index>`: Target specific tab index.
- `--url <url>`: Target URL.
- `--cookies <path>`: Cookies JSON file.
- `--headed`: Run in headed browser mode.

### Probe Examples:
```powershell
# 1. Inspect targeted field and its dropdown options (default shows first 30)
wp find "@drop-1"

# 2. Strict Exact-Match Option Querying using Regular Expressions
wp find "@drop-1" -q "^Electrical Engineering$"

# 3. View options starting from index 30 onwards (options 31 to end)
wp find "@drop-1" --from 30

# 4. View all options completely without truncation
wp find "@drop-1" --all

# 5. Check input rules and constraints before filling (Max, Pattern, Mode, Accept)
wp find "@inp-2" --rules

# 6. Diagnose validation error and rejection message after form submission
wp find "@inp-2" --error

# 7. Check if field is trapped inside an Iframe or Shadow DOM
wp find "@inp-cv" --context

# 8. Full smart diagnostic report (rules + error + deps + context)
wp find "@inp-2" --smart

# 9. Ascend 2 levels up DOM hierarchy to inspect outer section HTML
wp find "@fld-1" --html --up 2

# 10. Arbitrary XPath / CSS selector inspection
wp find --selector "//button[contains(text(), 'Save')]" --html
```

---

## 5. Command 4: Dedicated Tab Management (`wp tab`)

Native, first-class tab management to coordinate multi-tab workflows, popup authentication windows, external redirections, and multi-portal operations.

```powershell
wp tab [ACTION] [TARGET] [OPTIONS]
```

### Subactions:
- `wp tabs` (or `wp tab list`): Displays formatted hierarchical tree of all open browser tabs across sessions, including real-time lifecycle telemetry (`state`: `IDLE` / `LOADING (loading since Ns)`, `open_since`, `last_activity`, `tab_timeout`).
- `wp tab new [URL] [--tab-timeout <min>]`: Spawns a new browser tab in the active session, optionally navigating to `URL` and setting an inactivity watchdog timeout.
- `wp tab switch <INDEX>`: Brings Tab #INDEX to the front and sets it as the active context for subsequent commands.
- `wp tab close [INDEX]`: Safely closes the tab at INDEX (or active tab if omitted), ensuring at least one tab or `about:blank` page remains open.
- `wp tab timeout <INDEX> <MINUTES>`: Configures an inactivity watchdog timeout for a specific tab (default: 30 min, 0 = disable auto-close).

### Options:
- `--url <url>`: Target URL for `wp tab new`.
- `--tab <index>`: Target tab index (0-based) for `switch`, `close`, or `timeout`.
- `--tab-timeout <minutes>`: Inactivity watchdog auto-close timeout in minutes.
- `--all-sessions`: List tabs across all running browser instances/sessions.
- `--json`: Output raw JSON response containing tabs array and active index.
- `--strip-header`: Suppress verbose telemetry banners.

### Tab Management Examples:
```powershell
# 1. Enumerate all active tabs with lifecycle state and timeout
wp tab list
wp tabs

# 2. Open a new tab navigating to a login or secondary portal with 15min inactivity timeout
wp tab new "https://auth.example.com/login" --tab-timeout 15

# 3. Set or update inactivity timeout for Tab #1
wp tab timeout 1 45

# 4. Switch active context to Tab #1 to complete secondary verification
wp tab switch 1
wp apply --fill "otp_code=891024" --press "Verify"

# 5. Close the secondary tab and automatically focus the remaining tab
wp tab close 1

# 6. Return to or verify main window (Tab #0)
wp tab list
wp apply --press "Finish"
```

---

## 6. Command 5: Interactive REPL Shell (`wp shell`)

Launch a sub-second, interactive automation console attached directly to the persistent browser session:

```powershell
wp shell
```

### Shell Commands:
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

## 7. Command 6: Supervisor Service Management (`wp service`)

Inspect and manage the zero-elevation background daemon, worker processes, and memory watchdogs:

```powershell
wp service status   # View real-time PID telemetry for Layer 1, Layer 2, Layer 3 & idle timer
wp service restart  # Cascading kill of Layer 2 & 3; auto-spawns fresh worker in ~300ms
wp service stop     # Cleanly terminates all layers and reclaims 100% of memory
wp service start    # Explicitly spawn Layer 1 supervisor daemon in background
```

---

## 8. Command 7: Full Server State Reload (`wp reload` / `wp refresh`)

Hard-reloads the active page directly from the server, clears client DOM cache, and returns an updated schema:

```powershell
wp reload [OPTIONS]
# Alias: wp refresh [OPTIONS]
```

```powershell
# Reload active live page and get updated field states
wp reload

# Reload and save full schema
wp reload --output "fresh_schema.json"
```

---

## 9. Command 8: Live JavaScript Execution (`wp eval` / `wp js` / `wp exec`)

Executes arbitrary JavaScript expressions or functions directly inside the active browser context and returns structured results:

```powershell
wp eval <script> [OPTIONS]
# Aliases: wp js <script> [OPTIONS] | wp exec <script> [OPTIONS]
```

### Options:
- `script` / `--code`, `-c`: JavaScript expression or function string to evaluate.
- `--file`, `-f <path>`: Path to `.js` script file to execute in the page.
- `--json`: Return output as formatted JSON.
- `--tab <index>`: Target a specific tab index.

### DevTools Console Helpers Injected Automatically:
WebPilot automatically injects standard browser DevTools convenience functions into all expressions:
- `$(selector, root=document)`: Shorthand for `root.querySelector(selector)`
- `$$(selector, root=document)`: Shorthand for `Array.from(root.querySelectorAll(selector))`
- `$x(xpath, root=document)`: Evaluates XPath expressions directly into an array of DOM nodes
- `$0`: Current active/focused element
- `copy(data)`: Clipboard copying helper

### Eval Examples:
```powershell
# 1. Evaluate quick expression with console helper
wp eval "$('h1').innerText"

# 2. Extract array of links via $$ querySelectorAll shorthand
wp eval "$$('nav a').map(a => a.href)" --json

# 3. Locate element via XPath $x shorthand
wp eval "$x('//button[contains(., \"Submit\")]')[0].click()"

# 4. Extract client-side token or session state
wp eval "window.__INITIAL_STATE__ || localStorage.getItem('token')" --json

# 5. Execute external script file
wp eval --file "scripts/custom_extractor.js"
```

---

## 10. Command 9: Dynamic CSS Injection & Inspection (`wp css` / `wp style`)

Injects custom CSS stylesheets or inspects/modifies computed element styles in real-time:

```powershell
wp css [target] [OPTIONS]
# Alias: wp style [target] [OPTIONS]
```

### Options:
- `--selector`, `-sel <selector>`: Target element selector to inspect or style.
- `--set`, `-s <rules>`: Apply inline CSS styles (e.g. unhiding obscured elements: `--set "display: block !important;"`).
- `--prop`, `-p <name>`: Inspect specific computed CSS property (e.g. `display`, `visibility`, `z-index`).
- `--file`, `-f <path>`: Path to `.css` file to inject into page header.

### CSS Examples:
```powershell
# 1. Un-hide an obscured submit button or modal container
wp css --selector "#submit-btn" --set "display: block !important; visibility: visible !important;"

# 2. Inspect computed visibility of an overlay
wp css --selector ".modal-overlay" --prop "display"

# 3. Inject global style tweaks
wp css "* { animation: none !important; transition: none !important; }"
```

---

## 11. Command 10: Browser Binaries Setup (`wp install`)

Downloads and configures the required Playwright browser engines:

```powershell
wp install          # Download required Playwright Chromium engine
wp install --all    # Download Chromium, Firefox, and WebKit
```

---

## 12. Command 11: Agent Skill Introspection (`wp skill`)

Prints the machine-actionable AI agent skill specification directly to standard output:

```powershell
wp skill
```

---

## 13. Command 12: Session Cookies Management (`wp cookies`)

Inspect, filter, dump, or export session cookies to JSON:

```powershell
wp cookies [export|dump|list] [OPTIONS]
# Alias: wp cookie [OPTIONS]
```

### Options:
- `--output`, `--out`, `-o <path>`: Path to write the exported cookies JSON file.
- `--domain`, `-d <string>`: Filter cookies matching domain or cookie name substring.
- `--url <url>`: Target URL to filter or navigate to before extraction.
- `--tab <index>`: Target specific tab index.
- `--json`: Output raw JSON list of cookies to stdout.
- `--strip-header`: Suppress verbose telemetry banners.

### Cookie Examples:
```powershell
# 1. Inspect all cookies in active browser session
wp cookies

# 2. Filter cookies for a specific domain
wp cookies --domain "example.com"

# 3. Export cookies directly to a JSON file
wp cookies export --out "C:\sessions\workday_cookies.json"

# 4. Two-way persistence with wp apply:
# Loads existing cookies on start AND writes refreshed cookies to the file upon completion!
wp apply --url "https://portal.com" --cookies "cookies.json" --fill "status=active"
```

---

## 14. Command 13: Explicit Element & Network Wait (`wp wait` / `wp wait_for`)

Waits deterministically for a CSS selector or XPath to reach an explicit state, or waits for all network activity to settle:

```powershell
wp wait [OPTIONS]
# Alias: wp wait_for [OPTIONS]
```

### Options:
- `--selector`, `-s <selector>`: Target CSS selector or XPath to wait for.
- `--state <state>`: Target element state to wait for: `visible` (default), `attached`, `detached`, `hidden`.
- `--timeout <ms>`: Maximum timeout in milliseconds (Default: 10000ms).
- `--network-idle`, `--networkidle`: Wait for network requests to settle (zero pending requests for at least 500ms).
- `--url <url>`: Target URL (optional; navigates before waiting).
- `--tab <index>`: Target specific tab index.
- `--strip-header`: Suppress verbose telemetry banners.

### Wait Examples:
```powershell
# 1. Wait for submit button to become visible
wp wait --selector "#submitBtn" --state visible --timeout 5000

# 2. Wait for loading spinner overlay to detach/hide
wp wait --selector ".loading-spinner" --state hidden

# 3. Wait for AJAX requests to settle after button click
wp wait --network-idle
```

---

## 15. Command 14: Persistent User Preferences & Sticky Flags (`wp config`)

Manages sticky configurations stored in `~/.webpilot/preferences.json`, automatically applied to all commands unless overridden:

```powershell
wp config [ACTION] [KEY] [VALUE] [OPTIONS]
# Aliases: wp pref | wp prefs | wp preference | wp preferences
```

### Supported Keys:
- `strip_header` (`true` / `false`): Always suppress telemetry headers.
- `exclude` (`tags` e.g. `'svg,script,style'`): Default HTML tags to prune during diagnostics.
- `include` (`tags` e.g. `'div,label,input'`): Default structural tag whitelist.
- `dns` (`true` / `false`): Default DNS-over-HTTPS status.
- `doh_servers` (`urls`): Default DoH resolver URLs.
- `block_images` (`true` / `false`): Default image resource blocking status.
- `tab_timeout` (`minutes`): Default inactivity watchdog timeout for all browser tabs.
- `session` (`name`): Default browser session name.

### Config Examples:
```powershell
# 1. List all active persistent preferences
wp config list

# 2. Set strip_header permanently active
wp config set strip_header true

# 3. Configure default DoH resolvers
wp config set doh_servers "https://dns.adguard.com/dns-query,https://adblock.doh.mullvad.net/dns-query"

# 4. Set persistent tag exclusions
wp config set exclude "svg,script,style,header,footer"

# 5. Clear a preference or reset all
wp config unset exclude
wp config clear
```

---

## 16. Command 15: Clean High-Density Markdown Reader (`wp read`)

Extracts clean, structured markdown content via Trafilatura, stripping boilerplate, ads, and navigation saving ~99.7% of LLM token context:

```powershell
wp read [OPTIONS]
# Aliases: wp clean_read | wp content
```

### Options:
- `--url <url>`: Target URL to fetch and read (optional if reading existing active tab).
- `--selector`, `-s <selector>`: Confine markdown extraction strictly to a specific container (e.g. `main`, `#article`).
- `-o`, `--output <path>`: Save clean markdown to local file path.
- `--tab <index>`: Target specific tab index.
- `--strip-header`: Suppress verbose telemetry banners.

### Read Examples:
```powershell
# 1. Read clean markdown from active tab
wp read

# 2. Extract content strictly from the main article container
wp read --selector "main" -o "article.md"

# 3. Read external URL without opening a visible browser window
wp read --url "https://news.ycombinator.com"
```

---

## 17. Command 16: Live Network API & Traffic Sniffing (`wp sniff`)

Sniffs and captures real-time fetch, XHR, and background API calls initiated by JavaScript:

```powershell
wp sniff [OPTIONS]
```

### Options:
- `--types <types>`: Comma-separated resource types to sniff (Default: `xhr,fetch`).
- `--url <pattern>` / `--filter <pattern>`: Filter traffic matching endpoint pattern or URL substring.
- `--timeout <ms>`: Listen duration in milliseconds (Default: 3000ms).
- `--tab <index>`: Target specific tab index.
- `--json`: Output raw JSON capture entries.
- `--strip-header`: Suppress verbose telemetry banners.

### Sniff Examples:
```powershell
# 1. Sniff all background XHR/Fetch API requests in real time
wp sniff --types xhr,fetch

# 2. Sniff specific search or autocomplete API endpoint
wp sniff --url "search" --timeout 5000

# 3. Output captured requests as structured JSON
wp sniff --filter "/api/v1/" --json
```

---

## 18. Command 17: Local Asset & Script Dumping (`wp dump`)

Extracts and downloads site scripts (.js) and assets locally grouped by sanitized filenames for offline analysis:

```powershell
wp dump [OPTIONS]
```

### Options:
- `--types <types>`: Comma-separated asset types to dump: `js` (default), `json`, `css`.
- `-o`, `--output <dir>`: Local destination directory (Default: `./site_scripts/`).
- `--filter <pattern>`: URL glob filter pattern.
- `--tab <index>`: Target specific tab index.

### Dump Examples:
```powershell
# 1. Dump all loaded website JavaScript files to local folder
wp dump --types js --output ./site_scripts/

# 2. Dump specific vendor libraries
wp dump --types js --filter "*vendor*" -o ./vendor_scripts/
```

---

## 19. Command 18: Background API JSON Response Capture (`wp capture`)

Intercepts and saves incoming JSON responses from background APIs into formatted local files:

```powershell
wp capture [OPTIONS]
```

### Options:
- `--filter <pattern>`: URL pattern or prefix to match (Default: `/api/`).
- `-o`, `--output <dir>`: Destination folder (Default: `./api_data/`).
- `--types <types>`: Types to capture (Default: `json`).
- `--tab <index>`: Target specific tab index.

### Capture Examples:
```powershell
# 1. Capture all background JSON API responses to folder
wp capture --filter "/api/" --output ./api_data/

# 2. Capture specific portal dataset responses
wp capture --filter "*wizardPortal*" -o ./portal_datasets/
```

---

## 20. Command 19: Real-Time Resource & URL Blocking (`wp block`)

Dynamically blocks images and URL glob patterns in real time across the active browser context:

```powershell
wp block [OPTIONS]
```

### Options:
- `--pattern <glob>`: URL pattern to block (can be repeated, e.g. `--pattern "*analytics*.js"`).
- `--images`: Block all image resources (.png, .jpg, .webp, .svg, etc.).
- `--clear`: Clear all active blocking rules.
- `--tab <index>`: Target specific tab index.

### Block Examples:
```powershell
# 1. Block analytics and tracker scripts
wp block --pattern "*analytics*.js" --pattern "*/gtm.js*"

# 2. Block images dynamically
wp block --images

# 3. Clear all blocking rules
wp block --clear
```

---

## 21. Command 20: Network Engine & HAR 1.2 Recording (`wp network`)

Manages network interception buffers and exports complete network traces in standard HAR 1.2 format:

```powershell
wp network [record|status|clear] [OPTIONS]
```

### Options:
- `record`: Exports captured network requests into a standard HAR 1.2 JSON file.
- `status`: Displays network interception manager statistics and captured entry counts.
- `clear`: Flushes in-memory traffic buffer.
- `-o`, `--output <path>`: Destination path for HAR file (Default: `session.har`).

### Network Examples:
```powershell
# 1. Record complete network session trace to HAR 1.2 file
wp network record -o session.har

# 2. Inspect network engine status
wp network status

# 3. Clear network buffer before starting a test flow
wp network clear
```

---

## 22. Master Enterprise Automation Workflows

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

### Strategy B: SAP SuccessFactors Cascading Picklists & Scoped Repeaters
```powershell
# 1. Select Country first to populate dependent State/Region picklist
wp apply --fill "country=Saudi Arabia"

# 2. Add new repeating row in Employment History with container scoping
wp apply --press "Employment History >> Add" `
         --fill "Employment History > Company Name=UNITED AMANA Contracting" `
         --fill "Employment History > Title=Technical Office Engineer"

# 3. Handle dependent Education fields (Country unlocks University)
wp apply --fill "Educational Background > Country of Education=Sudan (the)" `
         --fill "Educational Background > University=Omdurman Islamic University" `
         --fill "Educational Background > Degree=Bachelors"
```
