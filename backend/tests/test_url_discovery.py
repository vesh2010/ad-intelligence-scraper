from app.url_discovery import URLQueue, extract_links, normalize_url, same_site


def test_normalize_url_removes_fragment_and_trailing_slash():
    assert normalize_url("https://www.example.com/news/#story") == "https://www.example.com/news"


def test_normalize_url_rejects_binary_assets():
    assert normalize_url("https://example.com/file.pdf") is None


def test_same_site_allows_subdomain_but_not_external_domain():
    assert same_site("https://www.example.com/news", "https://example.com/")
    assert same_site("https://cdn.example.com/news", "https://example.com/")
    assert not same_site("https://example.org/news", "https://example.com/")


def test_extract_links_resolves_relative_and_filters_external():
    result = extract_links(
        "https://example.com/news/story",
        ["/markets", "https://example.com/business", "https://evil.example/x", "mailto:test@example.com"],
        "https://example.com/",
    )
    assert result == ["https://example.com/markets", "https://example.com/business"]


def test_url_queue_deduplicates_and_respects_page_limit():
    queue = URLQueue("https://example.com/", max_pages=3)
    assert queue.pop() == (0, "https://example.com/")
    assert queue.add_links(
        "https://example.com/",
        ["/news/a", "/news/a#x", "/markets", "https://other.example/x"],
        depth=0,
    ) == 2
    assert queue.seen_count == 3
    assert len(queue) == 2
