import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import threading
from unittest.mock import Mock
from urllib.parse import urlparse

import pytest

from scripts import run_hindustan_times_local as local


def test_environment_forces_ncr_verification_and_clears_remote_credentials(monkeypatch):
    monkeypatch.setenv("REQUIRE_INDIA_PROXY", "false")
    monkeypatch.setenv("PROXY_USERNAME", "old-user")
    monkeypatch.setenv("PROXY_PASSWORD", "old-password")
    env = local.local_environment("http://127.0.0.1:9999")
    assert env["REQUIRE_INDIA_PROXY"] == "true"
    assert env["SCREENSHOT_COUNT"] == "25"
    assert env["PROXY_USERNAME"] == env["PROXY_PASSWORD"] == ""


def test_exclusive_lock_rejects_overlap_then_releases(tmp_path):
    path = tmp_path / "run.lock"
    with local.exclusive_run(path):
        with pytest.raises(RuntimeError, match="is active"):
            with local.exclusive_run(path):
                pytest.fail("Concurrent lock acquired")
    with local.exclusive_run(path):
        pass


def test_real_loopback_proxy_forwards_and_shuts_down():
    pytest.importorskip("proxy", reason="Install scripts/windows/requirements-ht-monitor.txt for proxy integration tests")
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "10")
            self.end_headers()
            self.wfile.write(b"local-test")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with local.local_proxy() as endpoint:
            address = urlparse(endpoint)
            assert address.hostname == "127.0.0.1"
            # CONNECT tests the same tunneling method used for HTTPS, with a
            # local HTTP fixture inside the tunnel. No external service is used.
            connection = http.client.HTTPConnection(address.hostname, address.port, timeout=5)
            connection.set_tunnel("127.0.0.1", server.server_port)
            connection.request("GET", "/")
            response = connection.getresponse()
            assert response.status == 200
            assert response.read() == b"local-test"
            connection.close()
        connection = http.client.HTTPConnection(address.hostname, address.port, timeout=1)
        with pytest.raises(OSError):
            connection.connect()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_check_only_verifies_browser_without_capture(monkeypatch, tmp_path):
    from contextlib import contextmanager

    @contextmanager
    def proxy():
        yield "http://127.0.0.1:9999"

    monkeypatch.setattr(local, "ROOT", tmp_path)
    monkeypatch.setattr(local, "local_proxy", proxy)
    verifier = Mock(return_value={"country": "IN", "city": "Noida", "region": "Uttar Pradesh"})
    monkeypatch.setattr(local, "verify_local_exit", verifier)
    runner = Mock()
    monkeypatch.setattr(local.subprocess, "run", runner)
    local.run(check_only=True)
    verifier.assert_called_once_with("http://127.0.0.1:9999")
    runner.assert_not_called()


def test_capture_failure_does_not_validate_stale_batch(monkeypatch, tmp_path):
    from contextlib import contextmanager

    @contextmanager
    def proxy():
        yield "http://127.0.0.1:9999"

    monkeypatch.setattr(local, "ROOT", tmp_path)
    monkeypatch.setattr(local, "local_proxy", proxy)
    monkeypatch.setattr(local.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1)))
    with pytest.raises(RuntimeError, match="Capture failed"):
        local.run()


def test_ps_setup_has_loopback_preflight_before_task_registration():
    root = Path(__file__).resolve().parents[2]
    setup = (root / "scripts/windows/setup_ht_monitor.ps1").read_text()
    assert setup.index("--check-proxy") < setup.index("Register-ScheduledTask")
    assert 'Get-TimeZone' in setup
    assert '-LogonType Interactive -RunLevel Limited' in setup
    assert 'New-ScheduledTaskTrigger -Daily -At "08:00"' in setup
    assert 'New-ScheduledTaskTrigger -Daily -At "14:00"' in setup
