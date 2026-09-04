from concurrent.futures import ThreadPoolExecutor

from app.history_store import HistoryStore


def test_history_store_concurrent_appends_are_transactional(tmp_path):
    store = HistoryStore(tmp_path / "history")
    target = "https://example.com/news"

    def append(index: int):
        return store.append(
            target,
            [{"observed_at": f"2026-09-04T10:{index:02d}:00Z", "campaign_key": f"campaign-{index}"}],
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(append, range(24)))

    assert len(results) == 24
    observations = store.load(target)
    assert len(observations) == 24
    assert {row["campaign_key"] for row in observations} == {f"campaign-{i}" for i in range(24)}


def test_history_store_clear_is_atomic(tmp_path):
    store = HistoryStore(tmp_path / "history")
    target = "https://example.com"
    store.append(target, [{"campaign_key": "one"}, {"campaign_key": "two"}])
    store.clear(target)
    assert store.load(target) == []
