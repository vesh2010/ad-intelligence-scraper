from app.crawler.security import redact_headers
from app.crawler.models import CrawlRequest


def test_redacts_sensitive_headers_case_insensitively():
    result = redact_headers(
        {"Authorization": "Bearer secret", "cookie": "sid=secret", "Accept": "text/html"}
    )
    assert result["Authorization"] == "[REDACTED]"
    assert result["cookie"] == "[REDACTED]"
    assert result["Accept"] == "text/html"


def test_crawl_request_defaults_and_bounds():
    request = CrawlRequest(url="https://www.ndtvprofit.com/")
    assert request.wait_ms == 2000
    assert request.timeout_ms == 30000
    assert request.trace is True
