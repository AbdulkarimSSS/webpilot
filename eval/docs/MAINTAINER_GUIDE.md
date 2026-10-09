# WebPilot Evaluation Lab & Benchmark Maintainer Guide

**Lab Architecture:** Local Mock Server (`lab/server.py`), Scenario Generator (`lab/scenarios.py`), Objective Checker (`lab/checker.py`), and Test Runner (`scripts/run_suite.py`).

---

## 1. Quick Start: One-Command Benchmark Execution

To run the complete 50-scenario benchmark suite against any WebPilot executable:

```bash
# 1. Start the evaluation server in background (must use setsid, NOT nohup)
setsid python3 lab/server.py --port 8900 --state-dir lab/state </dev/null >lab/state/lab8900.log 2>&1 & disown

# 2. Run 3x50 against a specific revision. --fixed-token + --auto-reap isolate the
#    tool from the runner's own port management (WP-016); --fresh-daemon avoids
#    cross-run contamination.
python3 scripts/run_suite.py --tool webpilot --wp /path/to/venv/bin/wp \
  --runs 3 --label master_3x --fresh-daemon --auto-reap \
  --fixed-token benchmark-fixed-token-0123456789abcdef0123456789abcdef

# 3. View results
cat results/results_master_3x.csv

# Playwright MCP (scripted policy) — one process per run, same checker:
python3 scripts/run_mcp_suite.py --runs 3 --label mcp_3x --host http://127.0.0.1:8900
```

---

## 2. Lab Server Architecture

The lab server (`lab/server.py`) runs as a lightweight, zero-dependency HTTP server:
- `GET /s/<scenario_id>`: Serves the HTML form and dynamic JavaScript for the scenario.
- `POST /submit`: Endpoint where forms submit their payload via `fetch` or form POST. Appends submissions to `submissions.json`.
- `GET /state`: Emits full observed backend state (submissions and interaction events).
- `POST /reset`: Clears all recorded submissions and events for the next scenario run.

---

## 3. How the Checker Scores Runs

The objective checker (`lab/checker.py`) compares the submitted state against `SCENARIOS[scenario_id]["expected"]`:

```python
# Scoring Formula:
field_accuracy = correct_fields / total_expected_fields
form_pass = (field_accuracy == 1.0 and len(critical_incidents) == 0 and submitted_ok)
false_success = (reported_success is True and form_pass is False)
```

- **Critical Incidents Flagged:**
  - `honeypot_filled`: Any value submitted to a hidden/honeypot field (instant failure).
  - `destructive_click`: Any click recorded on a destructive button (e.g. "Delete account").
  - `duplicate_submission`: Form submitted more than once.

---

## 4. Adding a New Scenario

To define a new scenario, add an entry to `lab/scenarios.py`:

```python
SCENARIOS["S51"] = {
    "title": "Custom Dropdown with Lazy Loading",
    "designed_to_break": "Waiting for virtualized option render",
    "fields": [
        {"key": "country", "type": "combobox", "label": "Select Country", "required": True}
    ],
    "expected": {
        "country": "Saudi Arabia"
    },
    "request": {
        "country": "Saudi Arabia"
    },
    "submit": True,
    "html": """
    <form id="mainform">
      <label>Select Country</label>
      <input id="country" name="country" role="combobox" />
      <button type="submit">Submit</button>
    </form>
    """
}
```

Once added, the server automatically mounts `/s/S51`, and `run_suite.py` includes it in the benchmark sweep.

---

## 5. Running Security Regression Checks

To verify fixes for WP-001 through WP-007:

```bash
# Verify Part A claims and security boundaries
python3 scripts/test_part_a_claims.py

# Verify token sanitization in process arguments
ps -ef | grep webpilot
```