"""Automated PyInstaller Build Script for WebPilot Standalone Windows Binary.

Builds a self-contained webpilot.exe with all supervisor tiers, Playwright runtime,
and orchestration modules embedded.
"""

import os
import shutil
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def build_binary():
    print("═" * 70)
    print(" 🚀 WEBPILOT | STANDALONE WINDOWS BINARY COMPILER")
    print("═" * 70)

    # 1. Ensure output directories exist
    build_dir = os.path.join(PROJECT_ROOT, "build")
    dist_dir = os.path.join(PROJECT_ROOT, "dist")
    spec_file = os.path.join(PROJECT_ROOT, "webpilot.spec")

    print("[*] Target Output: dist/webpilot.exe")
    print(f"[*] Project Root : {PROJECT_ROOT}")

    # 2. Assemble PyInstaller arguments
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",  # fast loading, reliable child process spawning
        "--name=webpilot",
        f"--paths={PROJECT_ROOT}",
        "--hidden-import=playwright",
        "--hidden-import=playwright.sync_api",
        "--hidden-import=dotenv",
        "--hidden-import=adapters",
        "--hidden-import=common",
        "--hidden-import=config",
        "--hidden-import=constants",
        "--hidden-import=core",
        "--hidden-import=orchestration",
        "--hidden-import=services",
        "--hidden-import=supervisor",
        "--hidden-import=validators",
        "--hidden-import=supervisor.contracts",
        "--hidden-import=supervisor.client",
        "--hidden-import=supervisor.master_daemon",
        "--hidden-import=supervisor.worker_process",
        "--hidden-import=supervisor.shell",
        os.path.join(PROJECT_ROOT, "cli.py"),
    ]

    print("[*] Running PyInstaller command:")
    print("    " + " ".join(cmd))
    print("═" * 70)

    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print(f"[!] Build failed with exit code: {res.returncode}")
        sys.exit(res.returncode)

    print("\n[✓] PyInstaller build completed successfully!")
    print(f"[✓] Artifact created at: {os.path.join(dist_dir, 'webpilot')}")


if __name__ == "__main__":
    build_binary()
