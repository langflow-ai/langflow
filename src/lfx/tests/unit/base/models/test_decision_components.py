"""Decision Model component discovery and the shared execution contract."""

import pytest
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionRequest, DecisionResult
from lfx.components.llm_operations import decision_model as component_module
from lfx.components.llm_operations.decision_model import _NEW_QUESTION as NEW_QUESTION
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
    assert template["template"]["questions"]["type"] == "decision_questions"
    assert template["template"]["questions"]["new_question"]["kind"] == "Choice"
    assert template["template"]["model"]["model_type"] == "decision"
    assert template["outputs"][0]["types"] == ["JSON"]
    restored = eval_custom_component_code(template["template"]["code"]["value"])()
    assert restored.name == component.name


@pytest.mark.parametrize("kind", ["Choice", "Boolean", "Score"])
def test_component_preserves_evidence_and_executes_once(kind, monkeypatch):
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "model"}],
        context="sensitive context",
        questions=[
            {
                "kind": kind,
                "question": "What applies?",
                "options": [{"id": "a", "label": "Refund"}, {"id": "b", "label": "Support"}],
                "levels": [{"id": "a", "label": "Low"}, {"id": "b", "label": "High"}],
            }
        ],
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
    assert [row.label for row in request.options] == (["Refund", "Support"] if kind == "Choice" else [])
    assert [row.label for row in request.levels] == (["Low", "High"] if kind == "Score" else [])
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
    columns = next(item for item in component.inputs if item.name == "questions").table_schema
    rows = []
    for row_id, label in (("a", "Low"), ("b", "High")):
        row = {column["name"]: column.get("default") for column in columns}
        row.update(id=row_id, label=label)
        rows.append(row)
    component.set(
        model=[{"provider": "TypeSafe", "name": "model"}],
        context="text",
        questions=[{"kind": "Choice", "question": "Which applies?", "options": rows}],
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
        context="text",
        questions=[{"kind": "Choice", "question": "Which applies?", "options": candidates}],
    )
    with pytest.raises(DecisionConfigurationError, match=cause):
        component.evaluate()


def test_component_takes_no_api_key_from_the_flow():
    """Credentials come only from the provider's own settings, never from a flow field."""
    assert "api_key" not in {component_input.name for component_input in DecisionModelComponent.inputs}


BOOLEAN_RESULT = DecisionResult(kind="boolean", provider="TypeSafe", model="m", probability_true=0.8)


_QUESTION_KEYS = {"options", "levels", "yes_description", "no_description"}


def _captured(monkeypatch, kind="Boolean", result=BOOLEAN_RESULT, **fields):
    """Evaluate once with the provider replaced; returns the request the runtime received."""
    question = {"kind": kind, "question": "Refund?", **{k: v for k, v in fields.items() if k in _QUESTION_KEYS}}
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "jev-latest"}],
        questions=[question],
        **{k: v for k, v in fields.items() if k not in _QUESTION_KEYS},
    )
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
        options=[{"id": "a", "label": "Low"}, {"id": "b", "label": "High"}],
        yes_description="Asks for money back",
    )
    assert request.yes_description == ""


async def test_an_agent_supplies_the_context_when_used_as_a_tool():
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "jev-latest"}], questions=[{"kind": "Boolean", "question": "Refund?"}]
    )
    [tool] = await component.to_toolkit()
    assert set(tool.args) == {"context"}


async def test_an_agent_learns_what_the_tool_answers():
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "jev-latest"}], questions=[{"kind": "Boolean", "question": "Refund?"}]
    )
    [tool] = await component.to_toolkit()
    assert "probability_true" in tool.description
    assert "selected_option" in tool.description
    assert tool.args["context"]["description"].startswith("The text the questions are about")


def test_the_result_leaves_out_what_this_decision_did_not_return(monkeypatch):
    component = DecisionModelComponent()
    component.set(
        model=[{"provider": "TypeSafe", "name": "jev-latest"}], questions=[{"kind": "Boolean", "question": "Refund?"}]
    )
    component.set(context="I was charged twice.")
    monkeypatch.setattr(component_module, "evaluate_decision", lambda *_a, **_k: BOOLEAN_RESULT)
    data = component.evaluate().data
    assert data["probability_true"] == 0.8
    assert not {"probabilities", "score", "refusal", "request_id"} & data.keys()
    assert not {"options", "levels", "yes_description", "no_description"} & data["request"].keys()


def test_questions_are_typed_in_not_connected():
    questions = next(field for field in DecisionModelComponent().inputs if field.name == "questions")
    assert not questions.input_types


def test_a_structured_context_that_is_a_list_says_it_must_be_one_object(monkeypatch):
    with pytest.raises(DecisionConfigurationError, match="must be one JSON object"):
        _captured(monkeypatch, structured_context=[{"order": 1042}, {"order": 1043}])


@pytest.mark.parametrize("kind", ["Ranking", None, "boolean"])
def test_an_unknown_decision_type_says_which_ones_exist(monkeypatch, kind):
    with pytest.raises(DecisionConfigurationError, match="Pick a Decision Type for Question 1"):
        _captured(monkeypatch, kind=kind, context="text")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("legacy", "expected"),
    [
        (
            {"kind": "Boolean", "question": "Refund?", "yes_description": "Asks for money back"},
            {"kind": "Boolean", "question": "Refund?", "yes_description": "Asks for money back"},
        ),
        (
            {"kind": "Choice", "question": "Which team?", "candidates": [{"id": "x", "label": "X"}]},
            {"kind": "Choice", "options": [{"id": "x", "label": "X"}]},
        ),
        # Older Score nodes stored their rubric in the shared candidates field.
        (
            {"kind": "Score", "question": "How happy?", "candidates": [{"id": "bad", "label": "Bad"}]},
            {"kind": "Score", "levels": [{"id": "bad", "label": "Bad"}], "options": NEW_QUESTION["options"]},
        ),
        (
            {"kind": "Score", "question": "How happy?", "levels": [{"id": "ok", "label": "OK"}]},
            {"kind": "Score", "levels": [{"id": "ok", "label": "OK"}]},
        ),
    ],
)
async def test_a_node_saved_before_the_question_list_keeps_its_question(legacy, expected):
    component = DecisionModelComponent()
    saved = component.to_frontend_node()["data"]["node"]
    del saved["template"]["questions"]
    saved["template"].update({name: {"value": value} for name, value in legacy.items()})
    updated = await component.update_frontend_node(component.to_frontend_node()["data"]["node"], saved)
    [question] = updated["template"]["questions"]["value"]
    assert {key: question[key] for key in expected} == expected
    assert updated["template"]["questions"]["show"]


@pytest.mark.asyncio
async def test_a_dev_node_with_the_questions_table_starts_a_fresh_list():
    """Multiple mode's questions table never shipped; its rows don't match a question list item."""
    component = DecisionModelComponent()
    saved = component.to_frontend_node()["data"]["node"]
    saved["template"]["questions"] = {"type": "table", "value": [{"id": "team", "kind": "Choice"}]}
    saved["template"]["question_mode"]["value"] = "Multiple"
    updated = await component.update_frontend_node(component.to_frontend_node()["data"]["node"], saved)
    assert updated["template"]["questions"]["value"] == [NEW_QUESTION]
    assert updated["template"]["question_mode"]["value"] == "Form"


def mixed_question_component():
    component = DecisionModelComponent()
    component.set(
        context="An urgent billing issue.",
        questions=[
            {
                "name": "team",
                "kind": "Choice",
                "question": "Which team?",
                "options": [{"id": "billing", "label": "Billing"}, {"id": "support", "label": "Support"}],
            },
            {"name": "urgent", "kind": "Boolean", "question": "Is this urgent?"},
            {
                "name": "impact",
                "kind": "Score",
                "question": "How much impact?",
                "levels": [{"id": "low", "label": "Low"}, {"id": "high", "label": "High"}],
            },
        ],
    )
    return component


def test_form_and_json_build_identical_requests():
    import json

    component = mixed_question_component()
    form_request = component._request()
    component.set(
        question_mode="JSON",
        questions_json=json.dumps(form_request.model_dump(mode="json")["questions"]),
    )
    assert component._request() == form_request
    assert list(form_request.questions) == ["team", "urgent", "impact"]
    assert [question.kind for question in form_request.questions.values()] == ["choice", "boolean", "score"]
    assert [level.id for level in form_request.questions["impact"].levels] == ["low", "high"]


def test_unnamed_form_questions_default_to_their_position():
    component = mixed_question_component()
    component.questions[0]["name"] = ""
    component.questions[2]["name"] = " "
    assert list(component._request().questions) == ["q1", "urgent", "q3"]


def test_one_form_question_keeps_the_single_result_shape():
    component = mixed_question_component()
    component.set(questions=component.questions[:1])
    request = component._request()
    assert isinstance(request, DecisionRequest)
    assert request.question == "Which team?"


@pytest.mark.parametrize(
    "source",
    [
        "",
        "{}",
        "[]",
        "null",
        '{"q":',
        '{"q":{"kind":"boolean","question":"one"},"q":{"kind":"boolean","question":"two"}}',
        '{"q":{"kind":"boolean","question":"one","kind":"score"}}',
        '{"q":{"kind":"boolean","question":"one","endpoint":"https://example.com"}}',
        '{"q":{"kind":"choice","question":"one","options":[]}}',
    ],
)
def test_invalid_questions_json_fails_before_execution(source, monkeypatch):
    component = mixed_question_component()
    component.set(question_mode="JSON", questions_json=source)
    monkeypatch.setattr(
        component_module, "evaluate_decision", lambda *_a, **_k: pytest.fail("Must not invoke provider")
    )
    with pytest.raises(DecisionConfigurationError):
        component.evaluate()


@pytest.mark.parametrize(
    ("index", "change", "message"),
    [
        (2, {"name": "team"}, "named 'team'"),
        (1, {"question": ""}, "Question 2: Question can't be empty"),
        (2, {"kind": "Rating"}, "Decision Type for Question 3"),
        (2, {"levels": [{"id": "low", "label": "Low"}]}, "Question 3: Add at least two levels"),
    ],
)
def test_form_questions_reject_ambiguous_input(index, change, message):
    component = mixed_question_component()
    component.questions[index].update(change)
    with pytest.raises(DecisionConfigurationError, match=message):
        component._request()


@pytest.mark.parametrize("questions", [None, "not a list", ["not an object"]])
def test_a_question_list_a_tweak_broke_says_so(questions):
    component = mixed_question_component()
    component._attributes["questions"] = questions
    with pytest.raises(DecisionConfigurationError, match=r"Add a question|Decision Type for Question 1"):
        component._request()


def test_questions_mode_shows_one_editor_and_keeps_both_values():
    component = mixed_question_component()
    template, _ = create_component_template(component_extractor=component)
    config = template["template"]
    config["questions_json"]["value"] = '{"q":{"kind":"boolean","question":"Q?"}}'
    values = {name: config[name]["value"] for name in ("questions", "questions_json")}
    for mode in ("JSON", "Form", "JSON"):
        component.update_build_config(config, mode, "question_mode")
        assert config["questions"]["show"] is (mode == "Form")
        assert config["questions_json"]["show"] is (mode == "JSON")
        assert {name: config[name]["value"] for name in values} == values


def test_batch_component_preserves_answers_and_shared_usage(monkeypatch):
    from lfx.base.models.decisions.schema import DecisionBatchResult

    component = mixed_question_component()
    calls = []

    def evaluate(request, **_kwargs):
        calls.append(request)
        return DecisionBatchResult(
            answers={
                "team": DecisionResult(
                    kind="choice",
                    provider="TypeSafe",
                    model="m",
                    probabilities={"billing": 0.8, "support": 0.2},
                    selected_option="billing",
                ),
                "urgent": DecisionResult(kind="boolean", provider="TypeSafe", model="m", probability_true=0.9),
                "impact": DecisionResult(
                    kind="score", provider="TypeSafe", model="m", probabilities={"low": 0.1, "high": 0.9}, score=0.9
                ),
            },
            usage={"input_tokens": 21, "output_tokens": 3},
            request_id="req_multi",
        )

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    data = component.evaluate().data
    assert len(calls) == 1
    assert set(data["answers"]) == {"team", "urgent", "impact"}
    assert "context" not in data["request"]
    assert data["request_id"] == "req_multi"
    assert component._token_usage.total_tokens == 24
    assert all("usage" not in answer for answer in data["answers"].values())


def test_mixed_component_runs_through_runtime_and_http_adapter(monkeypatch):
    import httpx
    from lfx.base.models.decisions import providers

    component = mixed_question_component()
    component.set(model=[{"provider": "TypeSafe", "name": "jev-latest"}])
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-only-key")
    calls = []

    def post(url, **kwargs):
        assert url == providers.ENDPOINTS["TypeSafe"]
        calls.append(kwargs["json"])
        assert kwargs["headers"]["Authorization"] == "Bearer test-only-key"
        return httpx.Response(
            200,
            json={
                "model": "jev-test",
                "answers": {
                    "team": {"type": "choice", "choice": "billing", "probabilities": {"billing": 0.8, "support": 0.2}},
                    "urgent": {"type": "noul", "noul": 0.9},
                    "impact": {
                        "type": "score",
                        "score": 0.9,
                        "legend": {"0": "Low", "1": "High"},
                        "probabilities": {"0": 0.1, "1": 0.9},
                    },
                },
                "usage": {"input_tokens": 30, "output_tokens": 0},
            },
        )

    monkeypatch.setattr(providers, "provider_safe_httpx_post", post)
    data = component.evaluate().data
    assert len(calls) == 1
    assert calls[0]["state"] == "An urgent billing issue."
    assert set(calls[0]["questions"]) == {"team", "urgent", "impact"}
    assert data["answers"]["impact"]["score"] == 0.9
    assert component._token_usage.total_tokens == 30


@pytest.mark.asyncio
async def test_saved_question_list_survives_component_update():
    from copy import deepcopy

    component = mixed_question_component()
    saved, _ = create_component_template(component_extractor=component)
    saved["template"]["questions"]["value"] = deepcopy(component.questions)
    new, _ = create_component_template(component_extractor=DecisionModelComponent())
    updated = await component.update_frontend_node(new, deepcopy(saved))
    assert updated["template"]["questions"]["value"] == component.questions
    assert updated["template"]["questions"]["show"]


@pytest.mark.asyncio
async def test_saved_json_mode_survives_component_update():
    from copy import deepcopy

    component = mixed_question_component()
    saved, _ = create_component_template(component_extractor=component)
    saved["template"]["question_mode"]["value"] = "JSON"
    saved["template"]["questions_json"]["value"] = '{"urgent":{"kind":"boolean","question":"Urgent?"}}'
    new, _ = create_component_template(component_extractor=DecisionModelComponent())
    updated = await component.update_frontend_node(new, deepcopy(saved))
    assert updated["template"]["question_mode"]["value"] == "JSON"
    assert updated["template"]["questions_json"]["value"] == saved["template"]["questions_json"]["value"]
    assert updated["template"]["questions_json"]["show"]
    assert not updated["template"]["questions"]["show"]
