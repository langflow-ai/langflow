"""Credential-free migration locations preserve the distinction between IPv6 hosts and ports."""

import pytest
from langflow.api.utils.migration_probes import location


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("postgresql://db.internal/langflow", "db.internal/langflow"),
        ("postgresql://db.internal:5432/langflow", "db.internal:5432/langflow"),
        ("postgresql://[::1]/langflow", "[::1]/langflow"),
        ("postgresql://[::1]:5432/langflow", "[::1]:5432/langflow"),
    ],
)
def test_locations_keep_hosts_and_ports_unambiguous(address, expected):
    assert location(address) == expected
