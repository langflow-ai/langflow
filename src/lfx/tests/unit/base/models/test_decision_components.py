"""Decision Model component discovery and the shared execution contract."""

import pytest
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionResult
from lfx.components.llm_operations import decision_model as component_module
from lfx.components.llm_operations.decision_model import DecisionModelComponent
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.utils import create_component_template
from lfx.schema.data import Data


def test_component_template_discoverable():
    component_class = DecisionModelComponent
    component = component_class()
    template, _ = create_component_template(
        component_extractor=component,
        module_name=f"{component_class.__module__}.{component_class.__name__}",
    )
    assert template["display_name"] == component_class.display_name
    assert template["template"]["kind"]["options"] == ["Choice", "Boolean", "Score"]
    assert template["template"]["model"]["model_type"] == "decision"
    assert template["outputs"][0]["types"] == ["JSON"]
    restored = eval_custom_component_code(template["template"]["code"]["value"])()
    assert restored.name == component.name


@pytest.mark.parametrize("kind", ["Choice", "Boolean", "Score"])
def test_component_preserves_evidence_and_executes_once(kind, monkeypatch):
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "model"}],
        kind=kind,
        context="sensitive context",
        question="What applies?",
        candidates=[{"id": "a", "label": "Low"}, {"id": "b", "label": "High"}],
        timeout=30,
    )
    calls = []

    def evaluate(request, **kwargs):
        calls.append((request, kwargs))
        fields = (
            {"probability_true": 0.3}
            if kind == "Boolean"
            else {
                "probabilities": {"a": 0.3, "b": 0.7},
                "confidence": 0.25,
                "selected_option": "b" if kind == "Choice" else None,
                "score": 0.7 if kind == "Score" else None,
            }
        )
        return DecisionResult(kind=kind.lower(), provider="TypeSafe", model="actual-model", **fields)

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    result = component.evaluate()
    assert len(calls) == 1
    request, kwargs = calls[0]
    assert request.context == "sensitive context"
    assert kwargs["timeout"] == 30
    assert result.data["model"] == "actual-model"
    assert "context" not in result.data["request"]
    assert result.data["request"]["kind"] == kind.lower()


def test_packaged_index_preserves_decision_component_sources():
    import hashlib
    from importlib.resources import files

    import orjson

    blob = orjson.loads(files("lfx").joinpath("_assets/component_index.json").read_bytes())
    signature = blob.pop("sha256")
    assert hashlib.sha256(orjson.dumps(blob, option=orjson.OPT_SORT_KEYS)).hexdigest() == signature
    components = dict(blob["entries"])["llm_operations"]
    assert not {"TypeSafeDecision", "PerplexityDecision", "OpenAIDecision"} & components.keys()
    template = components[DecisionModelComponent.name]
    assert template["template"]["model"]["model_type"] == "decision"
    restored = eval_custom_component_code(template["template"]["code"]["value"])()
    assert restored.name == DecisionModelComponent.name
    restored.set(context="Old text", structured_context=Data(data={}))
    with pytest.raises(DecisionConfigurationError, match="Structured Context is empty"):
        restored._context()


def test_components_do_not_import_provider_sdks():
    import subprocess
    import sys

    script = """
import importlib.abc
import sys
class NoProviderSDKs(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path, target=None):
        if fullname.split('.')[0] in {'openai', 'perplexity', 'typesafe', 'langchain_openai', 'langchain_perplexity'}:
            raise AssertionError(f'Unexpected provider SDK import: {fullname}')
sys.meta_path.insert(0, NoProviderSDKs())
from lfx.components.llm_operations import DecisionModelComponent
assert DecisionModelComponent().name
"""
    subprocess.run(  # noqa: S603 - fixed local interpreter and literal SDK-isolation check
        [sys.executable, "-c", script], check=True, capture_output=True, timeout=60
    )


def test_row_added_in_the_editor_accepts_blank_description(monkeypatch):
    """The editor fills a new row's cells with each column's default, or null when it has none."""
    component = DecisionModelComponent()
    columns = next(item for item in component.inputs if item.name == "candidates").table_schema
    rows = []
    for row_id, label in (("a", "Low"), ("b", "High")):
        row = {column["name"]: column.get("default") for column in columns}
        row.update(id=row_id, label=label)
        rows.append(row)
    component.set(
        model=[{"provider": "TypeSafe", "name": "model"}],
        kind="Choice",
        context="text",
        question="Which applies?",
        candidates=rows,
    )
    captured = []

    def evaluate(request, **_kwargs):
        captured.append(request)
        return DecisionResult(kind="choice", provider="TypeSafe", model="m", probabilities={"a": 0.4, "b": 0.6})

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    component.evaluate()
    assert [option.description for option in captured[0].options] == ["", ""]


@pytest.mark.parametrize(
    ("candidates", "cause"),
    [
        ([{"id": "a", "label": "Low"}, {"id": "a", "label": "High"}], "have the same ID"),
        ([{"id": "a", "label": "Low"}], "at least two"),
        ([{"id": "a", "label": "Low", "unexpected": 1}, {"id": "b", "label": "High"}], "unexpected"),
        # A row added in the editor and left blank.
        (
            [{"id": "a", "label": "Low"}, {"id": None, "label": None, "description": ""}],
            "Option 2 needs an ID and a Label",
        ),
    ],
)
def test_invalid_options_table_is_a_clear_configuration_error(candidates, cause):
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "jev-latest"}],
        kind="Choice",
        context="text",
        question="Which applies?",
        candidates=candidates,
    )
    with pytest.raises(DecisionConfigurationError, match=cause):
        component.evaluate()


def test_component_takes_no_api_key_from_the_flow():
    """Credentials come only from the provider's own settings, never from a flow field."""
    assert "api_key" not in {component_input.name for component_input in DecisionModelComponent.inputs}


BOOLEAN_RESULT = DecisionResult(kind="boolean", provider="TypeSafe", model="m", probability_true=0.8)


def _captured(monkeypatch, kind="Boolean", result=BOOLEAN_RESULT, **fields):
    """Evaluate once with the provider replaced; returns the request the runtime received."""
    component = DecisionModelComponent()
    component.set(model=[{"provider": "TypeSafe", "name": "jev-latest"}], kind=kind, question="Refund?", **fields)
    captured = []

    def evaluate(request, **_kwargs):
        captured.append(request)
        return result

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    component.evaluate()
    return captured[0]


def test_structured_context_reaches_the_model_as_json(monkeypatch):
    request = _captured(monkeypatch, structured_context=Data(data={"order": 1042, "status": "charged twice"}))
    assert request.context == {"order": 1042, "status": "charged twice"}


@pytest.mark.parametrize(
    ("fields", "cause"),
    [
        ({}, "Enter a Context, or connect a Structured Context"),
        ({"context": "  "}, "Enter a Context, or connect a Structured Context"),
        # Connected but empty, as from a Dynamic Create Data with no fields: say so, don't ask to connect it.
        ({"structured_context": Data(data={})}, "Structured Context is empty"),
        ({"structured_context": {}}, "Structured Context is empty"),
        ({"context": "Old text", "structured_context": Data(data={})}, "Structured Context is empty"),
        ({"context": "Old text", "structured_context": {}}, "Structured Context is empty"),
        ({"context": "Charged twice", "structured_context": {"order": 1042}}, "not both"),
    ],
)
def test_exactly_one_context_is_required(monkeypatch, fields, cause):
    with pytest.raises(DecisionConfigurationError, match=cause):
        _captured(monkeypatch, **fields)


def test_boolean_sends_what_yes_and_no_mean(monkeypatch):
    request = _captured(monkeypatch, context="text", yes_description="Asks for money back", no_description="Other")
    assert (request.yes_description, request.no_description) == ("Asks for money back", "Other")


def test_yes_and_no_left_from_boolean_never_apply_to_another_type(monkeypatch):
    request = _captured(
        monkeypatch,
        kind="Choice",
        result=DecisionResult(kind="choice", provider="TypeSafe", model="m", probabilities={"a": 0.4, "b": 0.6}),
        context="text",
        candidates=[{"id": "a", "label": "Low"}, {"id": "b", "label": "High"}],
        yes_description="Asks for money back",
    )
    assert request.yes_description == ""


@pytest.mark.parametrize(("kind", "shown"), [("Boolean", True), ("Choice", False), ("Score", False)])
def test_yes_and_no_fields_show_only_for_boolean(monkeypatch, kind, shown):
    monkeypatch.setattr(component_module, "handle_model_input_update", lambda _c, config, *_a, **_k: config)
    component = DecisionModelComponent()
    config = {name: field.model_dump() for name, field in component._inputs.items()}
    config = component.update_build_config(config, kind, "kind")
    assert config["yes_description"]["show"] is shown
    assert config["no_description"]["show"] is shown
    assert config["candidates"]["show"] is not shown


async def test_an_agent_supplies_the_context_when_used_as_a_tool():
    component = DecisionModelComponent()
    component.set(model=[{"provider": "TypeSafe", "name": "jev-latest"}], kind="Boolean", question="Refund?")
    [tool] = await component.to_toolkit()
    assert set(tool.args) == {"context"}


@pytest.mark.parametrize(("kind", "name"), [("Choice", "Options"), ("Score", "Levels")])
def test_the_table_is_named_for_the_decision_type(monkeypatch, kind, name):
    monkeypatch.setattr(component_module, "handle_model_input_update", lambda _c, config, *_a, **_k: config)
    component = DecisionModelComponent()
    config = {field: spec.model_dump() for field, spec in component._inputs.items()}
    assert component.update_build_config(config, kind, "kind")["candidates"]["display_name"] == name


async def test_an_agent_learns_what_the_tool_answers():
    component = DecisionModelComponent()
    component.set(model=[{"provider": "TypeSafe", "name": "jev-latest"}], kind="Boolean", question="Refund?")
    [tool] = await component.to_toolkit()
    assert "probability_true" in tool.description
    assert "selected_option" in tool.description
    assert tool.args["context"]["description"].startswith("The text the question is about")


def test_the_result_leaves_out_what_this_decision_did_not_return(monkeypatch):
    component = DecisionModelComponent()
    component.set(model=[{"provider": "TypeSafe", "name": "jev-latest"}], kind="Boolean", question="Refund?")
    component.set(context="I was charged twice.")
    monkeypatch.setattr(component_module, "evaluate_decision", lambda *_a, **_k: BOOLEAN_RESULT)
    data = component.evaluate().data
    assert data["probability_true"] == 0.8
    assert not {"probabilities", "score", "refusal", "request_id"} & data.keys()
    assert not {"options", "levels", "yes_description", "no_description"} & data["request"].keys()


def test_options_are_typed_in_not_connected():
    candidates = next(field for field in DecisionModelComponent().inputs if field.name == "candidates")
    assert candidates.input_types == []


def test_a_structured_context_that_is_a_list_says_it_must_be_one_object(monkeypatch):
    with pytest.raises(DecisionConfigurationError, match="must be one JSON object"):
        _captured(monkeypatch, structured_context=[{"order": 1042}, {"order": 1043}])


@pytest.mark.parametrize("kind", ["Ranking", None, "boolean"])
def test_an_unknown_decision_type_says_which_ones_exist(monkeypatch, kind):
    with pytest.raises(DecisionConfigurationError, match="Pick a Decision Type: Choice, Boolean or Score"):
        _captured(monkeypatch, kind=kind, context="text")


async def test_update_keeps_a_boolean_nodes_yes_and_no_meanings_shown():
    component = DecisionModelComponent()
    fresh = component.to_frontend_node()["data"]["node"]
    saved = {**fresh, "template": {**fresh["template"], "kind": {**fresh["template"]["kind"], "value": "Boolean"}}}
    node = await component.update_frontend_node(component.to_frontend_node()["data"]["node"], saved)
    assert node["template"]["yes_description"]["show"] is True
    assert node["template"]["no_description"]["show"] is True
    assert node["template"]["candidates"]["show"] is False
