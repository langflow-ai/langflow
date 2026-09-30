import pytest


@pytest.fixture(autouse=True)
def _run_erase_inline(monkeypatch):
    """Tests drive the engine directly; the background worker must not race them."""
    monkeypatch.setenv("LANGFLOW_DATA_SUBJECT_WORKER_ENABLED", "false")
    monkeypatch.setattr("langflow.services.data_subjects.engine.LATE_WRITE_SETTLE_SECONDS", 0)
