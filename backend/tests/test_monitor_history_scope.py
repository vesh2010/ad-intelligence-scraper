from app.ad_records import AdRecord
from app.crawler.models import CrawlResult
from app.history_orchestration import persist_crawl_result
from app.history_store import HistoryStore


def _result(device: str, brand: str) -> CrawlResult:
    return CrawlResult(
        run_id=(brand.lower() + device).encode().hex()[:32].ljust(32, "0"),
        requested_url="https://example.com/news",
        final_url="https://example.com/news",
        status=200,
        title="Example",
        elapsed_ms=1,
        dimensions={"width": 1280, "height": 720},
        counts={}, metadata={}, redirects=[], network=[], console_errors=[], page_errors=[], frames=[], artifacts={},
        ad_records=[AdRecord(ad_id=brand, ad_type="display", brand_name=brand, advertiser_name=f"{brand} Corp", ad_unit_code="top")],
        device=device,
    )


def test_monitor_observations_are_scoped_to_monitor_id(tmp_path):
    store = HistoryStore(tmp_path)
    persist_crawl_result(store, "https://example.com/news", _result("desktop", "Alpha"), session_id="s1", observed_at="2026-09-04T10:00:00Z", monitor_id="m1")
    persist_crawl_result(store, "https://example.com/news", _result("desktop", "Beta"), session_id="s2", observed_at="2026-09-04T11:00:00Z", monitor_id="m2")

    rows = store.load("https://example.com/news")
    assert {row["monitor_id"] for row in rows} == {"m1", "m2"}
    assert [row["brand_name"] for row in rows if row["monitor_id"] == "m1"] == ["Alpha"]
    assert [row["brand_name"] for row in rows if row["monitor_id"] == "m2"] == ["Beta"]
