from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import traceback
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


def configure_logging() -> Path:
    log_path = application_root() / "startup.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    return log_path


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


def wait_for_port(host: str, port: int, timeout: float = 180.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def open_browser_when_ready(url: str, host: str, port: int) -> None:
    if os.getenv("AD_SCRAPER_DISABLE_BROWSER") == "1":
        return
    if wait_for_port(host, port):
        webbrowser.open(url)


def main() -> int:
    log_path = configure_logging()
    try:
        logging.info("launcher start; frozen=%s bundle=%s", getattr(sys, "frozen", False), bundle_root())
        configure_bundled_tools()
        os.environ.setdefault("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", "1")
        os.environ.setdefault("AD_SCRAPER_MONITOR_POLL_SECONDS", "60")
        os.environ.setdefault("AD_SCRAPER_DATA_ROOT", str(runtime_root()))

        from app.main import app

        host = "127.0.0.1"
        port = int(os.getenv("AD_SCRAPER_PORT", "8765"))
        url = f"http://{host}:{port}/"
        if os.getenv("AD_SCRAPER_DISABLE_BROWSER") != "1":
            threading.Thread(
                target=open_browser_when_ready,
                args=(url, host, port),
                name="open-browser",
                daemon=True,
            ).start()

        logging.info("starting uvicorn on %s", url)
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="info",
            workers=1,
            log_config=None,
        )
        server = uvicorn.Server(config)
        server.run()
        logging.info("uvicorn stopped")
        return 0
    except Exception:
        logging.exception("launcher failed")
        return 1
    finally:
        logging.shutdown()
        if not log_path.exists():
            log_path.write_text("launcher exited without diagnostics\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
