"""Tests for upload_backend_strings.py."""

import json
from unittest.mock import patch

import pytest
import upload_backend_strings as upload_mod


def _run_main(source_path: str):
    with patch("sys.argv", ["upload_backend_strings.py", "--source", source_path]):
        upload_mod.main()


class TestUploadBackendStrings:
    def test_uploads_when_bundle_exists(self, tmp_path):
        source = tmp_path / "en.json"
        strings = {"components.ChatInput.display_name": "Chat Input"}
        source.write_text(json.dumps(strings), encoding="utf-8")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": ["langflow-backend"]}),
            patch.object(upload_mod, "create_backend_bundle") as mock_create,
            patch.object(upload_mod, "upload_backend_strings") as mock_upload,
            patch.object(upload_mod, "GP_BACKEND_BUNDLE", "langflow-backend"),
        ):
            _run_main(str(source))

        mock_create.assert_not_called()
        mock_upload.assert_called_once_with(strings)

    def test_creates_bundle_when_missing_then_uploads(self, tmp_path):
        source = tmp_path / "en.json"
        strings = {"components.ChatInput.display_name": "Chat Input"}
        source.write_text(json.dumps(strings), encoding="utf-8")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": []}),
            patch.object(upload_mod, "create_backend_bundle") as mock_create,
            patch.object(upload_mod, "upload_backend_strings") as mock_upload,
            patch.object(upload_mod, "GP_BACKEND_BUNDLE", "langflow-backend"),
        ):
            _run_main(str(source))

        mock_create.assert_called_once()
        mock_upload.assert_called_once_with(strings)

    def test_exits_when_source_file_missing(self, tmp_path):
        missing = str(tmp_path / "missing.json")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": []}),
            patch.object(upload_mod, "create_backend_bundle"),
            patch.object(upload_mod, "upload_backend_strings"),
            pytest.raises(SystemExit) as exc_info,
        ):
            _run_main(missing)

        assert exc_info.value.code == 1

    def test_uploads_all_strings_from_file(self, tmp_path):
        source = tmp_path / "en.json"
        strings = {
            "components.ChatInput.display_name": "Chat Input",
            "components.ChatInput.description": "Get chat inputs.",
            "components.ChatInput.inputs.message.display_name": "Message",
        }
        source.write_text(json.dumps(strings), encoding="utf-8")

        captured = {}

        def _capture_upload(s):
            captured.update(s)
            return {}

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": ["langflow-backend"]}),
            patch.object(upload_mod, "create_backend_bundle"),
            patch.object(upload_mod, "upload_backend_strings", side_effect=_capture_upload),
            patch.object(upload_mod, "GP_BACKEND_BUNDLE", "langflow-backend"),
        ):
            _run_main(str(source))

        assert captured == strings
