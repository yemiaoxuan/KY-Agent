import pytest

from app.services.notification.email_service import _run_async_from_sync


@pytest.mark.asyncio
async def test_run_async_from_sync_works_inside_running_event_loop() -> None:
    async def _value() -> str:
        return "ok"

    assert _run_async_from_sync(lambda: _value()) == "ok"
