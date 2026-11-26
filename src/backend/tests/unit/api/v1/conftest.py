"""Fixtures shared by the v1 API tests."""

import pytest
from langflow.services.deps import get_settings_service


@pytest.fixture
def allow_edited_component_code(client, monkeypatch):  # noqa: ARG001
    """Let a regular user run a flow whose component code a test edited on purpose.

    ``custom_component_admin_only`` defaults to True, which blocks such code as outdated.
    Depends on ``client`` because the client starts the settings service this patches.
    """
    monkeypatch.setattr(get_settings_service().settings, "custom_component_admin_only", False)
