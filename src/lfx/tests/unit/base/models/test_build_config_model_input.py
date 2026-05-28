"""handle_model_input_update must honor the ModelInput string contract.

Bug (real user): the assistant built a flow whose Agent ``model`` was
configured as the bare string "gpt-5.4". On canvas mount the frontend
POSTs /custom_component/update for the model field; this function then
did ``field_value[0]["name"]`` on the string ("g"["name"]) and raised
``TypeError: string indices must be integers, not 'str'`` -> the
"Error while updating the Component" toast. ModelInput documents
"single string ... auto-converted to list", and
``normalize_model_names_to_dicts`` exists for exactly this — it was
just never called here.
"""

from __future__ import annotations

from lfx.base.models.unified_models.build_config import handle_model_input_update


class _Comp:
    user_id = None
    cache: dict = {}


def _no_options(user_id=None):  # noqa: ARG001
    return []


class TestHandleModelInputUpdateStringValue:
    def test_should_not_crash_and_should_normalize_when_model_value_is_a_bare_string(self):
        # Exactly the shape configure_component persisted from the LLM tool call.
        build_config = {"model": {"value": "gpt-5.4", "options": []}}

        result = handle_model_input_update(
            component=_Comp(),
            build_config=build_config,
            field_value="gpt-5.4",
            field_name="model",
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=_no_options,
        )

        value = result["model"]["value"]
        # Must be coerced to the list-of-dicts shape, never left a string.
        assert isinstance(value, list)
        assert value
        assert isinstance(value[0], dict)
        assert value[0]["name"] == "gpt-5.4"

    def test_should_leave_a_proper_list_of_dicts_value_working(self):
        proper = [{"name": "gpt-4o", "provider": "OpenAI"}]
        build_config = {"model": {"value": proper, "options": []}}

        result = handle_model_input_update(
            component=_Comp(),
            build_config=build_config,
            field_value=proper,
            field_name="model",
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=_no_options,
        )

        # The already-correct shape must not be mangled.
        assert isinstance(result["model"]["value"], list)
        assert result["model"]["value"][0]["name"] == "gpt-4o"

    def test_should_not_turn_an_empty_string_value_into_a_bogus_model(self):
        build_config = {"model": {"value": "", "options": []}}

        result = handle_model_input_update(
            component=_Comp(),
            build_config=build_config,
            field_value="",
            field_name="model",
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=_no_options,
        )

        # Empty stays empty (reset), NOT [{"name": ""}].
        assert result["model"]["value"] in ("", [])
