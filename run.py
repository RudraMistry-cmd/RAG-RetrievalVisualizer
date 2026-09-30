"""One-command dev launcher for the RAG Visualizer stack.

Starts the FastAPI backend (venv uvicorn) and the Vite frontend (npm run dev),
reusing either server if it is already running. Ctrl+C shuts both down.
Usage:
    python run.py            # normal
    python run.py --no-browser
"""
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"

BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://127.0.0.1:5173"
HEALTH_PATH = "/api/health"


def _venv_python():
    candidates = [
        BACKEND_DIR / "venv" / "Scripts" / "python.exe",
        BACKEND_DIR / "venv" / "bin" / "python",
    ]
    for cand in candidates:
        if cand.exists():
            return str(cand)
    raise SystemExit(
        "Backend venv not found. Run the README setup first "
        "(cd backend && py -3.11 -m venv venv && venv\\Scripts\\activate && pip install -r requirements.txt)."
    )


def _http_ok(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _wait(url, name, procs, timeout=90):
    print(f"waiting for {name} at {url} ...")
    start = time.time()
    while time.time() - start < timeout:
        if _http_ok(url):
            print(f"{name} is up: {url}")
            return True
        if procs and all(p.poll() is not None for p in procs):
            print(f"ERROR: {name} process exited before becoming ready", file=sys.stderr)
            return False
        time.sleep(1)
    print(f"WARNING: {name} did not respond within {timeout}s", file=sys.stderr)
    return False


def _spawn(cmd, cwd):
    try:
        return subprocess.Popen(cmd, cwd=str(cwd), shell=os.name == "nt")
    except FileNotFoundError:
        raise SystemExit(f"Could not start: {cmd[0]} not found on PATH.")


def main():
    no_browser = "--no-browser" in sys.argv
    procs = []

    if _http_ok(BACKEND_URL + HEALTH_PATH):
        print(f"backend already running: {BACKEND_URL}")
    else:
        print("starting backend (uvicorn) ...")
        procs.append(_spawn([_venv_python(), "-m", "uvicorn", "app.main:app", "--port", "8000"], BACKEND_DIR))

    if _http_ok(FRONTEND_URL):
        print(f"frontend already running: {FRONTEND_URL}")
    else:
        print("starting frontend (vite) ...")
        npm = "npm.cmd" if os.name == "nt" else "npm"
        procs.append(_spawn([npm, "run", "dev"], FRONTEND_DIR))

    up_backend = _wait(BACKEND_URL + HEALTH_PATH, "backend", procs)
    up_frontend = _wait(FRONTEND_URL, "frontend", procs)

    print()
    print("RAG Visualizer is ready:")
    print(f"  UI:        {FRONTEND_URL}")
    print(f"  API:       {BACKEND_URL}")
    print(f"  API docs:  {BACKEND_URL}/docs")

    if not no_browser and up_frontend:
        webbrowser.open(FRONTEND_URL)

    try:
        while True:
            for p in procs:
                code = p.poll()
                if code is not None:
                    print(f"WARNING: process exited with code {code}", file=sys.stderr)
            if any(p.poll() is not None for p in procs):
                raise SystemExit("A launched process exited unexpectedly.")
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nshutting down ...")
        for p in procs:
            p.terminate()
        time.sleep(1)
        for p in procs:
            p.kill()


if __name__ == "__main__":
    main()
