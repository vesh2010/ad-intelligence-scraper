from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundle_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", application_root()))


def runtime_root() -> Path:
    root = Path(os.getenv("AD_SCRAPER_DATA_ROOT", application_root() / "data"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def configure_bundled_tools() -> None:
    browser_root = bundle_root() / "browsers"
    if browser_root.is_dir():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_root))
    tools = bundle_root() / "tools"
    if tools.is_dir():
        os.environ["PATH"] = str(tools) + os.pathsep + os.environ.get("PATH", "")
        tessdata = tools / "tessdata"
        if tessdata.is_dir():
            os.environ.setdefault("TESSDATA_PREFIX", str(tessdata))


def wait_for_port(host: str, port: int, timeout: float = 60.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def main() -> int:
    configure_bundled_tools()
    os.environ.setdefault("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", "1")
    os.environ.setdefault("AD_SCRAPER_MONITOR_POLL_SECONDS", "60")
    os.environ.setdefault("AD_SCRAPER_DATA_ROOT", str(runtime_root()))

    from app.main import app

    host = "127.0.0.1"
    port = int(os.getenv("AD_SCRAPER_PORT", "8765"))
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning", workers=1))
    thread = threading.Thread(target=server.run, name="ad-scraper-server", daemon=True)
    thread.start()
    if not wait_for_port(host, port):
        print("Ad Intelligence Scraper could not start.", file=sys.stderr)
        return 1

    url = f"http://{host}:{port}/"
    webbrowser.open(url)
    print(f"Ad Intelligence Scraper is running at {url}")
    print("Keep this window open while using the scraper. Close it to stop the server.")
    try:
        while thread.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        server.should_exit = True
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
