# WebPilot Adversarial Verification Report: Claimed Fixes FX1 to FX7

**Audit Target:** WebPilot (`webpilot-engine`)  
**Commits:** `b2046a1e6819269484e0cbe5553943be872b0533` (v2.0.7 / PyPI latest) and `9799854cbef104dc369437df2cf2891da0f443ad` (v2.0.8 / `origin/master`, unreleased on PyPI)  
**PyPI Release:** `webpilot-engine==2.0.7` (Uploaded 2026-10-09T03:12:59Z)  
**Audit Environment:** Oracle Linux Server 9.8 (aarch64), Python 3.11.13, Chromium 153.0.8010.12  
**Auditor Role:** Independent QA Engineer & Offensive Security Auditor  

> **Correction banner.** Two statements from the first draft were wrong and are corrected inline below: (1) **N1 is conditional** — the auto-spawn path passes the token via `WEBPILOT_SUPERVISOR_TOKEN` in the child environment, and a second local user cannot read the daemon/worker `environ` or the token file; only the explicit `--token` / `--run-daemon <port> <token>` path exposes it in `argv`. (2) **N3 drops the connection** (`RemoteDisconnected`); it does **not** return HTTP 500. In addition, **N8/N10/N11 are fixed in v2.0.8** (`worker_process.py:376` honesty contract, `:263,297` redaction) — see the addendum in §3.

---

## 1. Executive Summary of Part A Claims

The project maintainer claimed that all previous defects FX1 through FX7 had been completely resolved in releases v2.0.5 through v2.0.7. Each claim was subjected to adversarial penetration testing and strict code verification:

| Claim ID | Claimed Fix Description | Verdict | Primary Technical Cause & Evidence |
|:---|:---|:---|:---|
| **FX1** | Master Supervisor on `127.0.0.1:9333` protected by high-entropy token authentication | **FIX INTRODUCED NEW DEFECT** | Token auth implemented, but **N1** exposes token in plaintext via CLI `argv` (`ps -ef`), **N3** crashes on non-ASCII headers (`TypeError`), and **N5** causes zombie daemon port deadlocks. |
| **FX2** | Secrets hygiene: passwords supplied via `@env:`, `@stdin`, `@file:` never leak into shell history/`ps` | **FIX INTRODUCED NEW DEFECT** | Input parsing protects shell history, but **N10** worker prints clear-text passwords in telemetry lines `[✓] Set & Verified '{key}' -> '{val}'`, leaking secrets directly into stdout and AI Agent MCP context! |
| **FX3** | Cross-platform `ProcessManager` abstraction replacing Windows-first WMI and `taskkill` calls | **PARTIALLY FIXED** | `common/process_manager.py` created, but `adapters/live_session_manager.py:209,248` still has raw `taskkill` calls, and POSIX path calls `os.kill(pid, 9)` which orphans Chromium child processes. |
| **FX4** | Docs aligned with Strategies A-D; modal backdrop/DOM surgical removal deleted; Mock CI added | **VERIFIED (With Caveats)** | Stages 3 & 4 removed from documentation. Mock CI suite exists in `test_enterprise_integration.py`, but mock HTML is synthetic and does not prove real-world SAP/Workday compatibility. |
| **FX5** | Centralized `_spawn_worker` with `start_new_session=True` on POSIX for clean restarts | **VERIFIED** | Centralized in `supervisor/master_daemon.py:91`, applies `start_new_session=True` across initial spawn and restart. |
| **FX6** | Post-set DOM verification (`verify_field_value`) eliminating silent false success | **FIX INTRODUCED NEW DEFECT** | Verification wired in, but **N8** hardcodes `success=True` regardless of unconfirmed fields, **N9** click fallback flips toggles/radios, and **N11** immediate readback fails on silent reverts (S44). |
| **FX7** | Explicit `--token` CLI argument and cascading token resolution | **VERIFIED (Security Warning)** | Precedence (CLI > ENV > File) works correctly, but CLI flag directly enables **N1** local privilege escalation. |

---

## 2. In-Depth Adversarial Analysis by Claim

### FX1 & FX7: Token Authentication & Local Access Boundary

#### The Claim
`MasterSupervisor` generates a 256-bit hexadecimal token via `secrets.token_hex(32)`, stores it at `~/.webpilot/supervisor.token` with mode `0600`, requires `X-Supervisor-Token` or `Authorization: Bearer <token>` on all HTTP endpoints, compares tokens using `secrets.compare_digest`, and supports a `--token` CLI flag.

#### Adversarial Execution & Findings

1. **Hypothesis N1: Local Token Exposure via Process Arguments [EXECUTED - CRITICAL]**
   - **Mechanism:** When a daemon is started via `python -m supervisor.master_daemon 9335 <token>` or when a user/agent invokes `wp apply --token <token>`, the authentication secret is placed into `sys.argv`.
   - **Exploit Verification:** On standard Linux installations without `hidepid` mounted on `/proc`, any local unprivileged OS user can read command-line arguments.
   - **Test Execution:** A test daemon was started by user `abdulkarim` with token `canary-super-secret-token-abcdef1234567890`. An unprivileged probe user (`webpilot_probe`, UID 1003) executed `ps -ef`.
   - **Result:** The full canary token was clearly visible in `ps -ef` output to UID 1003. User `webpilot_probe` then issued:
     ```bash
     curl -s -H "X-Supervisor-Token: canary-super-secret-token-abcdef1234567890" http://127.0.0.1:9335/status
     ```
     The unprivileged user received HTTP 200 and full daemon telemetry, completely bypassing the local security boundary.
   - **Scope correction [EXECUTED]:** This exploit requires the daemon to be started with an **explicit** token argument. The default auto-spawn path (`SupervisorClient`) passes the token via the **environment** (`WEBPILOT_SUPERVISOR_TOKEN`, `client.py:134`); the T14 probe confirmed a second local user cannot read the daemon/worker `environ` nor `~/.webpilot/supervisor.token` (`Permission denied`), and the auto-spawned daemon's `cmdline` contains **no** token. The finding is real but **conditional**, hence WP-001 is High, not Critical.
   - **Code Reference:** `supervisor/master_daemon.py:328-330,379-380` and `cli.py:278-279,297`.

2. **Hypothesis N3: Unhandled TypeError on Non-ASCII Header Input [EXECUTED - HIGH]**
   - **Mechanism:** `supervisor/security.py:109` executes:
     ```python
     return secrets.compare_digest(clean_token, expected_token)
     ```
   - **Exploit Verification:** In Python's standard library, `hmac.compare_digest` / `secrets.compare_digest` raises `TypeError: comparing strings with non-ASCII characters is not supported` if either string contains non-ASCII codepoints.
   - **Test Execution:** An HTTP request with `X-Supervisor-Token: token\u1234` was dispatched to the supervisor HTTP handler.
   - **Result (corrected):** In `supervisor/master_daemon.py:248`, `_authenticate()` does not catch the error. The handler raises **before writing any response**, so the client receives `RemoteDisconnected('Remote end closed connection without response')` — **the connection is dropped, not answered with HTTP 500**. A wrong **ASCII** token returns a clean 401 JSON. The daemon survives. [EXECUTED]
   - **Code Reference:** `supervisor/security.py:109`, `supervisor/master_daemon.py:248`.

3. **Hypothesis N5: Zombie Daemon Port Lockout on Token File Deletion [EXECUTED - HIGH]**
   - **Mechanism:** In `supervisor/master_daemon.py:322`, `remove_supervisor_token()` deletes `~/.webpilot/supervisor.token` on daemon shutdown. However, if the daemon crashes, hangs, or if a test runner deletes the token file while the daemon process remains alive, the daemon continues listening on port 9333.
   - **Result:** Subsequent CLI invocations find no token file, send unauthenticated requests, receive 401, fail to load a token, assume the supervisor is down, and attempt to spawn a new supervisor. The new process fails with `OSError: [Errno 98] Address already in use`. All future WebPilot commands hang or fail with:
     ```text
     RuntimeError: Failed to auto-spawn Master Supervisor on http://127.0.0.1:9333.
     ```
   - **Code Reference:** `supervisor/client.py:97-105`, `supervisor/master_daemon.py:310,322`.

4. **Hypothesis N2: Directory Traversal Permissions [EXECUTED - LOW]**
   - **Mechanism:** While `~/.webpilot/supervisor.token` is created with mode `0600` via `os.open(..., 0o600)`, the parent directory `~/.webpilot/` is created via `os.makedirs(token_dir, exist_ok=True)` without explicit permissions, defaulting to umask `0755` (`rwxr-xr-x`). Local users can enumerate directory metadata.

---

### FX2: Secrets Hygiene & Plaintext Emission

#### The Claim
Field inputs starting with `@env:`, `@stdin`, or `@file:` resolve secrets dynamically at runtime, preventing clear-text passwords from appearing in shell history or process arguments.

#### Adversarial Execution & Findings

1. **Hypothesis N10: Verification Telemetry Leaks Secrets in Plaintext [EXECUTED - CRITICAL]**
   - **Mechanism:** While `common/secrets.py` hides secrets from CLI `sys.argv`, the post-set verification logging in `supervisor/worker_process.py:273,276,279` logs the resolved secret value `val`:
     ```python
     if verified:
         confirmed.append((key, val))
         lines.append(f"  [✓] Set & Verified '{key}' -> '{val}'")
     else:
         unconfirmed.append((key, val))
         lines.append(f"  [?] Set but unconfirmed '{key}' -> '{val}'")
     ```
   - **Impact on AI Agents:** These `lines` are returned in `SupervisorActionResponse.output_lines` and printed directly to `stdout` by `cli.py:104`, logged to `master_daemon.log`, and returned inside the text block of the FastMCP tool response (`mcp_server.py:183`).
   - **Exploit Verification:** Passing `--fill "password=@env:ERP_PASS"` results in WebPilot printing:
     ```text
     [✓] Set & Verified 'password' -> 'SuperSecretP@ssw0rd!'
     ```
     The resolved secret is injected directly into the LLM agent's conversational context window and stored in log files.
   - **Code Reference:** `supervisor/worker_process.py:273,276,279`.

2. **Hypothesis N14: Error Handling for Unset Environment Variables and Missing Files [EXECUTED - VERIFIED]**
   - When an unresolvable environment variable is supplied (`@env:MISSING_VAR`), `common/secrets.py:35` correctly raises `ConfigurationError("Referenced environment variable 'MISSING_VAR' is not set")`.
   - When a missing file is supplied (`@file:/missing.txt`), `common/secrets.py:46` correctly raises `ConfigurationError("Referenced secret file not found")`.
   - Literal escaping (`@@env:LITERAL`) returns `@@env:LITERAL`.

---

### FX3: ProcessManager Abstraction & Orphaned Process Leaks

#### The Claim
`common/process_manager.py` abstracts process lifecycle via `BaseProcessManager`, `PosixProcessManager` (using `setsid`, `os.killpg(pgid, signal.SIGKILL)`, and `pgrep -P`), and `WindowsProcessManager` (using WMI and `taskkill`). No stray WMI/taskkill calls remain.

#### Adversarial Execution & Findings

1. **Stray WMI/Taskkill Audit [CODE - HIGH]**
   - Scanning the entire codebase revealed that `adapters/live_session_manager.py:209` and `adapters/live_session_manager.py:248` still contain hardcoded Windows `taskkill` calls:
     ```python
     subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc_pid)], ...)
     ```
   - This bypasses `ProcessManager` entirely.

2. **POSIX Chromium Process Orphan Leak [EXECUTED - MEDIUM]**
   - In `adapters/live_session_manager.py:214` and line `253`:
     ```python
     else:
         os.kill(browser_pid, 9)
     ```
   - Calling `os.kill(browser_pid, 9)` on POSIX kills only the root browser process PID. Chromium's child processes (zygote, GPU process, network service, and renderers) are not killed and become orphaned zombie processes running under init (`PID 1`).

---

### FX4: Documentation & Enterprise Mocks

#### The Claim
Stages 3 & 4 (backdrop click and surgical DOM removal) were completely removed from docs and replaced with Strategies A-D matching `reactive_interaction_service.py`. A SAP & Workday Mock CI suite was added.

#### Adversarial Execution & Findings

1. **Documentation Text Search [EXECUTED - VERIFIED]**
   - Verified that `README.md`, `ARCHITECTURE.md`, and `CHANGELOG.md` no longer contain any references to backdrop-click or surgical DOM removal stages. Strategies A through D are accurately documented.

2. **Enterprise Mock Suite Evaluation [CODE - MEDIUM]**
   - The test file `tests/test_enterprise_integration.py` and fixture `tests/fixtures/enterprise_portal.html` test synthetic picklists and modal overlays.
   - However, the mock HTML was authored from internal assumptions rather than authentic vendor shadow DOM / iframe hierarchies. Passing this suite does not constitute evidence of real-world SAP SuccessFactors or Workday compatibility.

---

### FX5: Centralized Worker Spawning

#### The Claim
Worker launch is centralized in `MasterSupervisor._spawn_worker`, applying `start_new_session=True` on POSIX, used by both `_ensure_worker` and `restart_worker`.

#### Adversarial Execution & Findings

1. **Code Audit [CODE - VERIFIED]**
   - Verified that `_spawn_worker` at `supervisor/master_daemon.py:91-115` encapsulates all worker `Popen` logic, including passing `start_new_session=True` on POSIX. Both `_ensure_worker` (line 121) and `restart_worker` (line 187) invoke `self._spawn_worker()`.

---

### FX6: Post-Set Verification (`verify_field_value`)

#### The Claim
`field_svc.verify_field_value(key, val)` confirms DOM state after each write, separates results into `confirmed_fields` and `unconfirmed_fields`, and eliminates false success.

#### Adversarial Execution & Findings

1. **Hypothesis N8: False Success Lie in Status Responses [EXECUTED - CRITICAL]**
   - **Mechanism:** In `supervisor/worker_process.py:353`:
     ```python
     return SupervisorActionResponse(
         success=True,
         action="apply",
         ...
         confirmed_fields=confirmed,
         unconfirmed_fields=unconfirmed,
         failed_fields=failed,
     )
     ```
   - **Result:** `success=True` is **hardcoded**. Even if every single field is in `unconfirmed` or `failed`, the response object reports `success=True`.
   - In `cli.py:212`, the CLI checks `if not resp.success: sys.exit(1)`. Because `success` is `True`, the CLI **exits with code 0** (success)!
   - In `mcp_server.py:138-144`, `webpilot_fill_form` returns:
     ```json
     {
       "success": true,
       "confirmed_fields": [],
       "failed_fields": []
     }
     ```
     **`unconfirmed_fields` is completely omitted from the dictionary returned to the AI agent!** The calling LLM agent sees `success: true` and concludes the action succeeded, completely unaware that the form was not filled.

2. **Hypothesis N9: Destructive / Toggling Click Fallback [CODE & EXECUTED - HIGH]**
   - **Mechanism:** In `supervisor/worker_process.py:268`:
     ```python
     if not verified:
         field_svc._playwright_click_fallback(key, val)
         verified = field_svc.verify_field_value(key, val)
     ```
   - If a checkbox or toggle was set, but verification failed due to async delay, calling `_playwright_click_fallback` clicks the control again, **unchecking/flipping the user's correct input**!

3. **Hypothesis N11: Verification Timing & Silent Reverts (Scenario S44) [EXECUTED - CRITICAL]**
   - `verify_field_value` reads the DOM immediately at `t = 0 ms`.
   - On Scenario S44 (where an async script reverts the field at `t = 200 ms`), WebPilot verified the field at `t = 0 ms`, recorded `[✓] Set & Verified 'first_name' -> 'Alice'`, and clicked submit at `t = 1000 ms`.
   - The form was submitted with the field completely empty, while WebPilot reported 100% success.
   - **False Confirm Count: 1 | False Success: TRUE.**
---

## 3. Addendum: Re-verification Against v2.0.8 (`9799854`)

v2.0.8 was released to `origin/master` during this audit and **is not on PyPI** (latest published remains 2.0.7). Re-running the fixes adversarially against `venv_master` (editable @ `9799854`):

| Finding | v2.0.7 | v2.0.8 | Evidence |
|:--|:--|:--|:--|
| **N8** hardcoded `success` | BROKEN | **FIXED** — `overall_success = (len(failed)==0 and len(unconfirmed)==0)` at `worker_process.py:376` | `[CODE]` + benchmark: reported-success 98%→82% |
| **N8b** MCP omits `unconfirmed_fields` | BROKEN | **FIXED** — now emitted at `mcp_server.py:142` | `[CODE]` |
| **N10** plaintext secret in telemetry | BROKEN | **FIXED** — `***REDACTED***` for sensitive keys, `worker_process.py:263,297`; `common/logging.py:redact_sensitive` | `[CODE]` |
| **N11** silent revert (S44) | BROKEN | **PARTIAL** — pre-submit barrier `worker_process.py:292-298` + `settle_delay_ms`; false-unconfirms 63→24 | benchmark |
| **N1** token in argv | conditional | conditional (env-first, argv fallback retained at `master_daemon.py:379`) | `[CODE]` |
| **N3** non-ASCII header | dropped connection | **UNCHANGED** (connection dropped) | `[EXECUTED]` |
| **N5 / WP-016** token-desync self-DoS | present | **UNCHANGED and worse** — reaps 3→27 in the clean 3×150 run | `[EXECUTED]` |

**Field-level correctness did not improve for false-confirms** (30 field-writes falsely confirmed in both versions); only false-unconfirms and the reporting channel improved. See `FALSE_SUCCESS_ANATOMY.md` §5.
