from unittest.mock import patch

import pytest
from lfx.base.data.base_file import BaseFileComponent
from lfx.components.twelvelabs.video_file import VideoFileComponent


def test_video_file_component_missing_file_no_silent_errors():
    component = VideoFileComponent()
    component.silent_errors = False

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        component.file_path = "/fake/path/missing.mp4"

        with patch.object(component, "log") as mock_log:
            with pytest.raises(FileNotFoundError):
                component.load_files()
            mock_log.assert_any_call("WARNING: Video file not found at path: /fake/path/missing.mp4")


def test_video_file_component_load_files_silent_errors():
    component = VideoFileComponent()
    component.silent_errors = True

    with patch("pathlib.Path.exists") as mock_exists:
        mock_exists.return_value = False
        component.file_path = "/fake/path/missing.mp4"

        with patch.object(component, "log") as mock_log:
            component.load_files()
            mock_log.assert_any_call("WARNING: Video file not found at path: /fake/path/missing.mp4")


class TestFileComponent(BaseFileComponent):
    """Test implementation of BaseFileComponent for testing."""

    VALID_EXTENSIONS = ["txt", "json", "csv"]

    def process_files(self, file_list):
        return file_list
