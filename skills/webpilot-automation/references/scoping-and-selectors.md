# Hierarchical Scoping, Selectors & Container Isolation

Guide to target element resolution, container scoping grammar, and enterprise selector normalization in WebPilot.

---

## 1. Hierarchical Scoping & Container Isolation Grammar (`TargetDescriptorParser`)

WebPilot natively supports surgical, container-confined field resolution to eliminate collisions between identical field labels across different sections (e.g. `Degree` or `Company Name` appearing in multiple places):

### 1. Explicit Scope Prefix (`scope:` or `section:`):
```powershell
wp apply --fill "scope:Educational Background:Degree=Bachelors" `
         --fill "section:Employment History:Company Name=UNITED AMANA Contracting"
```

### 2. Playwright-Style Hierarchy Dividers (`>` or `>>`):
```powershell
wp apply --fill "Educational Background > Degree=Bachelors" `
         --fill "Employment History >> Company Name=UNITED AMANA Contracting"
```

### 3. Section Local ID Prefix (`@sec-N:`):
```powershell
wp apply --fill "@sec-7:Degree=Bachelors" `
         --fill "@sec-6:Company Name=UNITED AMANA Contracting"
```

### 4. Scoped Button Clicking (`Section >> Button`):
Confines button clicks to a specific section container (e.g. clicking "Add" inside Employment without triggering Add in Education):
```powershell
wp apply --press "Employment History >> Add"
```

### 5. Type Hints with Scope (`type:Section > Field`):
Forces the field interaction engine to use a specific widget adapter:
```powershell
wp apply --fill "picklist:Educational Background > Degree=Bachelors" `
         --fill "text:Employment History > Company Name=UNITED AMANA Contracting" `
         --fill "date:Employment History > From Date=01/06/2024"
```

Supported type hints:
- `text:` / `input:`: Standard text input
- `picklist:` / `select:` / `dropdown:`: Picklists or select elements
- `date:` / `datepicker:`: Date input with auto-formatting
- `checkbox:`: Checkbox toggle
- `radio:`: Radio button option
- `switch:`: ARIA switch toggle
- `file:` / `upload:`: File input

### 6. Nested JSON Data Payloads (`--data`):
Nested JSON structures are automatically parsed into scoped field descriptors:
```json
{
  "Employment History": {
    "Company Name": "UNITED AMANA Contracting",
    "Title": "Technical Office Engineer"
  },
  "Educational Background": {
    "Degree": "Bachelors",
    "University": "Omdurman Islamic University"
  }
}
```

---

## 2. Target Identifier Syntax

When targeting elements in `wp apply`, `wp find`, or `wp probe`, the target string can be:

| Target Syntax | Description | Example |
| :--- | :--- | :--- |
| **Local ID** | Ephemeral, token-efficient ID from `wp inspect` | `@fld-1`, `@btn-2`, `@sec-3`, `@drop-4` |
| **Field Label** | Exact or fuzzy matching on visible label text | `"Full Name"`, `"Country of Residence"` |
| **DOM Name / ID** | Exact HTML attribute `name` or `id` | `"applicant.email"`, `"63:_txtFld"` |
| **CSS Selector** | Direct CSS selector or with `css=` prefix | `css=input[type="email"]`, `#ssn-input` |
| **XPath Selector** | Direct XPath or with `xpath=` prefix | `xpath=//button[contains(., "Submit")]` |
| **Scoped Path** | Hierarchy with container divider | `"Educational Background > Degree"` |

---

## 3. Colon-ID Safe CSS Selector Normalization

Enterprise platforms (such as SAP SuccessFactors) frequently generate DOM IDs containing colons:
- Examples: `63:_txtFld`, `250:_datepicker`, `jobApp:subSection:degree`

In standard CSS, colons denote pseudo-classes (`:hover`, `:first-child`), causing standard `#63:_txtFld` queries to throw JavaScript DOMException syntax errors.

WebPilot automatically normalizes unescaped colon IDs in CSS selectors into safe attribute selectors:
- `#63:_txtFld` ➔ `[id="63:_txtFld"]`
- `#jobApp:subSection` ➔ `[id="jobApp:subSection"]`

This happens transparently in `wp apply`, `wp find`, `wp css`, and the Python SDK.

---

## 4. Automatic Private Use Area (PUA) Unicode Icon Stripping

Enterprise design systems (SAP Fiori, Oracle JET) often embed custom icon glyphs directly inside button or link text nodes using the Unicode Private Use Area (`\uE000` to `\uF8FF`).
- Example: `\uE1F6 Add` or `\uE03D Remove \uE03D`

WebPilot automatically strips all PUA Unicode characters during label extraction and element matching:
- The button is registered cleanly as `"Add"`.
- Agents can target `--press "Add"` or `--press "Remove"` with zero manual character escaping or regex hacks.

---

## 5. Relative DOM Hierarchy Traversal (`--up <N>`)

When diagnosing elements that are wrapped inside multiple shadow containers or custom card wrappers:
- `wp find @fld-1 --html --up 1`: Inspects immediate parent element HTML.
- `wp find @fld-1 --html --up 2`: Inspects 2 levels up (outer field row or card container).
- `wp find @fld-1 --html --up 3`: Inspects outer section fieldset.
