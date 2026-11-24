import pytest
from lfx.utils import ssrf_protection
from oracle_test_utils import MOCK_ORACLE_HOST


@pytest.fixture
def trusted_mock_oracle_endpoint(monkeypatch):
    """Trust the synthetic endpoint only in tests that mock Oracle connections."""
    get_allowed_hosts = ssrf_protection.get_allowed_hosts
    monkeypatch.setattr(
        ssrf_protection,
        "get_allowed_hosts",
        lambda: [*get_allowed_hosts(), MOCK_ORACLE_HOST],
    )
