import asyncio

from app import main


def test_lifespan_starts_and_stops_scheduler(monkeypatch):
    async def scenario():
        monkeypatch.setenv("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", "1")
        monkeypatch.setenv("AD_SCRAPER_MONITOR_POLL_SECONDS", "1")
        assert main._scheduler_task is None
        async with main.lifespan(main.app):
            task = main._scheduler_task
            assert task is not None
            await asyncio.sleep(0)
            assert not task.done()
        assert main._scheduler_task is None
        assert task.cancelled()

    asyncio.run(scenario())


def test_scheduler_disabled_by_default(monkeypatch):
    async def scenario():
        monkeypatch.delenv("AD_SCRAPER_ENABLE_MONITOR_SCHEDULER", raising=False)
        async with main.lifespan(main.app):
            assert main._scheduler_task is None

    asyncio.run(scenario())
