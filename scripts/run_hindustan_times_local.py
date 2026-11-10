"""Run on the NCR computer, with a temporary loopback-only forward proxy.

No public listener, port forwarding, TLS interception, or paid proxy account.
This does not make a GitHub-hosted runner use the Windows computer's network.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def exclusive_run(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("Another local monitor run is active.") from None
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise RuntimeError("Another local monitor run is active.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def local_environment(server: str) -> dict[str, str]:
    env = os.environ.copy()
    env.update(PROXY_SERVER=server, PROXY_USERNAME="", PROXY_PASSWORD="",
               REQUIRE_INDIA_PROXY="true", SCREENSHOT_COUNT="25",
               PYTHONUNBUFFERED="1")
    return env


@contextmanager
def local_proxy():
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        port = reservation.getsockname()[1]
    options = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == "nt" else {"start_new_session": True})
    process = subprocess.Popen([
        sys.executable, "-m", "proxy", "--hostname", "127.0.0.1",
        "--port", str(port), "--num-workers", "1", "--num-acceptors", "1",
        "--log-level", "ERROR",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **options)
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError("Local proxy exited; reinstall local monitor dependencies.")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                    break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Local proxy did not become ready.")
        yield f"http://127.0.0.1:{port}"
    finally:
        # proxy.py can spawn workers; stop the process tree, not only its parent.
        if os.name == "nt":
            if process.poll() is None:
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               check=False)
        else:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def verify_local_exit(server: str) -> dict[str, str]:
    from playwright.sync_api import sync_playwright
    try:
        from .capture_hindustan_times import validate_proxy_geo
    except ImportError:
        from capture_hindustan_times import validate_proxy_geo
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, proxy={"server": server})
        try:
            page = browser.new_page(ignore_https_errors=False)
            response = page.goto("https://ipapi.co/json/",
                                 wait_until="domcontentloaded", timeout=30000)
            if not response or response.status != 200:
                raise RuntimeError("Geolocation service unavailable; local exit not verified.")
            return validate_proxy_geo(response.json())
        finally:
            browser.close()


def run(check_only: bool = False) -> None:
    with exclusive_run(ROOT / ".ht-monitor" / "run.lock"), local_proxy() as server:
        if check_only:
            geo = verify_local_exit(server)
            print(f"Verified local browser exit: {geo['country']}, {geo['city']}, {geo['region']}")
            return
        before = set((ROOT / "screenshots").rglob("summary.json"))
        completed = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "capture_hindustan_times.py")],
            cwd=ROOT, env=local_environment(server), check=False,
        )
        if completed.returncode:
            raise RuntimeError("Capture failed. Inspect the local run log and screenshot diagnostics.")
        created = set((ROOT / "screenshots").rglob("summary.json")) - before
        if len(created) != 1:
            raise RuntimeError("Cannot identify exactly one new local batch.")
        try:
            from .validate_hindustan_times_batch import validate_batch
        except ImportError:
            from validate_hindustan_times_batch import validate_batch
        folder = created.pop().parent
        validate_batch(folder)
        print(f"Validated 25 unique viewport captures. Open: {folder / 'index.html'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-proxy", action="store_true",
                        help="Verify NCR egress through local Chromium without capturing publisher pages.")
    args = parser.parse_args()
    try:
        run(check_only=args.check_proxy)
    except Exception as exc:
        message = str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__
        raise SystemExit(message) from None
