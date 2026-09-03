from app.ad_records import AdRecord
from app.crawler.models import CrawlResult
from app.history_orchestration import persist_crawl_result, persist_dual_crawl_result
from app.history_store import HistoryStore


def _result(run_id: str, device: str) -> CrawlResult:
    return CrawlResult(
        run_id=run_id,
        requested_url="https://example.com/news",
        final_url="https://example.com/news",
        status=200,
        title="Example",
        elapsed_ms=10,
        dimensions={"width": 1280, "height": 720},
        counts={},
        metadata={},
        redirects=[],
        network=[],
        console_errors=[],
        page_errors=[],
        frames=[],
        artifacts={},
        ad_records=[
            AdRecord(
                ad_id="ad-1",
                ad_type="display",
                brand_name="Acme",
                advertiser_name="Acme Corp",
                ad_unit_code="top",
                destination_urls=["https://acme.example/offer"],
            )
        ],
        device=device,
    )


def test_persist_crawl_result_groups_observation(tmp_path):
    store = HistoryStore(tmp_path)
    result = _result("a" * 32, "desktop")

    stored = persist_crawl_result(
        store,
        "https://example.com/news",
        result,
        session_id="session-1",
        observed_at="2026-09-03T12:00:00Z",
    )

    assert stored["crawl_session_id"] == "session-1"
    assert stored["observations_added"] == 1
    rows = store.load("https://example.com/news")
    assert rows[0]["device"] == "desktop"
    assert rows[0]["crawl_session_id"] == "session-1"
    assert rows[0]["run_id"] == "a" * 32
    assert rows[0]["target_url"] == "https://example.com/news"


def test_persist_dual_crawl_result_uses_one_session(tmp_path):
    store = HistoryStore(tmp_path)
    payload = {
        "desktop": _result("a" * 32, "desktop").model_dump(),
        "mobile": _result("b" * 32, "mobile").model_dump(),
    }

    stored = persist_dual_crawl_result(
        store,
        "https://example.com/news",
        payload,
        session_id="session-2",
        observed_at="2026-09-03T13:00:00Z",
    )

    assert stored["observations_added"] == 2
    rows = store.load("https://example.com/news")
    assert {row["device"] for row in rows} == {"desktop", "mobile"}
    assert {row["crawl_session_id"] for row in rows} == {"session-2"}
    assert {row["observed_at"] for row in rows} == {"2026-09-03T13:00:00Z"}
    assert {row["run_id"] for row in rows} == {"a" * 32, "b" * 32}
