"""Standalone evaluator discovery and the shared execution contract."""

import pytest
from lfx.base.models.decisions import component as component_module
from lfx.base.models.decisions.schema import DecisionConfigurationError, DecisionResult
from lfx.components.llm_operations.openai_decision import OpenAIDecisionComponent
from lfx.components.llm_operations.perplexity_decision import PerplexityDecisionComponent
from lfx.components.llm_operations.typesafe_decision import TypeSafeDecisionComponent
from lfx.custom.eval import eval_custom_component_code
from lfx.custom.utils import create_component_template

COMPONENTS = (TypeSafeDecisionComponent, PerplexityDecisionComponent, OpenAIDecisionComponent)


@pytest.mark.parametrize("component_class", COMPONENTS)
def test_component_template_discoverable(component_class):
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
    assert restored.provider == component.provider
    assert restored.name == component.name


@pytest.mark.parametrize("component_class", COMPONENTS)
@pytest.mark.parametrize("kind", ["Choice", "Boolean", "Score"])
def test_component_preserves_evidence_and_executes_once(component_class, kind, monkeypatch):
    component = component_class()
    component.set(
        model=[{"provider": component.provider, "name": "model"}],
        kind=kind,
        context="sensitive context",
        question="What applies?",
        api_key="secret",
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
        return DecisionResult(kind=kind.lower(), provider=component.provider, model="actual-model", **fields)

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    result = component.evaluate()
    assert len(calls) == 1
    request, kwargs = calls[0]
    assert request.context == "sensitive context"
    assert kwargs["timeout"] == 30
    assert result.data["model"] == "actual-model"
    assert "context" not in result.data["request"]
    assert "secret" not in str(result.data)
    assert result.data["request"]["kind"] == kind.lower()


@pytest.mark.parametrize("component_class", COMPONENTS)
def test_provider_fixed_component_rejects_other_provider(component_class):
    component = component_class()
    component.set(model=[{"provider": "different", "name": "model"}])
    with pytest.raises(DecisionConfigurationError, match="Select a"):
        component.evaluate()


def test_packaged_index_preserves_decision_component_sources():
    import hashlib
    from importlib.resources import files

    import orjson

    blob = orjson.loads(files("lfx").joinpath("_assets/component_index.json").read_bytes())
    signature = blob.pop("sha256")
    assert hashlib.sha256(orjson.dumps(blob, option=orjson.OPT_SORT_KEYS)).hexdigest() == signature
    components = dict(blob["entries"])["llm_operations"]
    for component_class in COMPONENTS:
        template = components[component_class.name]
        assert template["template"]["model"]["model_type"] == "decision"
        restored = eval_custom_component_code(template["template"]["code"]["value"])()
        assert restored.provider == component_class.provider
        assert restored.name == component_class.name


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
from lfx.components.llm_operations import (
    TypeSafeDecisionComponent, PerplexityDecisionComponent, OpenAIDecisionComponent,
)
for component in (TypeSafeDecisionComponent, PerplexityDecisionComponent, OpenAIDecisionComponent):
    assert component().name
"""
    subprocess.run(  # noqa: S603 - fixed local interpreter and literal SDK-isolation check
        [sys.executable, "-c", script], check=True, capture_output=True, timeout=60
    )


@pytest.mark.parametrize("component_class", COMPONENTS)
def test_row_added_in_the_editor_accepts_blank_description(component_class, monkeypatch):
    """The editor fills a new row's cells with each column's default, or null when it has none."""
    component = component_class()
    columns = next(item for item in component.inputs if item.name == "candidates").table_schema
    rows = []
    for row_id, label in (("a", "Low"), ("b", "High")):
        row = {column["name"]: column.get("default") for column in columns}
        row.update(id=row_id, label=label)
        rows.append(row)
    component.set(
        model=[{"provider": component.provider, "name": "model"}],
        kind="Choice",
        context="text",
        question="Which applies?",
        candidates=rows,
    )
    captured = []

    def evaluate(request, **_kwargs):
        captured.append(request)
        return DecisionResult(kind="choice", provider=component.provider, model="m", probabilities={"a": 0.4, "b": 0.6})

    monkeypatch.setattr(component_module, "evaluate_decision", evaluate)
    component.evaluate()
    assert [option.description for option in captured[0].options] == ["", ""]
