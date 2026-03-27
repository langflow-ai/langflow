"""Tests for upload_strings.py."""

import json
from unittest.mock import patch

import pytest

import upload_strings as upload_mod


def _run_main(source_path: str):
    with patch("sys.argv", ["upload_strings.py", "--source", source_path]):
        upload_mod.main()


class TestUploadStrings:
    def test_uploads_strings_when_bundle_exists(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text(json.dumps({"hello": "Hello", "bye": "Bye"}), encoding="utf-8")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": ["langflow-ui"]}),
            patch.object(upload_mod, "create_bundle") as mock_create,
            patch.object(upload_mod, "upload_strings") as mock_upload,
            patch.object(upload_mod, "GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_create.assert_not_called()
        mock_upload.assert_called_once_with({"hello": "Hello", "bye": "Bye"})

    def test_creates_bundle_when_missing_then_uploads(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text(json.dumps({"hello": "Hello"}), encoding="utf-8")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": []}),
            patch.object(upload_mod, "create_bundle") as mock_create,
            patch.object(upload_mod, "upload_strings") as mock_upload,
            patch.object(upload_mod, "GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_create.assert_called_once()
        mock_upload.assert_called_once_with({"hello": "Hello"})

    def test_empty_json_file_uploads_empty_dict(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text("{}", encoding="utf-8")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": ["langflow-ui"]}),
            patch.object(upload_mod, "create_bundle"),
            patch.object(upload_mod, "upload_strings") as mock_upload,
            patch.object(upload_mod, "GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_upload.assert_called_once_with({})

    def test_raises_when_source_file_missing(self, tmp_path):
        missing = str(tmp_path / "missing.json")

        with (
            patch.object(upload_mod, "list_bundles", return_value={"bundleIds": []}),
            patch.object(upload_mod, "create_bundle"),
            patch.object(upload_mod, "upload_strings"),
            pytest.raises(FileNotFoundError),
        ):
            _run_main(missing)
