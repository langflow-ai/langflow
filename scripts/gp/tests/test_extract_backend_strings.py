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


# ---------------------------------------------------------------------------
# Installed extension bundles
# ---------------------------------------------------------------------------


def _fake_i18n_key_helpers():
    """Return the real key-shape helpers without needing langflow installed."""
    import hashlib
    import re
    import types

    module = types.ModuleType("langflow.utils.i18n_keys")

    def _content_hash(english: str) -> str:
        return hashlib.sha256(english.encode()).hexdigest()[:8]

    module.component_field_key = lambda norm, path, eng: f"components.{norm}.{path}.{_content_hash(eng)}"
    module.normalize_component_key = lambda name: name.replace(" ", "").lower()
    module.safe_flow_key = lambda name: re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower()
    return module


class _FakeInput:
    def __init__(self, name, display_name=None, info=None, placeholder=None):
        self.name = name
        self.display_name = display_name
        self.info = info
        self.placeholder = placeholder


class _FakeOutput:
    def __init__(self, name, display_name=None, info=None):
        self.name = name
        self.display_name = display_name
        self.info = info


class BundleFixtureComponent:
    """Stands in for a component that only exists inside an installed bundle.

    Its ``__module__`` is the loader's synthetic ``_lfx_ext.official.<bundle>``
    namespace, which is exactly why the ``lfx.components`` walk can never see
    it: nothing under ``lfx/components/`` declares it.
    """

    __module__ = "_lfx_ext.official.fixture.widget"
    code_class_base_inheritance = True
    name = "FixtureWidget"
    display_name = "Fixture Widget"
    description = "A component that ships inside an installed extension bundle."
    inputs = (_FakeInput("token", display_name="Token", info="The token to use.", placeholder="paste here"),)
    outputs = (_FakeOutput("result", display_name="Result", info="What came back."),)


class _FakeLoadedComponent:
    def __init__(self, bundle, klass):
        self.bundle = bundle
        self.klass = klass


class _FakeLoadResult:
    def __init__(self, distribution, extension_id, components, errors=()):
        self.distribution = distribution
        self.extension_id = extension_id
        self.components = components
        self.errors = list(errors)


def _install_fake_extension_system(monkeypatch, results):
    """Register a fake ``lfx.extension`` exposing ``load_installed_extensions``."""
    import sys
    import types

    fake_extension = types.ModuleType("lfx.extension")
    fake_extension.load_installed_extensions = lambda: results
    fake_lfx = sys.modules.get("lfx") or types.ModuleType("lfx")
    monkeypatch.setitem(sys.modules, "lfx", fake_lfx)
    monkeypatch.setitem(sys.modules, "lfx.extension", fake_extension)


class TestInstalledBundleWalk:
    def test_yields_component_classes_from_installed_extensions(self, monkeypatch):
        results = [
            _FakeLoadResult(
                "lfx-fixture",
                "lfx-fixture",
                [_FakeLoadedComponent("fixture", BundleFixtureComponent)],
            )
        ]
        _install_fake_extension_system(monkeypatch, results)

        assert list(extract_mod.iter_installed_bundle_classes()) == [("fixture", BundleFixtureComponent)]

    def test_skips_non_class_entries(self, monkeypatch):
        results = [_FakeLoadResult("lfx-fixture", "lfx-fixture", [_FakeLoadedComponent("fixture", None)])]
        _install_fake_extension_system(monkeypatch, results)

        assert list(extract_mod.iter_installed_bundle_classes()) == []

    def test_load_failure_is_reported_not_raised(self, monkeypatch, capsys):
        import sys
        import types

        def _boom():
            msg = "site-packages is on fire"
            raise RuntimeError(msg)

        fake_extension = types.ModuleType("lfx.extension")
        fake_extension.load_installed_extensions = _boom
        monkeypatch.setitem(sys.modules, "lfx", sys.modules.get("lfx") or types.ModuleType("lfx"))
        monkeypatch.setitem(sys.modules, "lfx.extension", fake_extension)

        assert list(extract_mod.iter_installed_bundle_classes()) == []
        assert "SKIP installed extension bundles" in capsys.readouterr().out

    def test_bundle_component_keys_use_the_same_format_as_core_components(self, monkeypatch):
        """A bundle component and a core component are keyed by identical rules.

        This is the churn guard: the hand-written INT-11 rows were produced with
        these helpers, so generating them from the bundle walk must reproduce the
        same hash-suffixed keys rather than a second, parallel set.
        """
        helpers = _fake_i18n_key_helpers()

        from_core: dict[str, str] = {}
        extract_mod.emit_component_strings(
            BundleFixtureComponent,
            from_core,
            set(),
            component_field_key=helpers.component_field_key,
            normalize_component_key=helpers.normalize_component_key,
        )

        results = [
            _FakeLoadResult(
                "lfx-fixture",
                "lfx-fixture",
                [_FakeLoadedComponent("fixture", BundleFixtureComponent)],
            )
        ]
        _install_fake_extension_system(monkeypatch, results)
        from_bundle: dict[str, str] = {}
        for _bundle, klass in extract_mod.iter_installed_bundle_classes():
            extract_mod.emit_component_strings(
                klass,
                from_bundle,
                set(),
                component_field_key=helpers.component_field_key,
                normalize_component_key=helpers.normalize_component_key,
            )

        assert from_bundle == from_core
        assert from_bundle == {
            "components.fixturewidget.display_name.62b5f139": "Fixture Widget",
            "components.fixturewidget.description.8109bea8": (
                "A component that ships inside an installed extension bundle."
            ),
            "components.fixturewidget.inputs.token.display_name.d2089be6": "Token",
            "components.fixturewidget.inputs.token.info.0b4751b6": "The token to use.",
            "components.fixturewidget.inputs.token.placeholder.01effd0c": "paste here",
            "components.fixturewidget.outputs.result.display_name.6e7d50e8": "Result",
            "components.fixturewidget.outputs.result.info.2b498ccb": "What came back.",
        }

    def test_component_claimed_by_the_core_walk_is_not_emitted_twice(self):
        """A shimmed bundle component reaches both walks; it must key once."""
        helpers = _fake_i18n_key_helpers()
        flat: dict[str, str] = {}
        seen: set[str] = set()

        assert extract_mod.emit_component_strings(
            BundleFixtureComponent,
            flat,
            seen,
            component_field_key=helpers.component_field_key,
            normalize_component_key=helpers.normalize_component_key,
        )
        first = dict(flat)
        assert not extract_mod.emit_component_strings(
            BundleFixtureComponent,
            flat,
            seen,
            component_field_key=helpers.component_field_key,
            normalize_component_key=helpers.normalize_component_key,
        )
        assert flat == first

    def test_class_without_the_component_marker_is_skipped(self):
        helpers = _fake_i18n_key_helpers()

        class NotAComponent:
            display_name = "Not A Component"

        flat: dict[str, str] = {}
        assert not extract_mod.emit_component_strings(
            NotAComponent,
            flat,
            set(),
            component_field_key=helpers.component_field_key,
            normalize_component_key=helpers.normalize_component_key,
        )
        assert flat == {}


class TestCollectStringsWithBundles:
    """End-to-end over collect_strings(), with both component sources faked."""

    @staticmethod
    def _patched(monkeypatch, tmp_path, bundle_results):
        import importlib
        import pkgutil
        import sys
        import types

        class CoreComponent:
            __module__ = "lfx.components.active"
            code_class_base_inheritance = True
            name = "CoreThing"
            display_name = "Core Thing"
            description = "In-tree component."
            inputs = ()
            outputs = ()

        active_module = types.ModuleType("lfx.components.active")
        active_module.__name__ = "lfx.components.active"
        active_module.CoreComponent = CoreComponent

        fake_components_pkg = types.ModuleType("lfx.components")
        fake_components_pkg.__path__ = []

        fake_langflow = types.ModuleType("langflow")
        fake_langflow_utils = types.ModuleType("langflow.utils")
        fake_extension = types.ModuleType("lfx.extension")
        fake_extension.load_installed_extensions = lambda: bundle_results

        monkeypatch.setitem(sys.modules, "lfx", types.ModuleType("lfx"))
        monkeypatch.setitem(sys.modules, "lfx.components", fake_components_pkg)
        monkeypatch.setitem(sys.modules, "lfx.extension", fake_extension)
        monkeypatch.setitem(sys.modules, "langflow", fake_langflow)
        monkeypatch.setitem(sys.modules, "langflow.utils", fake_langflow_utils)
        monkeypatch.setitem(sys.modules, "langflow.utils.i18n_keys", _fake_i18n_key_helpers())
        monkeypatch.setattr(
            pkgutil,
            "walk_packages",
            lambda *_a, **_k: [pkgutil.ModuleInfo(module_finder=None, name="lfx.components.active", ispkg=False)],
        )
        # Route only the faked module name; everything else keeps the real
        # importer, or mock.patch's own sys.argv lookup inside main() breaks.
        real_import_module = importlib.import_module

        def _import_module(name, *args, **kwargs):
            if name == "lfx.components.active":
                return active_module
            return real_import_module(name, *args, **kwargs)

        monkeypatch.setattr(extract_mod.importlib, "import_module", _import_module)
        # An empty starter-projects dir keeps tiers 3 and 4 out of the assertion.
        monkeypatch.setattr(extract_mod, "STARTER_PROJECTS_DIR", tmp_path / "starters")
        (tmp_path / "starters").mkdir()

    def test_bundle_components_reach_en_json(self, monkeypatch, tmp_path):
        results = [
            _FakeLoadResult(
                "lfx-fixture",
                "lfx-fixture",
                [_FakeLoadedComponent("fixture", BundleFixtureComponent)],
            )
        ]
        self._patched(monkeypatch, tmp_path, results)

        strings = extract_mod.collect_strings()

        assert any(k.startswith("components.corething.") for k in strings)
        assert strings["components.fixturewidget.display_name.62b5f139"] == "Fixture Widget"
        assert sorted(strings) == list(strings), "collect_strings() must return sorted keys"

    def test_check_is_stable_immediately_after_a_run(self, monkeypatch, tmp_path):
        """Write en.json, then --check must exit 0 without a second write."""
        results = [
            _FakeLoadResult(
                "lfx-fixture",
                "lfx-fixture",
                [_FakeLoadedComponent("fixture", BundleFixtureComponent)],
            )
        ]
        self._patched(monkeypatch, tmp_path, results)
        output_file = tmp_path / "en.json"
        monkeypatch.setattr(extract_mod, "OUTPUT_PATH", output_file)

        _run_main()
        written = output_file.read_text(encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            _run_main("--check")
        assert exc_info.value.code == 0
        assert output_file.read_text(encoding="utf-8") == written

    def test_check_fails_when_a_bundle_component_is_missing_from_en_json(self, monkeypatch, tmp_path):
        """The regression the bot hit: bundle rows absent from en.json must fail --check."""
        results = [
            _FakeLoadResult(
                "lfx-fixture",
                "lfx-fixture",
                [_FakeLoadedComponent("fixture", BundleFixtureComponent)],
            )
        ]
        self._patched(monkeypatch, tmp_path, results)
        output_file = tmp_path / "en.json"
        monkeypatch.setattr(extract_mod, "OUTPUT_PATH", output_file)

        _run_main()
        stripped = {k: v for k, v in json.loads(output_file.read_text()).items() if "fixturewidget" not in k}
        output_file.write_text(json.dumps(stripped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        with pytest.raises(SystemExit) as exc_info:
            _run_main("--check")
        assert exc_info.value.code == 1
