"""Fixtures shared by the Agent harness tests."""

import pytest


@pytest.fixture
def allow_edited_component_code(monkeypatch):
    """Let a regular user run a flow whose component code a test edited on purpose.

    ``custom_component_admin_only`` defaults to True, which blocks such code as outdated.
    """
    from lfx.services.deps import get_settings_service

    monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)
