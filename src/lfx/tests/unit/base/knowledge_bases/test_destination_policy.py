"""Unit tests for the exclusive KB destination policy, in isolation from the backends.

``enforce_kb_destination`` answers one question — did the *operator* choose this
host — and it is the only thing standing between a tenant-supplied hostname and
two SDKs that cannot be pinned to the address they validated as. The backend
suites exercise it through ``_resolve_secrets``; these tests pin the policy's own
semantics so a change in matching or provenance handling fails here first.
"""

from __future__ import annotations

import pytest
from lfx.base.knowledge_bases.backends.destination_policy import (
    enforce_kb_destination,
    get_kb_allowed_hosts,
    is_kb_destination_host_allowed,
)
from lfx.utils.ssrf_protection import SSRFProtectionError

_TENANT = "variable"
_OPERATOR = "environment"


@pytest.fixture(autouse=True)
def _connector_validation_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
    monkeypatch.delenv("LANGFLOW_KB_ALLOWED_HOSTS", raising=False)


def _enforce(url: str, source: str = _TENANT) -> None:
    enforce_kb_destination(url, source=source, description="the test destination")


# ---- allow-list parsing ----------------------------------------------------


def test_unset_allowlist_is_empty_not_permissive() -> None:
    """An empty exclusive list denies. This is the inversion vs. SSRF_ALLOWED_HOSTS."""
    assert get_kb_allowed_hosts() == []
    assert is_kb_destination_host_allowed("search.example.com") is False


def test_allowlist_is_split_and_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", " a.example , , b.example ")
    assert get_kb_allowed_hosts() == ["a.example", "b.example"]


@pytest.mark.parametrize(
    ("patterns", "hostname", "expected"),
    [
        ("search.example.com", "search.example.com", True),
        ("search.example.com", "other.example.com", False),
        ("*.corp.example", "search.corp.example", True),
        ("*.corp.example", "corp.example.evil.test", False),
        ("10.0.0.5", "10.0.0.5", True),
        ("10.0.0.0/24", "10.0.0.7", True),
        ("10.0.0.0/24", "10.0.1.7", False),
    ],
)
def test_host_matching(
    monkeypatch: pytest.MonkeyPatch,
    patterns: str,
    hostname: str,
    *,
    expected: bool,
) -> None:
    """Matching is delegated to the SSRF matcher so both lists behave identically."""
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", patterns)
    assert is_kb_destination_host_allowed(hostname) is expected


# ---- enforcement -----------------------------------------------------------


def test_tenant_host_is_refused_when_unlisted() -> None:
    with pytest.raises(SSRFProtectionError, match="not an approved destination"):
        _enforce("https://rebind.attacker.example:9200")


def test_public_resolution_does_not_approve_a_host() -> None:
    """The refusal is about provenance, so it never consults DNS at all."""
    with pytest.raises(SSRFProtectionError, match="not an approved destination"):
        _enforce("https://www.example.com")


def test_listed_tenant_host_is_approved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_KB_ALLOWED_HOSTS", "search.corp.example")
    _enforce("https://search.corp.example:9200")


def test_operator_provenance_is_approved_without_a_listing() -> None:
    _enforce("https://search.example.com:9200", source=_OPERATOR)


def test_missing_provenance_is_treated_as_tenant_supplied() -> None:
    """Anything that is not explicitly operator-set fails closed."""
    with pytest.raises(SSRFProtectionError, match="not an approved destination"):
        _enforce("https://search.example.com:9200", source="missing")


def test_refusal_names_the_host_and_both_remedies() -> None:
    with pytest.raises(SSRFProtectionError) as excinfo:
        _enforce("https://rebind.attacker.example:9200")
    message = str(excinfo.value)
    assert "rebind.attacker.example" in message
    assert "the test destination" in message
    assert "LANGFLOW_KB_ALLOWED_HOSTS" in message
    assert "environment variable" in message


@pytest.mark.parametrize("url", ["file:///etc/passwd", "not-a-url", ""])
def test_hostless_urls_defer_to_the_ssrf_shape_error(url: str) -> None:
    """No second wording for a malformed URL — validate_connector_url_for_ssrf owns it."""
    _enforce(url)


def test_kill_switch_disables_the_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "false")
    _enforce("https://rebind.attacker.example:9200")
