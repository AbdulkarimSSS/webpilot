#!/usr/bin/env python3
import subprocess, sys, time, os, json

cmd = [
    "/home/abdulkarim/webpilot_eval/install_matrix/venv_master/bin/python3",
    "/home/abdulkarim/webpilot_eval/scripts/run_suite.py",
    "--tool", "webpilot",
    "--wp", "/home/abdulkarim/webpilot_eval/install_matrix/venv_master/bin/wp",
    "--runs", "1",
    "--label", "v209_clean",
    "--out-dir", "/home/abdulkarim/webpilot_eval/results/v209_clean"
]

status_file = "/home/abdulkarim/webpilot_eval/results/v209_clean_status.txt"
os.makedirs("/home/abdulkarim/webpilot_eval/results", exist_ok=True)

total_scenarios = 50
completed = 0
start_time = time.time()

print(f"[WATCHDOG] Launching clean benchmark suite: {total_scenarios} scenarios...")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

for line in iter(proc.stdout.readline, ''):
    line_clean = line.strip()
    if not line_clean:
        continue
    if line_clean.startswith("[webpilot] run1"):
        completed += 1
        elapsed = time.time() - start_time
        pct = (completed / total_scenarios) * 100.0
        rate = completed / elapsed if elapsed > 0 else 0
        rem = (total_scenarios - completed) / rate if rate > 0 else 0
        elapsed_str = f"{int(elapsed//60):02d}:{int(elapsed%60):02d}"
        eta_str = f"{int(rem//60):02d}:{int(rem%60):02d}"
        
        status_line = f"[{completed:02d}/{total_scenarios:02d} ({pct:5.1f}%)] Elapsed: {elapsed_str} | ETA: {eta_str} | {line_clean}"
        print(status_line, flush=True)
        try:
            with open(status_file, "w") as f:
                f.write(status_line + "\n")
        except Exception:
            pass
    elif "wrote" in line_clean:
        print(f"[FINAL] {line_clean}", flush=True)

proc.stdout.close()
return_code = proc.wait()
total_time = time.time() - start_time
print(f"[WATCHDOG] Finished with exit code {return_code} in {total_time:.1f}s")
sys.exit(return_code)
