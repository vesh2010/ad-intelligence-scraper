from app.url_discovery import classify_page, extract_discovery_urls, infer_section


def test_extract_discovery_urls_includes_canonical_jsonld_and_iframe() -> None:
    html = '''
    <link rel="canonical" href="https://example.com/article/1/">
    <a href="/business">Business</a>
    <iframe src="https://example.com/ad-frame"></iframe>
    <script type="application/ld+json">{"@type":"NewsArticle","url":"https://example.com/article/2"}</script>
    <a href="https://outside.example/x">outside</a>
    '''
    result = extract_discovery_urls("https://example.com/", html, "https://example.com/")
    assert "https://example.com/article/1" in result
    assert "https://example.com/business" in result
    assert "https://example.com/ad-frame" in result
    assert "https://example.com/article/2" in result
    assert all("outside.example" not in url for url in result)


def test_page_taxonomy_and_section_are_stable() -> None:
    assert classify_page("https://example.com/") == "homepage"
    assert classify_page("https://example.com/business/markets/story") == "article"
    assert classify_page("https://example.com/video/123") == "video"
    assert classify_page("https://example.com/gallery/123") == "gallery"
    assert classify_page("https://example.com/category/business") == "category"
    assert infer_section("https://example.com/business/markets/story", "https://example.com/") == "business"
