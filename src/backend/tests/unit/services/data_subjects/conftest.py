import pytest


@pytest.fixture(autouse=True)
def _run_erase_inline(monkeypatch):
    """Tests drive the engine directly; the background worker must not race them."""

    async def _no_worker(_self) -> None:
        return None

    monkeypatch.setattr("langflow.services.data_subjects.worker.DataSubjectEraseWorker.start", _no_worker)
    monkeypatch.setattr("langflow.services.data_subjects.engine.LATE_WRITE_SETTLE_SECONDS", 0)
