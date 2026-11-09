import copy
import inspect
import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template, update_rebuilt_node
from lfx.schema.dotdict import dotdict

SEO_V1_11_6 = Path(__file__).parents[2] / "fixtures" / "starter_flows" / "v1.11.6" / "seo_keyword_generator.json"


async def test_update_rebuilt_node_keeps_saved_prompt_variables() -> None:
    flow = json.loads(SEO_V1_11_6.read_text(encoding="utf-8"))
    saved = next(node for node in flow["data"]["nodes"] if node["data"]["type"] == "Prompt")["data"]["node"]
    variables = saved["custom_fields"]["template"]
    assert variables
    assert all(saved["template"][name]["value"] for name in variables)
    code = Path(inspect.getsourcefile(PromptComponent)).read_text(encoding="utf-8")
    built, component = build_custom_component_template(Component(_code=code))
    assert not set(variables) & set(built["template"])

    updated = await update_rebuilt_node(component, built, copy.deepcopy(saved))

    assert {name: updated["template"][name]["value"] for name in variables} == {
        name: saved["template"][name]["value"] for name in variables
    }


def _refresh_node(value: object, field_type: str = "str") -> dict:
    return {
        "display_name": "Refresh component",
        "field_order": ["selection"],
        "outputs": [],
        "template": {
            "code": {"type": "code", "value": "rebuilt component source", "show": False},
            "selection": {"type": field_type, "value": value, "real_time_refresh": True},
        },
    }


@pytest.mark.parametrize("replacement_code", [None, {"type": "code", "value": "hook component source"}])
async def test_replacement_refresh_mapping_keeps_rebuilt_code(replacement_code: dict | None) -> None:
    class ReplacementConfigComponent(Component):
        async def update_build_config(self, build_config, field_value, field_name=None):
            assert field_name == "selection"
            assert field_value == "saved selection"
            result = dotdict(
                selection=build_config["selection"],
                generated={"type": "str", "value": "new default"},
            )
            if replacement_code is not None:
                result["code"] = replacement_code
            return result

    rebuilt = _refresh_node("new default")
    trusted_code = copy.deepcopy(rebuilt["template"]["code"])
    saved = _refresh_node("saved selection")
    saved["template"]["code"]["value"] = "saved component source"
    saved["template"]["generated"] = {"type": "str", "value": "saved generated value"}
    saved_before_update = copy.deepcopy(saved)
    warnings = []

    updated = await update_rebuilt_node(ReplacementConfigComponent(), rebuilt, saved, warnings=warnings)

    assert updated["template"]["code"] == trusted_code
    assert updated["template"]["generated"]["value"] == "saved generated value"
    assert saved == saved_before_update
    assert warnings == []


@pytest.mark.parametrize(("value", "field_type"), [(False, "bool"), (0, "int")])
async def test_synchronous_in_place_refresh_keeps_false_and_zero_values(value: object, field_type: str) -> None:
    calls = []

    class InPlaceConfigComponent(Component):
        def update_build_config(self, build_config, field_value, field_name=None):
            calls.append((field_name, field_value))
            build_config["generated"] = {"type": "str", "value": "new default"}

    rebuilt = _refresh_node(True if field_type == "bool" else 1, field_type)
    saved = _refresh_node(value, field_type)
    saved["template"]["generated"] = {"type": "str", "value": "saved generated value"}
    warnings = []

    updated = await update_rebuilt_node(InPlaceConfigComponent(), rebuilt, saved, warnings=warnings)

    assert calls == [("selection", value)]
    assert type(calls[0][1]) is type(value)
    assert updated["template"]["selection"]["value"] == value
    assert updated["template"]["generated"]["value"] == "saved generated value"
    assert warnings == []


async def test_inherited_refresh_hook_does_not_resolve_global_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    from lfx.interface.initialize import loading

    hydrate_globals = AsyncMock(side_effect=RuntimeError("Global variables are unavailable"))
    monkeypatch.setattr(loading, "update_params_with_load_from_db_fields", hydrate_globals)
    rebuilt = _refresh_node("new default")
    rebuilt["template"]["credential"] = {"type": "str", "value": "", "load_from_db": False}
    saved = _refresh_node("saved selection")
    saved["template"]["credential"] = {"type": "str", "value": "saved_variable", "load_from_db": True}
    warnings = []

    updated = await update_rebuilt_node(Component(), rebuilt, saved, warnings=warnings)

    hydrate_globals.assert_not_awaited()
    assert updated["template"]["selection"]["value"] == "saved selection"
    assert updated["template"]["credential"]["value"] == "saved_variable"
    assert updated["template"]["credential"]["load_from_db"] is True
    assert warnings == []


async def test_saved_refresh_flag_does_not_activate_a_current_static_field() -> None:
    calls = []

    class StaticConfigComponent(Component):
        def update_build_config(self, build_config, field_value, field_name=None):
            calls.append((build_config, field_value, field_name))

    rebuilt = _refresh_node("new default")
    rebuilt["template"]["selection"].pop("real_time_refresh")
    saved = _refresh_node("saved selection")
    warnings = []

    updated = await update_rebuilt_node(StaticConfigComponent(), rebuilt, saved, warnings=warnings)

    assert calls == []
    assert updated["template"]["selection"]["value"] == "saved selection"
    assert warnings == []


@pytest.mark.parametrize("collect_warnings", [False, True])
async def test_generic_refresh_failure_keeps_optional_warnings_outside_the_saved_node(
    *, collect_warnings: bool
) -> None:
    calls = []

    class UnavailableConfigComponent(Component):
        def update_build_config(self, build_config, field_value, field_name=None):
            calls.append((field_name, field_value))
            build_config["partial"] = {"type": "str", "value": "discarded hook mutation"}
            msg = "Configured service is unavailable"
            raise RuntimeError(msg)

    rebuilt = _refresh_node("new default")
    saved = _refresh_node("saved selection")
    warnings = [] if collect_warnings else None

    updated = await update_rebuilt_node(UnavailableConfigComponent(), rebuilt, saved, warnings=warnings)

    assert calls == [("selection", "saved selection")]
    assert updated["template"]["selection"]["value"] == "saved selection"
    assert "partial" not in updated["template"]
    assert "warnings" not in updated
    if collect_warnings:
        assert warnings == [
            {
                "code": "generated_fields_not_restored",
                "fields": [],
                "refresh_fields": ["selection"],
                "unverified": True,
                "inputs_unverified": True,
                "outputs_unverified": False,
            }
        ]


@pytest.mark.parametrize("collect_warnings", [False, True])
async def test_generic_refresh_does_not_swallow_wrapped_authorization_refusals(*, collect_warnings: bool) -> None:
    calls = []

    class DeniedConfigComponent(Component):
        def update_build_config(self, build_config, field_value, field_name=None):
            calls.append((field_name, field_value, build_config["selection"]["value"]))
            try:
                msg = "Configured service access denied"
                raise PermissionError(msg)
            except PermissionError as exc:
                msg = "Refresh failed"
                raise ValueError(msg) from exc

    warnings = [] if collect_warnings else None

    with pytest.raises(PermissionError, match="Configured service access denied"):
        await update_rebuilt_node(
            DeniedConfigComponent(), _refresh_node("new default"), _refresh_node("saved selection"), warnings=warnings
        )
    assert calls == [("selection", "saved selection", "saved selection")]
    if collect_warnings:
        assert warnings == []


@pytest.mark.parametrize("fallback", [False, True])
async def test_saved_refresh_honors_database_environment_fallback(monkeypatch, fallback):
    from contextlib import asynccontextmanager

    from lfx.interface.initialize import loading
    from lfx.services.deps import get_settings_service

    seen = []

    class RefreshComponent(Component):
        def update_build_config(self, build_config, field_value, field_name=None):  # noqa: ARG002
            seen.append(self.credential)
            build_config["selection"]["options"] = ["metadata refreshed"]
            return build_config

    @asynccontextmanager
    async def database_session():
        yield object()

    missing = AsyncMock(side_effect=ValueError("variable not found."))
    monkeypatch.setattr(RefreshComponent, "get_variable", missing)
    monkeypatch.setattr(loading, "session_scope", database_session)
    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "use_noop_database", False)
    monkeypatch.setattr(settings, "fallback_to_env_var", fallback)
    monkeypatch.setenv("UPGRADE_REPLAY_FIXTURE", "environment fixture value")
    rebuilt = _refresh_node("new default")
    rebuilt["template"]["credential"] = {"type": "str", "value": "", "load_from_db": False}
    saved = _refresh_node("saved selection")
    saved["template"]["credential"] = {"type": "str", "value": "UPGRADE_REPLAY_FIXTURE", "load_from_db": True}
    warnings = []
    updated = await update_rebuilt_node(RefreshComponent(), rebuilt, saved, warnings=warnings)
    assert seen == ["environment fixture value" if fallback else None]
    assert updated["template"]["selection"]["options"] == ["metadata refreshed"]
    assert updated["template"]["credential"]["value"] == "UPGRADE_REPLAY_FIXTURE"
    assert warnings == []
