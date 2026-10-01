"""Keep plugin discovery and throwaway declarations isolated between project tests."""

import pytest
from lfx.projects import builtins, registry
from lfx.services.adapters.schema import AdapterType
from lfx.services.deps import get_settings_service


@pytest.fixture(autouse=True)
def isolated_project_registry(monkeypatch, tmp_path):
    declarations = registry._ProjectTypeRegistry(
        adapter_type=AdapterType.PROJECT_TYPE,
        entry_point_group=AdapterType.PROJECT_TYPE.entry_point_group,
        config_section_path=AdapterType.PROJECT_TYPE.config_section_path,
    )
    for definition in (
        builtins.FlowsType,
        builtins.AgentHarnessType,
        builtins.ToolPackType,
        builtins.SkillPackType,
        builtins.EvalSuiteType,
    ):
        declarations.register_class(definition.name, definition)
    monkeypatch.setattr(registry, "_PROJECT_TYPES", declarations)
    monkeypatch.setattr(registry, "_SLOT_DEFINITIONS", dict(registry._SLOT_DEFINITIONS))
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(tmp_path))
    return declarations
