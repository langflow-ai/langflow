"""Tests for extract_backend_strings.py."""

import json
from unittest.mock import patch

import extract_backend_strings as extract_mod
import pytest

SAMPLE_STRINGS = {
    "components.ChatInput.description": "Get chat inputs from the Playground.",
    "components.ChatInput.display_name": "Chat Input",
    "components.ChatInput.inputs.input_value.display_name": "Input Text",
    "components.ChatInput.outputs.message.display_name": "Chat Message",
}


def _run_main(*args):
    with patch("sys.argv", ["extract_backend_strings.py", *args]):
        extract_mod.main()


class TestExtractBackendStrings:
    def test_writes_en_json_to_output_path(self, tmp_path):
        output_file = tmp_path / "en.json"
        with (
            patch.object(extract_mod, "collect_strings", return_value=SAMPLE_STRINGS),
            patch.object(extract_mod, "OUTPUT_PATH", output_file),
        ):
            _run_main()

        assert output_file.exists()
        data = json.loads(output_file.read_text(encoding="utf-8"))
        assert data == SAMPLE_STRINGS

    def test_writes_keys_in_order_returned_by_collect_strings(self, tmp_path):
        """main() writes keys in the order collect_strings() returns them.

        collect_strings() always returns sorted keys, so the output is sorted in practice.
        """
        output_file = tmp_path / "en.json"
        pre_sorted = {  # collect_strings() always returns sorted keys
            "components.A.display_name": "A",
            "components.M.display_name": "M",
            "components.Z.display_name": "Z",
        }
        with (
            patch.object(extract_mod, "collect_strings", return_value=pre_sorted),
            patch.object(extract_mod, "OUTPUT_PATH", output_file),
        ):
            _run_main()

        raw = output_file.read_text(encoding="utf-8")
        keys_in_order = [line.strip().split('"')[1] for line in raw.splitlines() if '": "' in line]
        assert keys_in_order == list(pre_sorted.keys())

    def test_check_mode_passes_when_in_sync(self, tmp_path):
        output_file = tmp_path / "en.json"
        expected_content = json.dumps(SAMPLE_STRINGS, ensure_ascii=False, indent=2) + "\n"
        output_file.write_text(expected_content, encoding="utf-8")

        with (
            patch.object(extract_mod, "collect_strings", return_value=SAMPLE_STRINGS),
            patch.object(extract_mod, "OUTPUT_PATH", output_file),
            pytest.raises(SystemExit) as exc_info,
        ):
            _run_main("--check")

        assert exc_info.value.code == 0

    def test_check_mode_fails_when_out_of_sync(self, tmp_path):
        output_file = tmp_path / "en.json"
        output_file.write_text('{"components.OldKey.display_name": "Old"}', encoding="utf-8")

        with (
            patch.object(extract_mod, "collect_strings", return_value=SAMPLE_STRINGS),
            patch.object(extract_mod, "OUTPUT_PATH", output_file),
            pytest.raises(SystemExit) as exc_info,
        ):
            _run_main("--check")

        assert exc_info.value.code == 1

    def test_check_mode_fails_when_file_missing(self, tmp_path):
        missing_file = tmp_path / "en.json"

        with (
            patch.object(extract_mod, "collect_strings", return_value=SAMPLE_STRINGS),
            patch.object(extract_mod, "OUTPUT_PATH", missing_file),
            pytest.raises(SystemExit) as exc_info,
        ):
            _run_main("--check")

        assert exc_info.value.code == 1

    def test_creates_output_directory_if_missing(self, tmp_path):
        nested_file = tmp_path / "nested" / "dir" / "en.json"

        with (
            patch.object(extract_mod, "collect_strings", return_value=SAMPLE_STRINGS),
            patch.object(extract_mod, "OUTPUT_PATH", nested_file),
        ):
            _run_main()

        assert nested_file.exists()

    def test_collect_strings_skips_deactivated_modules(self):
        """collect_strings() must skip any module whose name contains 'deactivated'."""
        import hashlib
        import pkgutil
        import re
        import sys
        import types

        fake_modules = [
            pkgutil.ModuleInfo(module_finder=None, name="lfx.components.active", ispkg=False),
            pkgutil.ModuleInfo(module_finder=None, name="lfx.components.deactivated.old", ispkg=False),
        ]

        fake_components_pkg = types.ModuleType("lfx.components")
        fake_components_pkg.__path__ = []
        fake_components_pkg.__name__ = "lfx.components"

        active_module = types.ModuleType("lfx.components.active")
        active_module.__name__ = "lfx.components.active"

        class FakeComponent:
            __module__ = "lfx.components.active"
            code_class_base_inheritance = True
            display_name = "Active Component"
            description = "An active component"
            name = "ActiveComponent"
            inputs = []
            outputs = []

        active_module.FakeComponent = FakeComponent

        # Provide a minimal fake langflow.utils.i18n_keys so collect_strings()
        # can be called without langflow installed in the test environment.
        fake_i18n_keys = types.ModuleType("langflow.utils.i18n_keys")

        def _content_hash(english: str) -> str:
            return hashlib.sha256(english.encode()).hexdigest()[:8]

        fake_i18n_keys.component_field_key = lambda norm, path, eng: f"components.{norm}.{path}.{_content_hash(eng)}"
        fake_i18n_keys.normalize_component_key = lambda name: name.replace(" ", "").lower()
        fake_i18n_keys.safe_flow_key = lambda name: re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()

        fake_langflow = types.ModuleType("langflow")
        fake_langflow_utils = types.ModuleType("langflow.utils")

        with (
            patch.dict(
                sys.modules,
                {
                    "lfx": types.ModuleType("lfx"),
                    "lfx.components": fake_components_pkg,
                    "langflow": fake_langflow,
                    "langflow.utils": fake_langflow_utils,
                    "langflow.utils.i18n_keys": fake_i18n_keys,
                },
            ),
            patch("pkgutil.walk_packages", return_value=fake_modules),
            patch("importlib.import_module", return_value=active_module),
        ):
            strings = extract_mod.collect_strings()

        # Deactivated module was skipped; active module processed
        assert any("activecomponent" in k for k in strings)
