from datetime import datetime, timezone

from app.monitor_scheduler import is_due, parse_timestamp


def test_parse_timestamp_normalizes_naive_and_zulu_values():
    assert parse_timestamp("2026-09-04T10:00:00") == datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    assert parse_timestamp("2026-09-04T10:00:00Z") == datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    assert parse_timestamp("not-a-date") is None


def test_is_due_handles_malformed_interval_without_crashing():
    now = datetime(2026, 9, 4, 10, tzinfo=timezone.utc)
    assert is_due({"enabled": True, "interval_minutes": "invalid"}, now=now) is True


def test_is_due_handles_naive_clock_value():
    now = datetime(2026, 9, 4, 11)
    assert is_due({"enabled": True, "interval_minutes": 60, "last_run_at": "2026-09-04T10:00:00Z"}, now=now) is True
