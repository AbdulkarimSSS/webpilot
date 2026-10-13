# Picklists, Value Prefixes, Formatting & Filtering

Comprehensive guide to dropdown selection, value prefixes, pagination, regex queries, and data normalization in WebPilot.

---

## 1. Advanced Value Prefixes for Dropdowns & Picklists

When targeting select dropdowns, custom combo boxes, or picklists with `--fill`, WebPilot provides surgical value prefixes to guarantee the exact intended option is selected:

| Value Prefix | Description | Example |
| :--- | :--- | :--- |
| **`@opt-<N>`** | Select option directly by local option ID | `wp apply --fill "Country=@opt-199"` |
| **`val:<value>`** / **`value:<value>`** | Match by HTML `<option value="...">` attribute | `wp apply --fill "Country=val:SA"` |
| **`text:<string>`** | Force matching strictly by visible option text | `wp apply --fill "Major=text:Electrical Engineering"` |
| **`index:<N>`** / **`#<N>`** | Select by 1-based numerical index | `wp apply --fill "Experience=index:2"` |
| **`re:<pattern>`** / **`regex:<pattern>`** | Select option matching a Regular Expression | `wp apply --fill "Degree=re:^Bach"` |
| **Comma-separated list** | For `<select multiple>`, selects all listed values | `wp apply --fill "Skills=Python, JavaScript, Docker"` |

---

## 2. Dropdown Option Pagination & Range Limits (`wp find`)

When inspecting picklists with dozens or hundreds of items, WebPilot includes complete pagination controls to prevent token bloat while ensuring exhaustive access:

| Option Flag | Purpose & Description | Example Usage |
| :--- | :--- | :--- |
| **`--show <N>`** / **`--limit <N>`** / **`-n <N>`** | Maximum options to display (Default: 30). | `wp find @drop-1 --show 50` |
| **`--from <N>`** / **`--offset <N>`** / **`--start <N>`** | Start from 0-based offset index. | `wp find @drop-1 --from 30` *(shows options 31+)* |
| **`--all`** / **`--full`** | Dump all options completely without cutoff. | `wp find @drop-1 --all` |
| **`--page <N>`** | Display specific page number (1-based). | `wp find @drop-1 --page 2` *(Page 2)* |
| **`--page-size <N>`** | Items per page when using `--page` (Default: 20). | `wp find @drop-1 --page 2 --page-size 15` |

### Telemetry Header Format:
```text
 📋 Options (36 total | Page 2/2 (size: 20)):
   • [@opt-21] 'Legal Services'
   • [@opt-22] 'Manufacturing'
   • [@opt-23] 'Military'
   ...
   • [@opt-36] 'Other'
   ... and 6 more options (use --all, --show <N>, --page 2, --from 30, or -q to filter).
```

---

## 3. Regular Expression (Regex) Option Filtering (`-q` / `--query`)

The `-q` parameter in `wp find` supports full **in-browser Regular Expressions** with automatic substring fallback:

- **Anchors (Starts/Ends with):**
  - `wp find @drop-1 -q "^B"` *(Options starting with B)*
  - `wp find @drop-1 -q "Services$"` *(Options ending with Services)*
- **Alternation & Multiple Branches (OR):**
  - `wp find @drop-1 -q "Banking|Healthcare|Education"`
- **Advanced Regex Flags & Groups:**
  - `wp find @drop-1 -q "/(oil|gas|chemical)/i"`
- **Strict Full-String Lock:**
  - `wp find @drop-1 -q "^Electrical Engineering$"` *(Guarantees zero partial collision with other disciplines)*

---

## 4. Three-Tier Ranked Overlap Scoring & 80% Token Coverage Barrier

In enterprise picklists with hundreds of items, naive substring matching often picks the first alphabetical option containing any part of the query (e.g. matching `Engineering` to `Aeronautical and Astronautical Engineering` when the user asked for `Electrical Engineering`).

WebPilot uses a strict **Three-Tier Ranked Overlap Scoring Engine** (`picklist.py`, `set_field.py`):

1. **Level 1 (Exact Match)**:
   - 100% strict string, value, and local ID match. If found, chosen immediately.
2. **Level 2 (Continuous Phrase Match)**:
   - Unbroken exact phrase matching, ranked by minimal length-distance to the target.
3. **Level 3 (Strict Token Coverage & Jaccard Overlap)**:
   - Splits target query into word tokens: `['electrical', 'engineering']`.
   - Computes token coverage ratio against candidate options.
   - **80% Safety Barrier**: Any candidate option with `< 80%` word coverage is **strictly rejected**.
   - *Result*: `Aeronautical Engineering` (50% coverage) is discarded; `Electrical Engineering` (100% coverage) is selected and verified.

---

## 5. Universal Date Normalization & Auto-Formatting

WebPilot automatically detects and adapts dates to the target field's expected format:
- Accepts ISO (`YYYY-MM-DD`), slash (`DD/MM/YYYY`, `MM/DD/YYYY`), dot (`DD.MM.YYYY`), or dash formats.
- Inspects target input placeholders, pattern attributes, or adjacent format hints (`dd/MM/yyyy`, `MM/dd/yyyy`, `yyyy-MM-dd`).
- Transparently converts the input string before typing to prevent form validation rejection.

---

## 6. Checkbox & Switch Interaction Syntax

### Single Checkbox:
Accepts flexible truthy/falsy values:
- **Check**: `true`, `1`, `yes`, `checked`, `on`
- **Uncheck**: `false`, `0`, `no`, `unchecked`, `off`

```powershell
wp apply --fill "Subscribe=yes" --fill "Terms=true"
```

### Multi-Value Checkbox Groups:
Specify multiple comma-separated values to check multiple boxes under one group in a single pass:
```powershell
wp apply --fill "Interests=AI, Cloud, Security"
```

### ARIA Switches (`role="switch"`):
Interacts with custom framework switches (`[role="switch"]`):
```powershell
wp apply --fill "dark_mode=on" --fill "notifications=off"
```

---

## 7. Radio Buttons & Custom Radio Groups

Targets native radios or custom framework radio groups (`.globalRadio`, `[role="radio"]`, `.sfRadioInputField`), matching by option text, label, or `data-val`:
```powershell
wp apply --fill "Gender=Male" --fill "Employment Status=Full-Time"
```

---

## 8. Enterprise Custom Picklists (SAP, Workday, Salesforce)

For dynamic widgets that do not use standard HTML `<select>` elements:
- Automatically identifies container widgets: `[role="listbox"]`, `.rcmpaginatedselectlist`, `.globalMenu`.
- Automatically scrolls picklist containers to bring off-screen options into view.
- Dispatches full synthetic mouse event lifecycle (`mousedown`, `focus`, `click`, `mouseup`).
- Verifies selection state physically in the DOM post-click.
