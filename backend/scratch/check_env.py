"""Quick health check for the VoxDoc dev environment.

Run from anywhere with the venv active:
    python backend/scratch/check_env.py
"""
import subprocess
import sys
from pathlib import Path

ok = True


def report(label, passed, detail):
    global ok
    ok = ok and passed
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}")


report("Python 3.11", sys.version_info[:2] == (3, 11), sys.version.split()[0])

in_venv = sys.prefix != sys.base_prefix
report("Inside a venv", in_venv, sys.prefix)

exe = Path(sys.executable)
report("Using voxdoc venv", exe.parts[-4:-2] == ("backend", ".venv"), exe)

repo = Path(__file__).resolve().parents[2]
status = subprocess.run(
    ["git", "status", "--porcelain", "--untracked-files=all"],
    cwd=repo, capture_output=True, text=True,
).stdout
report(".venv ignored by git", ".venv" not in status, "not listed" if ".venv" not in status else "LISTED - check .gitignore")

print("\nAll good!" if ok else "\nSomething is off - see FAIL lines above.")
sys.exit(0 if ok else 1)
