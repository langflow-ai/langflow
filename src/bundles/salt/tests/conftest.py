"""Per-test isolation for the Salt bundle tests."""

import pytest
from lfx_salt.components.salt import _salt_common as sc


@pytest.fixture(autouse=True)
def _isolate_state(tmp_path, monkeypatch):
    """Every test gets its own poll-cursor directory and a clean who_am_i cache -- without this.

    PersistentCursor would read/write a real ~/.salt/agents/... directory, and a stale cached identity from an
    earlier test (same api_key) would leak into a later one.
    """
    monkeypatch.setenv("SALTAPP_LANGFLOW_STATE_DIR", str(tmp_path / "state"))
    sc.reset_whoami_cache()
    yield
    sc.reset_whoami_cache()
