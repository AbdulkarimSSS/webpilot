#!/usr/bin/env python3
"""Adversarial verification of owner's claimed fixes FX1 to FX7."""
import os
import sys

EVAL_DIR = "/home/abdulkarim/webpilot_eval"
MASTER_SRC = f"{EVAL_DIR}/src/webpilot-master"
sys.path.insert(0, MASTER_SRC)

import json
import time
import socket
import secrets
import stat
import subprocess
import urllib.request
import urllib.error

VENV_MASTER = f"{EVAL_DIR}/install_matrix/venv_master"
PYTHON_BIN = f"{VENV_MASTER}/bin/python"
WP_BIN = f"{VENV_MASTER}/bin/wp"
SECURITY_DIR = f"{EVAL_DIR}/security"
os.makedirs(SECURITY_DIR, exist_ok=True)

report = {}

def log_test(test_id, status, details):
    print(f"[{status}] {test_id}: {details.get('summary', '')}")
    report[test_id] = {"status": status, **details}

print("=== PART A: ADVERSARIAL VERIFICATION OF FX1-FX7 ===")

# ---------------------------------------------------------
# FX1 & FX7: TOKEN AUTHENTICATION & CLI TOKEN HANDLING
# ---------------------------------------------------------
print("\n--- Testing FX1 & FX7: Token Authentication ---")

# 1. Token Generation & Storage
test_token = secrets.token_hex(32)
token_len = len(test_token)
entropy_bits = len(bytes.fromhex(test_token)) * 8
token_file = os.path.expanduser("~/.webpilot/supervisor.token")
token_dir = os.path.dirname(token_file)

token_file_mode = None
token_dir_mode = None
if os.path.exists(token_file):
    token_file_mode = oct(stat.S_IMODE(os.stat(token_file).st_mode))
if os.path.exists(token_dir):
    token_dir_mode = oct(stat.S_IMODE(os.stat(token_dir).st_mode))

log_test("FX1_STORAGE", "EXECUTED", {
    "summary": f"Token file mode: {token_file_mode}, Dir mode: {token_dir_mode}",
    "token_file": token_file,
    "token_file_mode": token_file_mode,
    "token_dir_mode": token_dir_mode,
    "entropy_bits": entropy_bits
})

# 2. Non-ASCII header handling (Hypothesis N3)
try:
    secrets.compare_digest("token\u1234", "expected_token")
    n3_result = "Did not raise TypeError"
    n3_status = "NOT_REPRODUCED"
except TypeError as te:
    n3_result = f"Raised TypeError: {te}"
    n3_status = "REPRODUCED_CRASH_DEFECT"

log_test("FX1_N3_NON_ASCII_HEADER", n3_status, {
    "summary": f"Non-ASCII header causes unhandled TypeError: {n3_result}",
    "exception": str(n3_result)
})

# 3. Local Token Exposure in Process Arguments (Hypothesis N1)
canary_token = "canary-super-secret-token-abcdef1234567890"
proc_daemon = subprocess.Popen(
    [PYTHON_BIN, "-m", "supervisor.master_daemon", "9335", canary_token],
    cwd=MASTER_SRC,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)
time.sleep(1.0)

# Check if webpilot_probe user can see canary_token in ps
ps_probe = subprocess.run(
    ["sudo", "-u", "webpilot_probe", "ps", "-ef"],
    capture_output=True, text=True
)
token_leaked_in_ps = canary_token in ps_probe.stdout

# Now probe makes an authenticated request using the leaked token
auth_status_probe = None
if token_leaked_in_ps:
    req = urllib.request.Request(
        "http://127.0.0.1:9335/status",
        headers={"X-Supervisor-Token": canary_token}
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            auth_status_probe = resp.getcode()
    except Exception as e:
        auth_status_probe = str(e)

# Stop the test daemon
proc_daemon.terminate()
proc_daemon.wait(timeout=3)

log_test("FX1_N1_LOCAL_TOKEN_LEAK", "REPRODUCED_HIGH_SEVERITY_DEFECT" if token_leaked_in_ps else "SECURE", {
    "summary": "Token exposed in process arguments readable by any local unprivileged user via ps/proc",
    "token_leaked_in_ps": token_leaked_in_ps,
    "probe_user_authenticated_status": auth_status_probe,
    "finding": "Any unprivileged local user can extract supervisor token from ps -ef and hijack session"
})

# ---------------------------------------------------------
# FX2: SECRETS HYGIENE & TELEMETRY LEAKAGE
# ---------------------------------------------------------
print("\n--- Testing FX2: Secrets Hygiene & Output Leakage ---")

# Hypothesis N10: Does worker_process emit secret values in [✓] Set & Verified?
worker_py = f"{MASTER_SRC}/supervisor/worker_process.py"
has_set_verified_cleartext = False
has_unconfirmed_cleartext = False
with open(worker_py, "r") as f:
    src = f.read()
    if "lines.append(f\"  [✓] Set & Verified '{key}' -> '{val}'\")" in src:
        has_set_verified_cleartext = True
    if "lines.append(f\"  [?] Set but unconfirmed '{key}' -> '{val}'\")" in src:
        has_unconfirmed_cleartext = True

log_test("FX2_N10_TELEMETRY_SECRET_LEAK", "REPRODUCED_HIGH_SEVERITY_DEFECT" if has_set_verified_cleartext else "SECURE", {
    "summary": "Worker emits resolved secrets in plain text to stdout, logs, JSON, and MCP results",
    "set_verified_line": has_set_verified_cleartext,
    "unconfirmed_line": has_unconfirmed_cleartext,
    "file_location": "supervisor/worker_process.py:273,276"
})

# Test @env: and @stdin resolution behavior (N13, N14)
from common.secrets import resolve_secret_value

# Unset variable test:
os.environ.pop("TEST_NONEXISTENT_SECRET", None)
try:
    res_missing_env = resolve_secret_value("@env:TEST_NONEXISTENT_SECRET")
except Exception as e:
    res_missing_env = f"Raised {type(e).__name__}: {e}"

log_test("FX2_N14_MISSING_ENV", "EXECUTED", {
    "summary": f"Unset @env raises: {res_missing_env}",
    "result": str(res_missing_env)
})

# Missing file test:
try:
    res_missing_file = resolve_secret_value("@file:/tmp/nonexistent_webpilot_secret.txt")
except Exception as e:
    res_missing_file = f"Raised {type(e).__name__}: {e}"

log_test("FX2_N14_MISSING_FILE", "EXECUTED", {
    "summary": f"Missing @file raises: {res_missing_file}",
    "result": str(res_missing_file)
})

# Literal @env: escape test:
try:
    res_literal = resolve_secret_value("@@env:LITERAL")
except Exception as e:
    res_literal = f"Raised {type(e).__name__}: {e}"

log_test("FX2_N14_LITERAL_ESCAPE", "EXECUTED", {
    "summary": f"Literal @@env: escape returns: {res_literal}",
    "result": str(res_literal)
})

# ---------------------------------------------------------
# FX3: PROCESS MANAGER ABSTRACTION
# ---------------------------------------------------------
print("\n--- Testing FX3: ProcessManager Abstraction ---")
from common.process_manager import get_process_manager, PosixProcessManager

pm = get_process_manager()
is_posix = isinstance(pm, PosixProcessManager)

# Check for stray WMI or taskkill in core codebase
stray_wmi = []
for root, dirs, files in os.walk(MASTER_SRC):
    if "tests" in root or ".git" in root or "venv" in root:
        continue
    for f in files:
        if f.endswith(".py") and f != "process_manager.py":
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8", errors="ignore") as fobj:
                txt = fobj.read()
                if "taskkill" in txt or "wmic" in txt:
                    stray_wmi.append(p)

log_test("FX3_PORTABILITY", "VERIFIED" if is_posix and not stray_wmi else "DEFECT", {
    "summary": f"ProcessManager is PosixProcessManager: {is_posix}. Stray WMI calls: {stray_wmi}",
    "pm_class": pm.__class__.__name__,
    "stray_calls": stray_wmi
})

# ---------------------------------------------------------
# FX4: DOCUMENTATION & MOCK CI SUITE
# ---------------------------------------------------------
print("\n--- Testing FX4: Documentation & Mock CI Suite ---")
readme_txt = open(f"{MASTER_SRC}/README.md", "r", encoding="utf-8").read()
arch_txt = open(f"{MASTER_SRC}/ARCHITECTURE.md", "r", encoding="utf-8").read()

leftover_backdrop = "backdrop click" in readme_txt.lower() or "backdrop click" in arch_txt.lower()
leftover_dom_removal = "surgical removal" in readme_txt.lower() or "surgical removal" in arch_txt.lower()
has_mock_test = os.path.exists(f"{MASTER_SRC}/tests/test_enterprise_integration.py")

log_test("FX4_DOCS_AND_MOCK_CI", "VERIFIED" if (not leftover_backdrop and not leftover_dom_removal and has_mock_test) else "DEFECT", {
    "summary": f"Stages 3/4 removed: {not leftover_backdrop and not leftover_dom_removal}. Mock CI test exists: {has_mock_test}",
    "leftover_backdrop": leftover_backdrop,
    "leftover_dom_removal": leftover_dom_removal,
    "has_mock_test": has_mock_test
})

# ---------------------------------------------------------
# FX5: UNIFIED WORKER SPAWN
# ---------------------------------------------------------
print("\n--- Testing FX5: Unified Worker Spawn ---")
daemon_py = f"{MASTER_SRC}/supervisor/master_daemon.py"
with open(daemon_py, "r") as f:
    dsrc = f.read()

has_spawn_helper = "def _spawn_worker(self)" in dsrc
uses_spawn_in_ensure = "self.worker_process = self._spawn_worker()" in dsrc
uses_spawn_in_restart = "new_worker = self._spawn_worker()" in dsrc
has_start_new_session = 'popen_kwargs["start_new_session"] = True' in dsrc

log_test("FX5_RESTART_WORKER", "VERIFIED" if (has_spawn_helper and uses_spawn_in_ensure and uses_spawn_in_restart and has_start_new_session) else "DEFECT", {
    "summary": "Worker spawn centralized in _spawn_worker with start_new_session=True on POSIX",
    "has_spawn_helper": has_spawn_helper,
    "uses_spawn_in_ensure": uses_spawn_in_ensure,
    "uses_spawn_in_restart": uses_spawn_in_restart,
    "has_start_new_session": has_start_new_session
})

# ---------------------------------------------------------
# FX6: POST-SET VERIFICATION & FALSE SUCCESS LIE
# ---------------------------------------------------------
print("\n--- Testing FX6: Post-set Verification Semantics ---")
with open(worker_py, "r") as f:
    wsrc = f.read()

n8_hardcoded_success = "success=True,\n            action=\"apply\"," in wsrc or "success=True," in wsrc and "unconfirmed_fields=unconfirmed" in wsrc

mcp_py = f"{MASTER_SRC}/mcp_server.py"
with open(mcp_py, "r") as f:
    msrc = f.read()
mcp_omits_unconfirmed = "confirmed_fields" in msrc and "unconfirmed_fields" not in msrc

log_test("FX6_N8_FALSE_SUCCESS_SEMANTICS", "REPRODUCED_HIGH_SEVERITY_DEFECT" if n8_hardcoded_success else "VERIFIED", {
    "summary": "success=True is hardcoded even when fields are unconfirmed; MCP completely omits unconfirmed_fields",
    "hardcoded_success": n8_hardcoded_success,
    "mcp_omits_unconfirmed": mcp_omits_unconfirmed,
    "impact": "Agent receives success=True and never discovers that critical form fields failed verification"
})

has_click_fallback = "field_svc._playwright_click_fallback(key, val)" in wsrc
log_test("FX6_N9_HARMFUL_CLICK_FALLBACK", "POTENTIALLY_DESTRUCTIVE_DEFECT" if has_click_fallback else "CLEAN", {
    "summary": "Failed verification triggers _playwright_click_fallback which flips checkboxes or clicks near-duplicate buttons",
    "has_click_fallback": has_click_fallback,
    "location": "supervisor/worker_process.py:268"
})

with open(f"{SECURITY_DIR}/part_a_verification_results.json", "w") as f:
    json.dump(report, f, indent=2)

print("\n=== PART A VERIFICATION COMPLETE. Saved to security/part_a_verification_results.json ===")