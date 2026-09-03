from app.history_store import HistoryStore, target_key


def test_target_key_is_stable_and_path_safe():
    assert target_key("https://Example.com/news") == target_key("https://example.com/home")
    assert "/" not in target_key("https://example.com")


def test_history_store_round_trip_and_append(tmp_path):
    store = HistoryStore(tmp_path)
    target = "https://example.com/news"
    first = [{"observed_at": "2026-09-03T10:00:00Z", "campaign_key": "c1"}]
    second = [{"observed_at": "2026-09-03T11:00:00Z", "campaign_key": "c2"}]

    assert store.append(target, first)["history_size"] == 1
    assert store.append(target, second)["history_size"] == 2
    assert store.load(target) == first + second
    store.clear(target)
    assert store.load(target) == []
