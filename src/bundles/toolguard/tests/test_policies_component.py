import json
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace

from lfx.components.models_and_agents import PoliciesComponent as PackagePoliciesComponent
from lfx.components.models_and_agents.policies_component import PoliciesComponent as CompatibilityPoliciesComponent
from lfx_toolguard.components.models_and_agents.policies_component import PoliciesComponent


def test_compatibility_import_preserves_class_identity():
    assert CompatibilityPoliciesComponent is PoliciesComponent
    assert PackagePoliciesComponent is PoliciesComponent
    assert PoliciesComponent.__name__ == "PoliciesComponent"


def test_toolguard_manifest_contract():
    manifest_path = Path(__file__).parents[1] / "src" / "lfx_toolguard" / "extension.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["version"] == version("lfx-toolguard")
    assert manifest["bundles"] == [
        {"name": "toolguard", "path": "components/models_and_agents"},
    ]


def test_code_execution_denied_when_allow_custom_components_setting_is_missing(monkeypatch):
    settings_service = SimpleNamespace(settings=SimpleNamespace())
    monkeypatch.setattr("lfx.services.deps.get_settings_service", lambda: settings_service)

    assert PoliciesComponent._code_execution_allowed() is False
