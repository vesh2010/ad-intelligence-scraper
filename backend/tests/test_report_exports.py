from app.report_exports import report_export_links


def test_report_export_links_url_encode_target():
    links = report_export_links("https://example.com/path?q=1&x=2")
    assert links["html"] == "/api/history/report?target=https%3A%2F%2Fexample.com%2Fpath%3Fq%3D1%26x%3D2"
    assert links["pdf"].startswith("/api/history/report.pdf?target=")
    assert links["intelligence"].startswith("/api/history/intelligence?target=")
