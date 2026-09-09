from app.crawler.models import CrawlRequest, SiteCrawlRequest


def test_crawl_request_prefers_https_for_public_http_url() -> None:
    request = CrawlRequest(url="http://ndtv.in/")
    assert str(request.url) == "https://ndtv.in/"


def test_crawl_request_keeps_local_http_fixture() -> None:
    request = CrawlRequest(url="http://127.0.0.1:8000/test")
    assert str(request.url) == "http://127.0.0.1:8000/test"


def test_site_crawl_request_prefers_https() -> None:
    request = SiteCrawlRequest(url="http://example.com/news")
    assert str(request.url) == "https://example.com/news"
