"""Tests for upload_strings.py."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest


def _run_main(source_path: str):
    """Helper to invoke upload_strings.main() with a --source argument."""
    with patch("sys.argv", ["upload_strings.py", "--source", source_path]):
        import importlib

        import scripts.gp.upload_strings as upload_mod  # noqa: PLC0415

        importlib.reload(upload_mod)
        upload_mod.main()


class TestUploadStrings:
    def test_uploads_strings_when_bundle_exists(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text(json.dumps({"hello": "Hello", "bye": "Bye"}), encoding="utf-8")

        with (
            patch("scripts.gp.upload_strings.list_bundles", return_value={"bundleIds": ["langflow-ui"]}),
            patch("scripts.gp.upload_strings.create_bundle") as mock_create,
            patch("scripts.gp.upload_strings.upload_strings") as mock_upload,
            patch("scripts.gp.upload_strings.GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_create.assert_not_called()
        mock_upload.assert_called_once_with({"hello": "Hello", "bye": "Bye"})

    def test_creates_bundle_when_missing_then_uploads(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text(json.dumps({"hello": "Hello"}), encoding="utf-8")

        with (
            patch("scripts.gp.upload_strings.list_bundles", return_value={"bundleIds": []}),
            patch("scripts.gp.upload_strings.create_bundle") as mock_create,
            patch("scripts.gp.upload_strings.upload_strings") as mock_upload,
            patch("scripts.gp.upload_strings.GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_create.assert_called_once()
        mock_upload.assert_called_once_with({"hello": "Hello"})

    def test_empty_json_file_uploads_empty_dict(self, tmp_path):
        source = tmp_path / "en.json"
        source.write_text("{}", encoding="utf-8")

        with (
            patch("scripts.gp.upload_strings.list_bundles", return_value={"bundleIds": ["langflow-ui"]}),
            patch("scripts.gp.upload_strings.create_bundle"),
            patch("scripts.gp.upload_strings.upload_strings") as mock_upload,
            patch("scripts.gp.upload_strings.GP_BUNDLE", "langflow-ui"),
        ):
            _run_main(str(source))

        mock_upload.assert_called_once_with({})

    def test_raises_when_source_file_missing(self, tmp_path):
        missing = str(tmp_path / "missing.json")

        with (
            patch("scripts.gp.upload_strings.list_bundles", return_value={"bundleIds": []}),
            patch("scripts.gp.upload_strings.create_bundle"),
            patch("scripts.gp.upload_strings.upload_strings"),
        ):
            with pytest.raises(FileNotFoundError):
                _run_main(missing)
