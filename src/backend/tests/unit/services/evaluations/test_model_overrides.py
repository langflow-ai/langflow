import copy

import pytest
from langflow.services.evaluations.errors import EvalsValidationError
from langflow.services.evaluations.flow_checks import check_flow
from langflow.services.evaluations.model_overrides import apply_model_overrides, model_fields, require_models
from langflow.services.evaluations.schemas import ModelOverride
from pydantic import ValidationError

GPT = [{"name": "gpt-4o", "provider": "OpenAI", "metadata": {}}]
MINI = [{"name": "gpt-4o-mini", "provider": "OpenAI", "metadata": {}}]


def _node(node_id: str, template: dict, display_name: str = "Agent") -> dict:
    return {
        "id": node_id,
        "type": "genericNode",
        "data": {
            "id": node_id,
            "type": node_id.split("-")[0],
            "node": {"display_name": display_name, "template": template},
        },
    }


def _flow() -> dict:
    return {
        "nodes": [
            _node("Agent-1", {"model": {"type": "model", "display_name": "Language Model", "value": GPT}}),
            _node(
                "Embed-1",
                {"model": {"type": "model", "display_name": "Embedding", "model_type": "embedding", "value": GPT}},
                "Embedding Model",
            ),
            _node("Wired-1", {"model": {"type": "model", "value": GPT}}, "Wired"),
            _node("Empty-1", {"model": {"type": "model", "value": None}}, "Empty"),
            _node("Prompt-1", {"template": {"type": "str", "value": "hi"}}, "Prompt"),
        ],
        "edges": [
            {
                "source": "Model-9",
                "target": "Wired-1",
                "data": {"targetHandle": {"id": "Wired-1", "fieldName": "model"}},
            }
        ],
    }


class TestModelFields:
    def test_should_list_selected_model_pickers_but_not_wired_or_empty_ones(self):
        fields = model_fields(_flow())

        assert [(f.node_id, f.field, f.model_type) for f in fields] == [
            ("Agent-1", "model", "language"),
            ("Embed-1", "model", "embedding"),
        ]
        assert fields[0].component == "Agent"
        assert fields[0].value == GPT

    def test_should_report_the_pickers_in_the_flow_check(self):
        report = check_flow(_flow())

        assert [picker.node_id for picker in report.model_pickers] == ["Agent-1", "Embed-1"]


def _two_agents_one_unset() -> dict:
    return {
        "nodes": [
            _node("Agent-1", {"model": {"type": "model", "display_name": "Language Model", "value": GPT}}),
            _node(
                "Agent-2", {"model": {"type": "model", "display_name": "Language Model", "value": [], "required": True}}
            ),
            _node(
                "Model-1",
                {"model": {"type": "model", "display_name": "Language Model", "value": GPT}},
                "Language Model",
            ),
        ],
        "edges": [],
    }


class TestUnsetModelFields:
    def test_should_list_a_required_picker_saved_without_a_model(self):
        fields = model_fields(_two_agents_one_unset())

        assert [(f.node_id, f.value) for f in fields] == [("Agent-1", GPT), ("Agent-2", []), ("Model-1", GPT)]

    def test_should_number_components_that_share_a_name(self):
        fields = model_fields(_two_agents_one_unset())

        assert [f.component for f in fields] == ["Agent (1)", "Agent (2)", "Language Model"]

    def test_should_refuse_a_run_that_leaves_a_required_picker_empty(self):
        with pytest.raises(EvalsValidationError, match=r"Agent \(2\) \(Language Model\)"):
            require_models(_two_agents_one_unset())

    def test_should_run_once_an_override_fills_the_empty_picker(self):
        filled = apply_model_overrides(
            _two_agents_one_unset(), [ModelOverride(node_id="Agent-2", field="model", value=MINI)]
        )

        require_models(filled)
        assert filled["nodes"][1]["data"]["node"]["template"]["model"]["value"] == MINI


class TestApplyModelOverrides:
    def test_should_swap_the_model_on_a_copy_and_leave_the_flow_untouched(self):
        flow = _flow()
        original = copy.deepcopy(flow)

        patched = apply_model_overrides(flow, [ModelOverride(node_id="Agent-1", field="model", value=MINI)])

        assert patched["nodes"][0]["data"]["node"]["template"]["model"]["value"] == MINI
        assert patched["nodes"][1]["data"]["node"]["template"]["model"]["value"] == GPT
        assert flow == original

    def test_should_accept_stored_overrides_as_dicts(self):
        patched = apply_model_overrides(_flow(), [{"node_id": "Agent-1", "field": "model", "value": MINI}])

        assert patched["nodes"][0]["data"]["node"]["template"]["model"]["value"] == MINI

    def test_should_return_the_same_flow_without_overrides(self):
        flow = _flow()

        assert apply_model_overrides(flow, []) is flow

    @pytest.mark.parametrize(
        ("node_id", "field"),
        [("Missing-1", "model"), ("Prompt-1", "template"), ("Wired-1", "model")],
    )
    def test_should_refuse_an_override_for_a_field_that_is_not_a_free_model_picker(self, node_id, field):
        with pytest.raises(EvalsValidationError, match="not in this flow version"):
            apply_model_overrides(_flow(), [ModelOverride(node_id=node_id, field=field, value=MINI)])


class TestModelOverrideSchema:
    def test_should_require_a_model_name_and_provider(self):
        with pytest.raises(ValidationError, match="model name and provider"):
            ModelOverride(node_id="Agent-1", field="model", value=[{"name": "gpt-4o"}])

    def test_should_take_exactly_one_model(self):
        with pytest.raises(ValidationError):
            ModelOverride(node_id="Agent-1", field="model", value=[])
        with pytest.raises(ValidationError):
            ModelOverride(node_id="Agent-1", field="model", value=GPT + MINI)
