"""Tests for download_translations.py."""

import json
import sys
from unittest.mock import patch

import pytest


def _run_main(output_dir: str):
    """Helper to invoke download_translations.main() with an --output argument."""
    with patch("sys.argv", ["download_translations.py", "--output", output_dir]):
        import importlib

        import scripts.gp.download_translations as dl_mod  # noqa: PLC0415

        importlib.reload(dl_mod)
        dl_mod.main()


SAMPLE_RESPONSE = {
    "resourceStrings": {
        "hello": {"value": "Bonjour"},
        "bye": {"value": "Au revoir"},
    }
}


class TestDownloadTranslations:
    def test_writes_json_files_for_each_language(self, tmp_path):
        with (
            patch("scripts.gp.download_translations.get_strings", return_value=SAMPLE_RESPONSE),
            patch("scripts.gp.download_translations.TARGET_LANGS", ["fr", "es"]),
        ):
            _run_main(str(tmp_path))

        for lang in ["fr", "es"]:
            out = tmp_path / f"{lang}.json"
            assert out.exists()
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data == {"hello": "Bonjour", "bye": "Au revoir"}

    def test_skips_language_with_empty_strings(self, tmp_path):
        def _get_strings(lang):
            if lang == "ja":
                return {"resourceStrings": {}}
            return SAMPLE_RESPONSE

        with (
            patch("scripts.gp.download_translations.get_strings", side_effect=_get_strings),
            patch("scripts.gp.download_translations.TARGET_LANGS", ["fr", "ja"]),
        ):
            _run_main(str(tmp_path))

        assert (tmp_path / "fr.json").exists()
        assert not (tmp_path / "ja.json").exists()

    def test_exits_with_error_on_partial_failure(self, tmp_path):
        def _get_strings(lang):
            if lang == "de":
                raise ConnectionError("network error")
            return SAMPLE_RESPONSE

        with (
            patch("scripts.gp.download_translations.get_strings", side_effect=_get_strings),
            patch("scripts.gp.download_translations.TARGET_LANGS", ["fr", "de"]),
        ):
            with pytest.raises(SystemExit) as exc_info:
                _run_main(str(tmp_path))

        assert exc_info.value.code == 1
        # Successful language should still have been written
        assert (tmp_path / "fr.json").exists()

    def test_exits_cleanly_when_all_succeed(self, tmp_path):
        with (
            patch("scripts.gp.download_translations.get_strings", return_value=SAMPLE_RESPONSE),
            patch("scripts.gp.download_translations.TARGET_LANGS", ["fr"]),
        ):
            # Should not raise
            _run_main(str(tmp_path))

        assert (tmp_path / "fr.json").exists()

    def test_handles_flat_string_values_in_response(self, tmp_path):
        flat_response = {
            "resourceStrings": {
                "hello": "Hola",
                "bye": "Adiós",
            }
        }

        with (
            patch("scripts.gp.download_translations.get_strings", return_value=flat_response),
            patch("scripts.gp.download_translations.TARGET_LANGS", ["es"]),
        ):
            _run_main(str(tmp_path))

        data = json.loads((tmp_path / "es.json").read_text(encoding="utf-8"))
        assert data == {"hello": "Hola", "bye": "Adiós"}
