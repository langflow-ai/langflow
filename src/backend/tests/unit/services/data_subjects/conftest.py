import pytest
from langflow.services.deps import get_settings_service
from langflow.services.knowledge_base_storage import coordinator


@pytest.fixture(autouse=True)
def _run_erase_inline(monkeypatch):
    """Tests drive the engine directly; the background worker must not race them."""

    async def _no_worker(_self) -> None:
        return None

    monkeypatch.setattr("langflow.services.data_subjects.worker.DataSubjectEraseWorker.start", _no_worker)
    monkeypatch.setattr("langflow.services.data_subjects.engine.LATE_WRITE_SETTLE_SECONDS", 0)


@pytest.fixture
def storage_root(client, monkeypatch, tmp_path):  # noqa: ARG001 - initialize the app first
    """A private local knowledge-base root that the automatic storage upgrade may use."""
    root = tmp_path / "knowledge"
    monkeypatch.setattr(get_settings_service().settings, "knowledge_bases_dir", str(root))
    monkeypatch.delenv("PGVECTOR_CONNECTION_STRING", raising=False)
    # The single-host preflight inspects this machine's processes and mounts; a test is one host.
    monkeypatch.setattr(coordinator, "check_local_upgrade", lambda *_args: None)
    return root
