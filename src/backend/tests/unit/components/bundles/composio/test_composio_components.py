"""Unit tests for Composio components cloud validation."""

import os
from unittest.mock import patch

import pytest
from lfx.base.composio.composio_base import ComposioBaseComponent
from lfx.components.composio.composio_api import ComposioAPIComponent


@pytest.mark.unit
class TestComposioCloudValidation:
    """Test Composio components cloud validation."""

    def test_composio_api_disabled_in_astra_cloud(self):
        """Test that ComposioAPI build_tool raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = ComposioAPIComponent(api_key="test-key")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.build_tool()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    def test_composio_base_execute_disabled_in_astra_cloud(self):
        """Test that ComposioBase execute_action raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            component = ComposioBaseComponent(api_key="test-key")

        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.execute_action()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg
