"""Tests for the ``uvx --with`` MCP SDK constraint injection helper."""

from types import SimpleNamespace

import lfx.services.deps
from lfx.base.mcp.uvx import DEFAULT_MCP_SDK_CONSTRAINT, mcp_sdk_constraint_args


def _install_settings(monkeypatch, **settings):
    service = SimpleNamespace(settings=SimpleNamespace(**settings))
    monkeypatch.setattr(lfx.services.deps, "get_settings_service", lambda: service)


def test_default_constraint_is_injected(monkeypatch):
    _install_settings(monkeypatch, mcp_sdk_constraint=DEFAULT_MCP_SDK_CONSTRAINT)
    assert mcp_sdk_constraint_args() == ["--with", DEFAULT_MCP_SDK_CONSTRAINT]


def test_custom_constraint_is_injected(monkeypatch):
    _install_settings(monkeypatch, mcp_sdk_constraint="mcp~=1.30")
    assert mcp_sdk_constraint_args() == ["--with", "mcp~=1.30"]


def test_empty_constraint_disables_injection(monkeypatch):
    _install_settings(monkeypatch, mcp_sdk_constraint="")
    assert mcp_sdk_constraint_args() == []


def test_whitespace_constraint_disables_injection(monkeypatch):
    _install_settings(monkeypatch, mcp_sdk_constraint="   ")
    assert mcp_sdk_constraint_args() == []


def test_unavailable_settings_fall_back_to_default(monkeypatch):
    def _raise():
        msg = "settings not ready"
        raise RuntimeError(msg)

    monkeypatch.setattr(lfx.services.deps, "get_settings_service", _raise)
    assert mcp_sdk_constraint_args() == ["--with", DEFAULT_MCP_SDK_CONSTRAINT]
