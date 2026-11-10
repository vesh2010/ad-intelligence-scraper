"""Offline regressions: no publisher requests or proxy credentials required."""
import csv
import json
import os
import struct
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from playwright.sync_api import TimeoutError as BrowserTimeout, sync_playwright

from scripts import capture_hindustan_times as capture
from scripts.validate_hindustan_times_batch import jpeg_dimensions, validate_batch


@pytest.mark.parametrize("url", [
    "http://hindustantimes.com/india-news/?utm_source=x#heading",
    "https://www.hindustantimes.com/india-news",
    "https://hindustantimes.com/india-news?x=1",
])
def test_canonical_collapses_aliases(url):
    assert capture.canonical(url) == capture.BASE_URL + "india-news"


@pytest.mark.parametrize("url", [
    "https://evil.example/", "https://hindustantimes.com.evil.example/",
    "https://user:password@hindustantimes.com/", "javascript:alert(1)",
    "https://www.hindustantimes.com/photo.jpg",
    "https://www.hindustantimes.com/amp/news",
])
def test_canonical_rejects_non_pages(url):
    assert capture.canonical(url) is None


@pytest.mark.parametrize("city,region", [
    ("New Delhi", "Delhi"), ("Gurugram", "Haryana"),
    ("Greater Noida", "Uttar Pradesh"), ("Faridabad", "Haryana"),
    ("Unknown", "National Capital Territory of Delhi"),
])
def test_verified_ncr(city, region):
    assert capture.validate_proxy_geo({"country_code": "IN", "city": city, "region": region})["country"] == "IN"


@pytest.mark.parametrize("geo", [
    {}, {"error": True, "country_code": "IN", "city": "Delhi"},
    {"country_code": "US", "city": "Delhi"},
    {"country_code": "IN", "city": "Mumbai", "region": "Maharashtra"},
    {"country_code": "IN", "city": "Unknown", "region": "Haryana"},
    {"country_code": "IN", "city": "Not Delhi", "region": "Unknown"},
])
def test_reject_unverified_geo(geo):
    with pytest.raises(RuntimeError):
        capture.validate_proxy_geo(geo)


def jpeg_fixture(width=1440, height=1000):
    # A minimal SOF segment for testing metadata validation, not a sample capture.
    return b"\xff\xd8\xff\xc0" + struct.pack(">HBHH", 7, 8, height, width) + b"\xff\xd9"


def fake_run(monkeypatch, tmp_path, count=30, fail_url=None, redirect=False):
    page = Mock()
    urls = [capture.BASE_URL + f"india-news/story-{n}.html" for n in range(count)]

    def goto(url, **kwargs):
        if url == fail_url:
            raise BrowserTimeout("navigation failed")
        page.url = capture.BASE_URL if redirect and url in urls else url
        return SimpleNamespace(status=200, json=lambda: {
            "country_code": "IN", "city": "New Delhi", "region": "Delhi"})

    def screenshot(**kwargs):
        assert kwargs["full_page"] is False
        Path(kwargs["path"]).write_bytes(jpeg_fixture())

    page.goto.side_effect = goto
    page.screenshot.side_effect = screenshot
    page.title.return_value = "<Test & title>"
    page.locator.return_value.evaluate_all.return_value = urls
    context = Mock()
    context.new_page.return_value = page
    browser = Mock()
    browser.new_context.return_value = context
    manager = Mock()
    manager.__enter__ = Mock(return_value=SimpleNamespace(
        chromium=SimpleNamespace(launch=Mock(return_value=browser))))
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(capture, "sync_playwright", lambda: manager)
    monkeypatch.setattr(capture, "OUT", tmp_path / "2026-11-10" / "08-00-00")
    monkeypatch.setattr(capture, "PROXY_SERVER", "http://proxy.invalid:8080")
    monkeypatch.setattr(capture, "REQUIRE_INDIA_PROXY", True)
    monkeypatch.setattr(capture, "COUNT", 25)
    robots = Mock()
    robots.can_fetch.return_value = True
    monkeypatch.setattr(capture, "robots_parser", lambda ctx: robots)
    monkeypatch.setattr(capture, "inspect_ads", lambda page: {
        "ad_slot_count": "1", "creative_evidence_count": "0",
        "creative_status": "iframe_content_unverified"})
    return page, urls


def test_complete_batch_with_timeout_replacement(monkeypatch, tmp_path):
    page, urls = fake_run(monkeypatch, tmp_path, fail_url=capture.BASE_URL + "india-news/story-0.html")
    capture.main()
    validate_batch(tmp_path)
    summary = json.loads((capture.OUT / "summary.json").read_text())
    assert summary["failed_attempts"] == 1
    failed = [x for x in summary["captures"] if x["status"] == "navigation_timeout"]
    assert failed and failed[0]["screenshot"] == ""
    assert page.screenshot.call_count == 25
    gallery = (capture.OUT / "index.html").read_text()
    assert "&lt;Test &amp; title&gt;" in gallery


def test_insufficient_urls_never_repeats_homepage(monkeypatch, tmp_path):
    page, _ = fake_run(monkeypatch, tmp_path, count=3)
    with pytest.raises(RuntimeError, match="unique permitted URLs"):
        capture.main()
    page.screenshot.assert_not_called()


def test_redirect_duplicates_produce_incomplete_batch(monkeypatch, tmp_path):
    page, _ = fake_run(monkeypatch, tmp_path, redirect=True)
    with pytest.raises(RuntimeError, match="Incomplete batch"):
        capture.main()
    assert page.screenshot.call_count == 1
    summary = json.loads((capture.OUT / "summary.json").read_text())
    assert summary["status"] == "incomplete"
    with pytest.raises(ValueError, match="incomplete"):
        validate_batch(tmp_path)


def test_missing_proxy_fails_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(capture, "OUT", tmp_path)
    monkeypatch.setattr(capture, "PROXY_SERVER", "")
    monkeypatch.setattr(capture, "REQUIRE_INDIA_PROXY", True)
    browser = Mock()
    monkeypatch.setattr(capture, "sync_playwright", browser)
    with pytest.raises(RuntimeError, match="PROXY_SERVER"):
        capture.main()
    browser.assert_not_called()


@pytest.mark.parametrize("mutation", ["duplicate_url", "wrong_size", "missing_image",
                                    "summary_mismatch", "wrong_geo", "broken_gallery"])
def test_validator_rejects_bad_batches(monkeypatch, tmp_path, mutation):
    fake_run(monkeypatch, tmp_path)
    capture.main()
    summary_path = capture.OUT / "summary.json"
    summary = json.loads(summary_path.read_text())
    if mutation == "wrong_size":
        (capture.OUT / summary["captures"][0]["screenshot"]).write_bytes(jpeg_fixture(1440, 5000))
    elif mutation == "missing_image":
        (capture.OUT / summary["captures"][0]["screenshot"]).unlink()
    elif mutation == "broken_gallery":
        (capture.OUT / "index.html").write_text("missing")
    else:
        if mutation == "wrong_geo":
            summary["proxy_geo"] = {"country": "US", "city": "Delhi", "region": ""}
        elif mutation == "duplicate_url":
            summary["captures"][1]["final_url"] = summary["captures"][0]["final_url"]
            with (capture.OUT / "manifest.csv").open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(summary["captures"][0]))
                writer.writeheader()
                writer.writerows(summary["captures"])
        else:
            summary["captures"][0]["title"] = "changed"
        summary_path.write_text(json.dumps(summary))
    with pytest.raises((ValueError, RuntimeError)):
        validate_batch(tmp_path)


def test_jpeg_rejects_truncated_file(tmp_path):
    path = tmp_path / "bad.jpg"
    path.write_bytes(b"\xff\xd8")
    with pytest.raises(ValueError):
        jpeg_dimensions(path)


@pytest.fixture
def local_page():
    # CI uses Playwright's installed Chromium. Nix development can use system Chromium.
    executable = os.getenv("TEST_CHROMIUM_EXECUTABLE")
    with sync_playwright() as p:
        browser = p.chromium.launch(**({"executable_path": executable} if executable else {}))
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        yield page
        browser.close()


def test_dom_slots_deduplicated_and_empty_not_creative(local_page, monkeypatch):
    monkeypatch.setattr(capture, "AD_WAIT_MS", 0)
    local_page.set_content('<div id="div-gpt-ad-1" class="advertisement ad-slot" '
                           'data-ad="yes" style="width:300px;height:250px">'
                           '<iframe id="google_ads_1" style="width:300px;height:250px"></iframe></div>')
    result = capture.inspect_ads(local_page)
    assert result["ad_slot_count"] == "1"
    assert result["creative_evidence_count"] == "0"
    assert result["creative_status"] == "iframe_content_unverified"


def test_dom_loaded_media_and_real_viewport(local_page, monkeypatch, tmp_path):
    monkeypatch.setattr(capture, "AD_WAIT_MS", 0)
    local_page.set_content('<div class="ad-slot" style="width:300px;height:250px">'
                           '<img width="300" height="250" src="data:image/svg+xml,'
                           '%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 '
                           'height=%22250%22%3E%3C/svg%3E"></div>'
                           '<div style="height:4000px"></div>')
    local_page.wait_for_function("document.querySelector('img').complete")
    result = capture.inspect_ads(local_page)
    assert result["creative_evidence_count"] == "1"
    path = tmp_path / "viewport.jpg"
    local_page.screenshot(path=str(path), type="jpeg", full_page=False)
    assert jpeg_dimensions(path) == (1440, 1000)


def test_robots_unavailable_fails_closed():
    context = Mock()
    context.request.get.return_value.status = 503
    with pytest.raises(RuntimeError, match="robots.txt"):
        capture.robots_parser(context)


def test_screenshot_timeout_is_not_navigation_timeout(monkeypatch, tmp_path):
    page, _ = fake_run(monkeypatch, tmp_path)
    original = page.screenshot.side_effect
    attempts = 0

    def screenshot(**kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            Path(kwargs["path"]).write_bytes(b"partial")
            raise BrowserTimeout("screenshot timed out")
        original(**kwargs)

    page.screenshot.side_effect = screenshot
    capture.main()
    validate_batch(tmp_path)
    summary = json.loads((capture.OUT / "summary.json").read_text())
    assert summary["captures"][0]["status"] == "screenshot_timeout"
    assert summary["captures"][0]["screenshot"] == ""


def test_robots_request_uses_browser_context_and_timeout():
    context = Mock()
    context.request.get.return_value.status = 200
    context.request.get.return_value.text.return_value = "User-agent: *\nDisallow: /private"
    parser = capture.robots_parser(context)
    context.request.get.assert_called_once_with(capture.BASE_URL + "robots.txt",
                                                timeout=capture.NAV_TIMEOUT_MS)
    assert not parser.can_fetch(capture.USER_AGENT, capture.BASE_URL + "private")
