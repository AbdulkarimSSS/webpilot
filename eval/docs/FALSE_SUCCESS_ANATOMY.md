# Deep-Dive D1: Anatomy of Residual False Success in WebPilot

**Component Analyzed:** Post-fill DOM verification (`services/field_interaction_service.py`) & Supervisor Worker Execution (`supervisor/worker_process.py`)  
**Commits:** `b2046a1e6819269484e0cbe5553943be872b0533` (v2.0.7) vs `9799854cbef104dc369437df2cf2891da0f443ad` (v2.0.8)  
**Evaluation Finding:** In v2.0.7 false success is structural (hardcoded `success=True` + MCP omitting `unconfirmed_fields`). v2.0.8 fixes the *reporting* channel (`overall_success`, pre-submit barrier, MCP exposes `unconfirmed_fields`), cutting false-success cells from **26% → 14%**, but **field-level false-confirms (30) are unchanged** — the deeper correctness problem persists.  
**Basis:** clean 3×50 = 150-cell run per version, lab 8900 (`results/results_master_3x.json`, `results/results_v208_3x.json`).

---

## 1. The Operational Definition of False Success

In agentic web automation, **False Success** represents the most dangerous failure mode:  
> *A condition where the engine returns an exit code of `0`, emits `success=True` in its structured IPC contracts, reports `[✓] Set & Verified` in human-readable output, or returns successful tool execution to an LLM agent, while the physical DOM or backend submission payload contains missing, reverted, or incorrect data.*

An agent that encounters an explicit error can retry, inspect, or branch its strategy. An agent misled by False Success marks its task as complete and proceeds, corrupting user data or abandoning form workflows incomplete.

---

## 2. The Mechanics of the Deception: How WebPilot Lies in Code

The false success pipeline in WebPilot operates across four distinct architectural layers:

```
[Agent / CLI Invocation]
       │
       ▼
[Layer 1: Master Supervisor] (Proxies request, reads worker JSON)
       │
       ▼
[Layer 2: Operational Worker] (Executes apply flow)
       │
       ├─► 1. Immediate Readback: verify_field_value(k, v) at t=0ms
       │      └─► Passes prematurely before dynamic UI scripts revert/clear field (Scenario S44)
       │
       ├─► 2. Failed Verification Fallback: _playwright_click_fallback(k, v)
       │      └─► Blind click toggles already-checked checkboxes, clicks wrong elements
       │
        ├─► 3. Response Construction (worker_process.py:353 @ v2.0.7):
        │      └─► HARDCODED: success=True regardless of len(unconfirmed_fields)
        │          (v2.0.8 :376: overall_success = len(failed)==0 and len(unconfirmed)==0)
        │
        ▼
[Layer 3: Consumer Presentation]
        ├─► CLI: Checks resp.success (True) -> Exits with code 0! (v2.0.7)
        └─► FastMCP (mcp_server.py:137-145 @ v2.0.7): OMITS unconfirmed_fields!
            (v2.0.8 :142: unconfirmed_fields exposed — concealment fixed.)
```

The two honesty channels are therefore fixed in 2.0.8. What remains is **correctness**: fields that the engine believes it confirmed but the backend never received (false-confirms), plus the residual timing failures that drive most false-success cells.

---

## 3. Field-by-Field Verification Postcondition Matrix

| Field Type | DOM Property Read | Normalization Applied | Can It Produce False Confirm? | Can It Produce False Unconfirm? | Failure Mechanism & Scenario |
|:---|:---|:---|:---:|:---:|:---|
| **Text / Email / Password** | `element.value` | `.trim().toLowerCase()` | **YES** | **NO** | Passes at `t=0ms`; fails if JS clears field at `t=200ms` (**S44**). |
| **Controlled Input (React/Vue)** | `element.value` | `.trim().toLowerCase()` | **YES** | **YES** | JS setter updates internal DOM property without tripping synthetic React event tracker; re-renders reset value (**S22**). |
| **Masked Input (Phone/IBAN)** | `element.value` | `.trim().toLowerCase()` | **NO** | **YES** | User provides raw digits `1234567890`; DOM formats to `(123) 456-7890`. Verification string equality fails (**S23**). |
| **Native `<select>`** | `select.value` / `selectedOptions` | Text / value matching | **NO** | **YES** | Select by visible label vs underlying option value mismatch (**S02**). |
| **Custom ARIA Combobox** | `input.value` or `[aria-selected="true"]` | Text matching | **YES** | **YES** | Closed dropdown hides selected label; combobox input remains visually blank (**S03**). |
| **Radio Buttons** | `input.checked` / `aria-checked` | Value vs label | **NO** | **YES** | Non-standard radio wrappers (e.g. custom spans without ARIA) report unchecked (**S05**). |
| **Checkbox / Toggle** | `input.checked` / `aria-checked` | Boolean truthiness | **YES** | **YES** | Failed verification triggers click fallback which unchecks the box! (**S06**). |
| **Date Picker** | `input.value` | String match | **NO** | **YES** | Locale formatting differences (`YYYY-MM-DD` vs `DD/MM/YYYY`) (**S07**). |
| **`contenteditable`** | `element.innerText` | `.trim().toLowerCase()` | **YES** | **YES** | Rich text markup / trailing `<br>` breaks string equality (**S29**). |

---

## 4. The S44 Silent Revert Forensic Timeline

In scenario S44, a page script silently clears the `first_name` input 200 ms after user entry. Below is the forensic trace reconstructed from `results/evidence/master_3x/S44/run1` (v2.0.7). On v2.0.8 the same scenario is still recorded as a false success in the benchmark, but the engine additionally reports failure on a subset of timing cases (see §5), confirming the pre-submit barrier only partially closes this gap:

- **t = 0.000s:** `FieldInteractionService.set_field('first_name', 'Alice')` executes `SET_FIELD_DOM_SCRIPT`.
- **t = 0.045s:** Script sets `input.value = 'Alice'` and dispatches `input` and `change` events.
- **t = 0.050s:** `verify_field_value('first_name', 'Alice')` executes `VERIFY_FIELD_DOM_SCRIPT`.
- **t = 0.065s:** DOM query inspects `input.value`, finds `'Alice'`. Returns `True`.
- **t = 0.070s:** Worker appends `'first_name'` to `confirmed_fields` and logs:  
  `[✓] Set & Verified 'first_name' -> 'Alice'`
- **t = 0.200s:** **Page timer fires**: `setTimeout(() => { document.getElementById('first_name').value = ''; }, 200)`.
- **t = 0.205s:** Field is now physically **empty** in the DOM.
- **t = 1.000s:** Worker moves to button press: `ReactiveInteractionService.click_button('Submit')`.
- **t = 1.150s:** Form is submitted with `first_name=""`.
- **t = 1.200s:** Worker returns `SupervisorActionResponse(success=True)`.
- **t = 1.250s:** Lab checker inspects `/submit` payload:  
  `expected: "Alice" | actual: "" | ok: False | form_pass: False`.  
  **Result: False Success Recorded.**

---

## 5. Field-Level Confusion Matrix (clean 3×150 per version)

Aggregated over 150 cells (3 runs × 50 scenarios); 483 field-writes per version.

| Metric | 2.0.7 (`b2046a1`) | 2.0.8 (`9799854`) | Notes |
|:---|:--:|:--:|:---|
| **Fields evaluated** | 483 | 483 | non-extraction cells only |
| **Correct fields** | 429 (88.8%) | 441 (91.3%) | backend received expected value |
| **False confirms** (tool confirmed, backend wrong/blank) | **30** (6.2%) | **30** (6.2%) | **unchanged by 2.0.8** |
| **False unconfirms** (value correct, tool said unconfirmed) | 63 (13.0%) | **24** (5.0%) | settle window helps |
| **Other incorrect** | 24 (5.0%) | 12 (2.5%) | never-set / wrong target |

Companion cell-level results (the headline numbers):

| Metric | 2.0.7 | 2.0.8 |
|:---|:--:|:--:|
| Non-passing cells | 42/150 | 36/150 |
| of which **falsely reported success** | **39** | **21** |
| of which honestly reported failure | 3 | 15 |
| cells reported failure though form passed (conservative) | 0 | 12 |

### Architectural Root Causes:
1. **Absence of a settled postcondition check for async frameworks** — reading DOM state ~10 ms after dispatch misses React/Vue reconciliation; **partially** mitigated in 2.0.8 by `settle_delay_ms` + pre-submit barrier (false-unconfirms 63→24).
2. **False-confirm class not addressed** — fields the engine marks confirmed but which the backend never receives remain at 30 in both versions (e.g. custom ARIA comboboxes whose visible label updates without the real form control being set).
3. **v2.0.7 Optimistic IPC Masking** — the contract failed to enforce `success = (len(unconfirmed_fields) == 0 and len(failed_fields) == 0)`. **Fixed in 2.0.8** (`worker_process.py:376`).