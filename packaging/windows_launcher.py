from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8000


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def wait_for_server(timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((HOST, PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    root = app_root()
    os.chdir(root)
    env = os.environ.copy()
    env.setdefault("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", "1")
    env.setdefault("AD_SCRAPER_MONITOR_POLL_SECONDS", "60")
    env.setdefault("AD_SCRAPER_DATA_ROOT", str(root / "data"))

    command = [sys.executable, "-m", "uvicorn", "app.main:app", "--app-dir", str(root / "backend"), "--host", HOST, "--port", str(PORT)]
    process = subprocess.Popen(command, cwd=root, env=env)
    try:
        if not wait_for_server():
            process.terminate()
            return 1
        webbrowser.open(f"http://{HOST}:{PORT}/")
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
