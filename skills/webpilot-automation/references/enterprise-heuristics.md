# Enterprise Safeguards, Heuristics & Diagnostics

Deep architectural safeguards, honeypot mitigation, secrets hygiene, failure classification, and retry loops in WebPilot.

---

## 1. Dynamic Row Local ID Preservation (`getOrCreateLocalId`)

### Problem Solved:
In enterprise platforms (SAP SuccessFactors, Workday, Taleo), clicking `Add new row` injects new DOM nodes dynamically. Naive scanners restart ID indexing from 0, corrupting existing field assignments (e.g. `First Name` unexpectedly changing from `@fld-1` to another ID or having data overwritten into the wrong row).

### Architectural Implementation (`inspection.py`):
1. **ID Preservation**: WebPilot checks whether an element already has a `data-wp-id`. If present, it preserves it unchanged.
2. **Cumulative Global Counters**: Pre-scans the DOM to identify the highest assigned indexes (`maxFld`, `maxDrop`, `maxOpt`, etc.). Newly injected row inputs receive clean, sequential increments starting from `maxFld + 1`.
3. **New Elements Telemetry**: Emits a `new_elements_captured` array to immediately inform the agent of newly available inputs without re-reading the entire page.

---

## 2. Cascading Dependency Detection & Visual Alerting

### Problem Solved:
Dependent dropdowns (e.g. `University` locked awaiting `Country of Education`, or `City` awaiting `State`) appear as disabled or empty without any clear indication of what unlocks them.

### Architectural Implementation (`universal_core.py`, `probe.py`, `find_cmd.py`):
1. **3-Tier Dependency Analysis**:
   - *HTML5 Attributes*: Scans for `data-parent`, `data-depends-on`, `data-cascade-from`, `data-master-field`, and reverse `aria-controls`.
   - *DOM Row Proximity*: Inspects preceding inputs in the same row or container (`.rcmFormField`, `tr`, `fieldset`).
   - *Semantic Pairing*: Recognizes common cascading pairs (`Country` ➔ `University`/`State`, `Category` ➔ `Subcategory`).
2. **Visual Telemetry Banner**:
   Emits an actionable diagnostic alert during `wp find` or `wp inspect`:
   ```text
    • Linked Parent : [@drop-2] 'Country of Education' (ID: country_sel)
    ⚠️ DEPENDENCY ALERT: Field is locked/empty awaiting parent selection 'Country of Education'!
   ```

---

## 3. Reactive Modal & Blocking Overlay Dissolution

### Escape Key Simulation:
Passing `"close"`, `"dismiss"`, `"cancel"`, or `"escape"` to `--press` automatically dispatches a hardware `Escape` key event to dismiss modal dialogs.

### Blocking Overlay Bypass (`dismiss_blocking_overlays`):
When a click is intercepted by a backdrop, loading mask, or sticky banner, WebPilot:
1. Detects the interception DOM event.
2. Identifies the overlay element obscuring the target.
3. Automatically dissolves or removes the overlay mask.
4. Re-attempts the click action seamlessly.

---

## 4. Anti-Bot & Honeypot Detection Shield (`isHoneypotOrHidden`)

To prevent agent disqualification or IP bans:
- Automatically detects hidden honeypot traps (`hp_`, `honeypot`, `tabindex="-1"`, `opacity: 0`, negative off-screen positioning `left: -500px`).
- Excludes honeypots from schema inspection and form population routines.

---

## 5. Security, Secrets Hygiene & Pipeline Redirection

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

### 5. Batch Fill Ingestion from Stdin (`--fill -`):
```powershell
Get-Content fields.txt | wp apply --fill -
```

### 6. Supervisor Token Security (`~/.webpilot/supervisor.token`):
- Generated at startup using 256-bit cryptographically secure randomness.
- Secured via OS ACLs (Windows user-only inheritance-stripped permissions; POSIX `chmod 0600`).
- Daemon HTTP endpoints require `X-Supervisor-Token` or `Authorization: Bearer <token>`.

---

## 6. Diagnostic Intelligence & Verification Failure Analysis

When an interaction finishes, WebPilot categorizes every field into deterministic buckets:
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

## 7. Token Conservation & AI Agent Optimization Guidelines

1. **Default Targeted Summary vs Full Schema**:
   - By default, `wp apply` outputs a **compact targeted summary** showing only modified fields. This saves up to **90% of LLM context window tokens**.
   - Use `--full-inspect` only when you explicitly need to inspect the entire new page state after submission.
2. **Speed & Token Optimization via `--no-auto-inspect`**:
   - For fast intermediate form steps (e.g. Step 1 of a 4-step wizard), add `--no-auto-inspect` to skip schema generation entirely until the final step.
3. **Targeted Dropdown Inspection via `wp find -q`**:
   - Instead of running `wp inspect --unpack-options` on a page with 250 countries and 500 job categories, use:
     ```powershell
     wp find "Country" -q "Saudi"
     ```
   - This returns only matching options, preventing context window exhaustion.
