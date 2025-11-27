"""Unit tests for Mem0MemoryComponent cloud validation."""

import os
from unittest.mock import patch

import pytest
from lfx.components.mem0.mem0_chat_memory import Mem0MemoryComponent


@pytest.mark.unit
class TestMem0CloudValidation:
    """Test Mem0 component cloud validation."""

    def test_build_mem0_disabled_in_astra_cloud(self):
        """Test that build_mem0 raises an error when ASTRA_CLOUD_DISABLE_COMPONENT is true."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = Mem0MemoryComponent(openai_api_key="test-key")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.build_mem0()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    @patch("lfx.components.mem0.mem0_chat_memory.Memory")
    def test_build_mem0_works_when_not_in_cloud(self, mock_memory):
        """Test that build_mem0 works when ASTRA_CLOUD_DISABLE_COMPONENT is false."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "false"}):
            component = Mem0MemoryComponent(openai_api_key="test-key")
            component.build_mem0()
            mock_memory.assert_called_once()
