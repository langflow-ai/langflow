"""Unit tests for TwelveLabs components cloud validation."""

import os
from unittest.mock import patch

import pytest
from lfx.components.twelvelabs.split_video import SplitVideoComponent
from lfx.components.twelvelabs.video_file import VideoFileComponent


@pytest.mark.unit
class TestTwelveLabsCloudValidation:
    """Test TwelveLabs components cloud validation."""

    def test_video_file_process_disabled_in_astra_cloud(self):
        """Test that VideoFile process_files raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = VideoFileComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process_files([])

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg

    def test_split_video_process_disabled_in_astra_cloud(self):
        """Test that SplitVideo process raises error in Astra Cloud."""
        with patch.dict(os.environ, {"ASTRA_CLOUD_DISABLE_COMPONENT": "true"}):
            component = SplitVideoComponent(api_key="test-key", index_id="test-index")

            with pytest.raises(ValueError, match=r".*") as exc_info:
                component.process()

            error_msg = str(exc_info.value).lower()
            assert "astra" in error_msg or "cloud" in error_msg
