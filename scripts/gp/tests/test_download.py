"""Tests for download.py."""

import json
from unittest.mock import patch

import download as dl_mod
import pytest


def _run_frontend(output_dir: str):
    with patch("sys.argv", ["download.py", "--target", "frontend", "--output", output_dir]):
        dl_mod.main()


def _run_backend(output_dir: str):
    with patch("sys.argv", ["download.py", "--target", "backend", "--output", output_dir]):
        dl_mod.main()


FRONTEND_SAMPLE_RESPONSE = {
    "resourceStrings": {
        "hello": {"value": "Bonjour"},
        "bye": {"value": "Au revoir"},
    }
}

BACKEND_SAMPLE_RESPONSE = {
    "resourceStrings": {
        "components.ChatInput.display_name": {"value": "Entrée de chat"},
        "components.ChatInput.description": {"value": "Obtenir les entrées de chat"},
    }
}


class TestDownloadFrontend:
    def test_writes_json_files_for_each_language(self, tmp_path):
        with (
            patch.object(dl_mod, "get_strings", return_value=FRONTEND_SAMPLE_RESPONSE),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "es"]),
        ):
            _run_frontend(str(tmp_path))

        for lang in ["fr", "es"]:
            out = tmp_path / f"{lang}.json"
            assert out.exists()
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data == {"hello": "Bonjour", "bye": "Au revoir"}

    def test_skips_language_with_empty_strings(self, tmp_path):
        def _get_strings(lang):
            if lang == "ja":
                return {"resourceStrings": {}}
            return FRONTEND_SAMPLE_RESPONSE

        with (
            patch.object(dl_mod, "get_strings", side_effect=_get_strings),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "ja"]),
        ):
            _run_frontend(str(tmp_path))

        assert (tmp_path / "fr.json").exists()
        assert not (tmp_path / "ja.json").exists()

    def test_exits_with_error_on_partial_failure(self, tmp_path):
        def _get_strings(lang):
            if lang == "de":
                raise ConnectionError("network error")
            return FRONTEND_SAMPLE_RESPONSE

        with (
            patch.object(dl_mod, "get_strings", side_effect=_get_strings),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "de"]),
            pytest.raises(SystemExit) as exc_info,
        ):
            _run_frontend(str(tmp_path))

        assert exc_info.value.code == 1
        assert (tmp_path / "fr.json").exists()

    def test_exits_cleanly_when_all_succeed(self, tmp_path):
        with (
            patch.object(dl_mod, "get_strings", return_value=FRONTEND_SAMPLE_RESPONSE),
            patch.object(dl_mod, "TARGET_LANGS", ["fr"]),
        ):
            _run_frontend(str(tmp_path))

        assert (tmp_path / "fr.json").exists()

    def test_handles_flat_string_values_in_response(self, tmp_path):
        flat_response = {
            "resourceStrings": {
                "hello": "Hola",
                "bye": "Adiós",
            }
        }

        with (
            patch.object(dl_mod, "get_strings", return_value=flat_response),
            patch.object(dl_mod, "TARGET_LANGS", ["es"]),
        ):
            _run_frontend(str(tmp_path))

        data = json.loads((tmp_path / "es.json").read_text(encoding="utf-8"))
        assert data == {"hello": "Hola", "bye": "Adiós"}


class TestDownloadBackend:
    def test_writes_json_files_for_each_language(self, tmp_path):
        with (
            patch.object(dl_mod, "get_backend_strings", return_value=BACKEND_SAMPLE_RESPONSE),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "es"]),
        ):
            _run_backend(str(tmp_path))

        for lang in ["fr", "es"]:
            out = tmp_path / f"{lang}.json"
            assert out.exists()
            data = json.loads(out.read_text(encoding="utf-8"))
            assert data == {
                "components.ChatInput.display_name": "Entrée de chat",
                "components.ChatInput.description": "Obtenir les entrées de chat",
            }

    def test_skips_language_with_empty_strings(self, tmp_path):
        def _get_backend_strings(lang):
            if lang == "ja":
                return {"resourceStrings": {}}
            return BACKEND_SAMPLE_RESPONSE

        with (
            patch.object(dl_mod, "get_backend_strings", side_effect=_get_backend_strings),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "ja"]),
        ):
            _run_backend(str(tmp_path))

        assert (tmp_path / "fr.json").exists()
        assert not (tmp_path / "ja.json").exists()

    def test_continues_after_language_error(self, tmp_path):
        """Backend download catches errors per-language and continues (no sys.exit)."""

        def _get_backend_strings(lang):
            if lang == "de":
                raise ConnectionError("network error")
            return BACKEND_SAMPLE_RESPONSE

        with (
            patch.object(dl_mod, "get_backend_strings", side_effect=_get_backend_strings),
            patch.object(dl_mod, "TARGET_LANGS", ["fr", "de"]),
        ):
            _run_backend(str(tmp_path))  # should NOT raise

        assert (tmp_path / "fr.json").exists()
        assert not (tmp_path / "de.json").exists()

    def test_creates_output_directory_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "locales"
        with (
            patch.object(dl_mod, "get_backend_strings", return_value=BACKEND_SAMPLE_RESPONSE),
            patch.object(dl_mod, "TARGET_LANGS", ["fr"]),
        ):
            _run_backend(str(nested))

        assert nested.is_dir()
        assert (nested / "fr.json").exists()

    def test_handles_flat_string_values_in_response(self, tmp_path):
        flat_response = {
            "resourceStrings": {
                "components.ChatInput.display_name": "Eingabe",
            }
        }

        with (
            patch.object(dl_mod, "get_backend_strings", return_value=flat_response),
            patch.object(dl_mod, "TARGET_LANGS", ["de"]),
        ):
            _run_backend(str(tmp_path))

        data = json.loads((tmp_path / "de.json").read_text(encoding="utf-8"))
        assert data == {"components.ChatInput.display_name": "Eingabe"}

    def test_attempts_all_target_languages(self, tmp_path):
        called_langs = []

        def _get_backend_strings(lang):
            called_langs.append(lang)
            return BACKEND_SAMPLE_RESPONSE

        all_langs = ["fr", "ja", "es", "de", "pt", "zh-Hans"]
        with (
            patch.object(dl_mod, "get_backend_strings", side_effect=_get_backend_strings),
            patch.object(dl_mod, "TARGET_LANGS", all_langs),
        ):
            _run_backend(str(tmp_path))

        assert called_langs == all_langs
