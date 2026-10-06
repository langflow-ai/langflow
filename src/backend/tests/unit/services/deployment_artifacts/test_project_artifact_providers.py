"""Unit tests for model-provider collection in the project-artifact builder.

Targets the private helpers directly (``_collect_required_providers``,
``_build_archive``, ``_build_deployment_snapshot_flows``) so they don't have to
thread the full ``build_project_artifact`` mock sequence, matching
``test_project_artifact_dependencies.py``.

Both deploy paths are covered, because a packaged artifact and a deployment
snapshot must report the same provider requirements: a precheck whose answer
depended on which path the caller took would pass a project one way and refuse
it the other.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from langflow.initial_setup import setup as initial_setup
from langflow.services.deployment_artifacts.builder import (
    ProjectArtifactLimits,
    ProjectArtifactRequiredModel,
    _build_archive,
    _build_deployment_snapshot_flows,
    _collect_model_requirements,
    _FlowSnapshot,
    _model_entry,
)

STARTER_PROJECTS = Path(initial_setup.__file__).parent / "starter_projects"


def _node(
    *,
    template: dict | None = None,
    base_classes: list[str] | None = None,
    metadata: dict | None = None,
    flow: dict | None = None,
    display_name: str | None = None,
) -> dict:
    inner: dict = {}
    if template is not None:
        inner["template"] = template
    if base_classes is not None:
        inner["base_classes"] = base_classes
    if metadata is not None:
        inner["metadata"] = metadata
    if flow is not None:
        inner["flow"] = flow
    if display_name is not None:
        inner["display_name"] = display_name
    return {"data": {"node": inner}}


def _model_field(value: object, *, model_type: str | None = None) -> dict:
    field: dict = {"name": "model", "type": "model", "value": value}
    if model_type is not None:
        field["model_type"] = model_type
    return {"model": field}


def _graph(nodes: list) -> dict:
    return {"nodes": nodes, "edges": []}


def _snapshot(nodes: list, *, name: str = "Flow") -> _FlowSnapshot:
    return _FlowSnapshot(flow_id=uuid4(), name=name, payload={"name": name, "data": _graph(nodes)})


def _manifest_of(artifact) -> dict:
    with zipfile.ZipFile(io.BytesIO(artifact.content)) as archive:
        return json.loads(archive.read("manifest.json"))


@pytest.mark.parametrize(
    ("label", "nodes", "expected"),
    [
        (
            "a configured model field names its provider",
            [_node(template=_model_field({"provider": "OpenAI", "name": "gpt-4o"}))],
            (("openai",), 0),
        ),
        (
            "a spec serialized into name is unwrapped rather than lost",
            [
                _node(
                    template=_model_field(
                        {"provider": "unknown", "name": json.dumps([{"provider": "Anthropic", "name": "claude"}])}
                    )
                )
            ],
            (("anthropic",), 0),
        ),
        (
            "a bare model name is counted, never guessed",
            [_node(template=_model_field("gpt-4o-mini"))],
            ((), 1),
        ),
        (
            "an unset model field is counted",
            [_node(template=_model_field(""))],
            ((), 1),
        ),
        (
            "a multi-entry value names every provider it carries",
            [_node(template=_model_field(json.dumps([{"provider": "OpenAI"}, {"provider": "Groq"}])))],
            (("groq", "openai"), 0),
        ),
        (
            "an unreadable entry beside a readable one is counted, not dropped",
            [_node(template=_model_field([{"provider": "OpenAI", "name": "x"}, {"name": "bare"}]))],
            (("openai",), 1),
        ),
        (
            "several specs serialized into one name are counted, not read as the first",
            [
                _node(
                    template=_model_field(
                        {
                            "provider": "unknown",
                            "name": json.dumps([{"provider": "OpenAI"}, {"provider": "Groq"}]),
                        }
                    )
                )
            ],
            ((), 1),
        ),
        (
            "JSON nested too deep inside a name is counted instead of crashing",
            [_node(template=_model_field({"provider": "unknown", "name": "[" * 200_000}))],
            ((), 1),
        ),
        (
            "a native list of dicts is the shape ModelInput documents",
            [_node(template=_model_field([{"name": "gpt-4o", "provider": "OpenAI"}]))],
            (("openai",), 0),
        ),
        (
            "a model wired in over an edge states no requirement of its own",
            [
                _node(template=_model_field("connect_other_models")),
                _node(
                    base_classes=["LanguageModel"],
                    metadata={"module": "lfx_anthropic.models.anthropic"},
                    display_name="Anthropic",
                ),
            ],
            (("anthropic",), 0),
        ),
        (
            "a standalone language model speaks for its own package",
            [
                _node(
                    base_classes=["LanguageModel"],
                    metadata={"module": "lfx_openai.models.openai_chat"},
                    display_name="OpenAI",
                )
            ],
            (("openai",), 0),
        ),
        (
            "a standalone embeddings component resolves the same way",
            [
                _node(
                    base_classes=["Embeddings"],
                    metadata={"module": "lfx_bundles.mistral.embeddings"},
                    display_name="MistralAI Embeddings",
                )
            ],
            (("mistral",), 0),
        ),
        (
            "an explicit model_provider_id wins over the module path",
            [
                _node(
                    base_classes=["LanguageModel"],
                    metadata={"model_provider_id": "azure-openai", "module": "lfx_openai.models.openai_chat"},
                )
            ],
            (("azure-openai",), 0),
        ),
        (
            "a model field beats the holding component's own base classes",
            [
                _node(
                    template=_model_field({"provider": "OpenAI"}),
                    base_classes=["LanguageModel"],
                    metadata={"module": "lfx_anthropic.models.anthropic"},
                )
            ],
            (("openai",), 0),
        ),
        (
            "a nested flow is walked and its duplicate provider deduped",
            [
                _node(
                    template=_model_field({"provider": "OpenAI"}),
                    flow={"data": _graph([_node(template=_model_field({"provider": "openai"}))])},
                )
            ],
            (("openai",), 0),
        ),
        (
            "a field that is not model-typed is not read as a selection",
            [_node(template={"provider": {"name": "provider", "type": "str", "value": "OpenAI"}})],
            ((), 0),
        ),
        (
            "malformed nodes are skipped instead of raising",
            ["not a node", None, {"data": None}, {"data": {"node": "not a dict"}}, {}],
            ((), 0),
        ),
    ],
)
def test_collect_required_providers(label: str, nodes: list, expected: tuple[tuple[str, ...], int]) -> None:
    requirements = _collect_model_requirements(_graph(nodes))
    assert (requirements.providers, requirements.unresolved_fields) == expected, label


@pytest.mark.parametrize("flow_data", [None, "not a graph", {}, {"nodes": "not a list"}])
def test_collect_model_requirements_tolerates_absent_graph_data(flow_data: object) -> None:
    requirements = _collect_model_requirements(flow_data)
    assert (requirements.providers, requirements.models, requirements.unresolved_fields) == ((), (), 0)


def test_collect_model_requirements_carries_the_selected_model_and_its_type() -> None:
    """The policy blocks by provider::type::name, so a provider id alone cannot answer it."""
    nodes = [
        _node(template=_model_field([{"name": "gpt-6-astra", "provider": "OpenAI", "metadata": {"model_type": "llm"}}]))
    ]

    requirements = _collect_model_requirements(_graph(nodes))

    assert requirements.providers == ("openai",)
    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="openai", name="gpt-6-astra", model_type="llm"),
    )


def test_collect_model_requirements_omits_a_type_the_flow_did_not_carry() -> None:
    """An absent type is left absent: the policy then tries every type segment."""
    nodes = [_node(template=_model_field([{"name": "claude-x", "provider": "Anthropic"}]))]

    requirements = _collect_model_requirements(_graph(nodes))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="anthropic", name="claude-x", model_type=None),
    )


# What the model picker actually saves: provider and name, metadata without a type.
_PICKER_SELECTION = {
    "name": "gpt-4o-mini",
    "provider": "OpenAI",
    "icon": "OpenAI",
    "metadata": {
        "model_class": "ChatOpenAI",
        "model_name_param": "model",
        "api_key_param": "api_key",  # pragma: allowlist secret
    },
}


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        pytest.param("language", "llm", id="a language model field"),
        pytest.param("embedding", "embeddings", id="an embedding model field"),
        pytest.param("something-new", None, id="a type this mapping does not know"),
    ],
)
def test_collect_model_requirements_takes_the_type_from_the_field_when_the_selection_has_none(
    declared: str, expected: str | None
) -> None:
    """The runtime checks a typed key, so a picker selection must not be reported typeless.

    A Language Model is instantiated with ``model_type="llm"``; reporting it with no
    type would let a typed allowlist (``openai::llm::gpt-4o-mini``) refuse at deploy
    what the runtime allows at invoke. An unrecognised declaration stays absent.
    """
    nodes = [_node(template=_model_field([_PICKER_SELECTION], model_type=declared))]

    requirements = _collect_model_requirements(_graph(nodes))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="openai", name="gpt-4o-mini", model_type=expected),
    )


def test_collect_model_requirements_prefers_the_selections_own_type_over_the_field() -> None:
    selection = {"name": "text-embed-x", "provider": "OpenAI", "metadata": {"model_type": "embeddings"}}
    nodes = [_node(template=_model_field([selection], model_type="language"))]

    requirements = _collect_model_requirements(_graph(nodes))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="openai", name="text-embed-x", model_type="embeddings"),
    )


@pytest.mark.parametrize(("field_type", "model_type"), [("language", "llm"), ("embedding", "embeddings")])
@pytest.mark.parametrize(
    ("overrides", "provider", "name"),
    [
        ({"provider": " Cohere ", "model_name": " custom-model "}, "cohere", "custom-model"),
        ({"provider": "Cohere"}, "cohere", "gpt-4o-mini"),
        ({"model_name": "custom-model"}, "openai", "custom-model"),
        ({"provider": " ", "model_name": ""}, "openai", "gpt-4o-mini"),
    ],
)
def test_deploy_requirements_follow_static_model_overrides(
    field_type: str, model_type: str, overrides: dict[str, str], provider: str, name: str
) -> None:
    template = _model_field([{"provider": "OpenAI", "name": "gpt-4o-mini"}], model_type=field_type)
    template.update({key: {"type": "str", "value": value} for key, value in overrides.items()})
    snapshot = _snapshot(
        [_node(template=template, base_classes=["Embeddings" if field_type == "embedding" else "LanguageModel"])]
    )

    manifest = _manifest_of(
        _build_archive(
            project_id=uuid4(), project_name="Overrides", snapshots=(snapshot,), limits=ProjectArtifactLimits()
        )
    )
    _, _, _, requirements = _build_deployment_snapshot_flows((snapshot,), limits=ProjectArtifactLimits())

    assert requirements.providers == (provider,)
    assert requirements.models == (ProjectArtifactRequiredModel(provider=provider, name=name, model_type=model_type),)
    assert requirements.unresolved_fields == 0
    assert manifest["required_providers"] == [provider]
    assert manifest["required_models"] == [{"provider": provider, "name": name, "model_type": model_type}]
    assert manifest["unresolved_model_fields"] == 0


@pytest.mark.parametrize(("field_name", "providers"), [("provider", ()), ("model_name", ("openai",))])
def test_variable_backed_model_overrides_are_unresolved(field_name: str, providers: tuple[str, ...]) -> None:
    template = _model_field([_PICKER_SELECTION], model_type="language")
    template[field_name] = {"type": "str", "value": "GLOBAL_MODEL_SETTING", "load_from_db": True}

    requirements = _collect_model_requirements(_graph([_node(template=template, base_classes=["LanguageModel"])]))

    assert requirements.providers == providers
    assert requirements.models == ()
    assert requirements.unresolved_fields == 1


@pytest.mark.parametrize(("field_name", "providers"), [("provider", ()), ("model_name", ("openai",))])
@pytest.mark.parametrize("legacy", [False, True])
def test_connected_model_overrides_are_unresolved(field_name: str, providers: tuple[str, ...], *, legacy: bool) -> None:
    template = _model_field([_PICKER_SELECTION], model_type="language")
    template[field_name] = {"type": "str", "value": "saved-default"}
    node = {"id": "model-node", **_node(template=template, base_classes=["LanguageModel"])}
    edge = {"source": "upstream", "target": "model-node"}
    if legacy:
        edge["targetHandle"] = f"str|{field_name}|model-node"
    else:
        edge["data"] = {"targetHandle": {"fieldName": field_name, "id": "model-node"}}
    graph = {"nodes": [node], "edges": [edge]}
    # Grouped flows have their own edge scope, just like their own nodes.
    requirements = _collect_model_requirements(_graph([_node(flow={"data": graph})]))

    assert requirements.providers == providers
    assert requirements.models == ()
    assert requirements.unresolved_fields == 1


def test_model_overrides_do_not_change_other_model_fields() -> None:
    template = {
        "other_model": {"type": "model", "value": [_PICKER_SELECTION], "model_type": "language"},
        "provider": {"type": "str", "value": "Cohere"},
        "model_name": {"type": "str", "value": "custom-model"},
    }

    requirements = _collect_model_requirements(_graph([_node(template=template)]))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="openai", name="gpt-4o-mini", model_type="llm"),
    )
    assert requirements.unresolved_fields == 0


def test_non_model_component_scalar_fields_do_not_override_its_model_input() -> None:
    template = _model_field([_PICKER_SELECTION], model_type="language")
    template["provider"] = {"type": "str", "value": "Cohere"}
    template["model_name"] = {"type": "str", "value": "custom-model"}

    requirements = _collect_model_requirements(_graph([_node(template=template, base_classes=["Message"])]))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="openai", name="gpt-4o-mini", model_type="llm"),
    )


def test_changed_provider_override_discards_the_old_selections_model_type() -> None:
    template = _model_field(
        [{"provider": "OpenAI", "name": "old-model", "metadata": {"model_type": "llm"}}], model_type="embedding"
    )
    template["provider"] = {"type": "str", "value": "Cohere"}
    template["model_name"] = {"type": "str", "value": "embed-model"}

    requirements = _collect_model_requirements(_graph([_node(template=template, base_classes=["Embeddings"])]))

    assert requirements.models == (
        ProjectArtifactRequiredModel(provider="cohere", name="embed-model", model_type="embeddings"),
    )


def test_dynamic_model_name_keeps_a_static_provider_override_and_counts_once() -> None:
    template = _model_field([_PICKER_SELECTION], model_type="language")
    template["provider"] = {"type": "str", "value": "Cohere"}
    template["model_name"] = {"type": "str", "value": "GLOBAL_MODEL", "load_from_db": True}

    requirements = _collect_model_requirements(_graph([_node(template=template, base_classes=["LanguageModel"])]))

    assert requirements.providers == ("cohere",)
    assert requirements.models == ()
    assert requirements.unresolved_fields == 1


@pytest.mark.parametrize("policy_mode", ["standalone", "unrecognized", None])
def test_unknown_policy_mode_keeps_the_standalone_provider_requirement(policy_mode: str | None) -> None:
    node = _node(
        base_classes=["LanguageModel"],
        metadata={"model_provider_policy_mode": policy_mode, "module": "lfx_openai.models.openai_chat"},
        display_name="OpenAI",
    )

    assert _collect_model_requirements(_graph([node])).providers == ("openai",)


@pytest.mark.parametrize("policy_mode", ["none", "delegate"])
def test_identity_free_components_do_not_declare_standalone_providers(policy_mode: str) -> None:
    node = _node(
        base_classes=["Embeddings"],
        metadata={
            "model_provider_policy_mode": policy_mode,
            "module": "lfx.components.langchain_utilities.fake_embeddings.FakeEmbeddingsComponent",
        },
        display_name="Fake Embeddings",
        template={"dimensions": {"type": "int", "value": 5}},
    )
    snapshot = _snapshot([node])

    manifest = _manifest_of(
        _build_archive(
            project_id=uuid4(), project_name="Local embeddings", snapshots=(snapshot,), limits=ProjectArtifactLimits()
        )
    )
    _, _, _, requirements = _build_deployment_snapshot_flows((snapshot,), limits=ProjectArtifactLimits())

    assert requirements.providers == ()
    assert requirements.models == ()
    assert requirements.unresolved_fields == 0
    assert manifest["schema_version"] == 1
    assert "required_providers" not in manifest


def test_collect_model_requirements_keeps_the_provider_of_a_model_it_cannot_name() -> None:
    """A standalone component implies a provider but selects no model."""
    nodes = [
        _node(
            base_classes=["LanguageModel"],
            metadata={"module": "lfx_openai.models.openai_chat"},
            display_name="OpenAI",
        )
    ]

    requirements = _collect_model_requirements(_graph(nodes))

    assert requirements.providers == ("openai",)
    assert requirements.models == ()
    assert requirements.unresolved_fields == 0


def test_manifest_reports_providers_and_claims_schema_version_5() -> None:
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="Providers",
        snapshots=(
            _snapshot([_node(template=_model_field({"provider": "OpenAI"}))], name="Chat"),
            _snapshot([_node(template=_model_field({"provider": "Anthropic"}))], name="Summarize"),
        ),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    assert manifest["schema_version"] == 5
    assert manifest["required_providers"] == ["anthropic", "openai"]
    assert manifest["unresolved_model_fields"] == 0
    assert {entry["name"]: entry["required_providers"] for entry in manifest["flows"]} == {
        "Chat": ["openai"],
        "Summarize": ["anthropic"],
    }


def test_manifest_reports_selected_models_beside_their_providers() -> None:
    """A deploy target checks two things: provider approved, and model not blocked."""
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="Models",
        snapshots=(
            _snapshot(
                [
                    _node(
                        template=_model_field(
                            [{"name": "gpt-6-astra", "provider": "OpenAI", "metadata": {"model_type": "llm"}}]
                        )
                    ),
                    _node(template=_model_field([{"name": "claude-x", "provider": "Anthropic"}])),
                ],
                name="Two models",
            ),
        ),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    assert manifest["required_providers"] == ["anthropic", "openai"]
    assert manifest["required_models"] == [
        # No model_type key at all for the selection that did not carry one.
        {"provider": "anthropic", "name": "claude-x"},
        {"provider": "openai", "name": "gpt-6-astra", "model_type": "llm"},
    ]
    assert manifest["flows"][0]["required_models"] == manifest["required_models"]


def test_manifest_omits_required_models_when_no_model_is_named() -> None:
    """A standalone component implies a provider without naming a model."""
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="Provider only",
        snapshots=(
            _snapshot(
                [
                    _node(
                        base_classes=["LanguageModel"],
                        metadata={"module": "lfx_openai.models.openai_chat"},
                        display_name="OpenAI",
                    )
                ]
            ),
        ),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    assert manifest["required_providers"] == ["openai"]
    assert manifest["required_models"] == []
    assert "required_models" not in manifest["flows"][0]


def test_manifest_carries_the_unresolved_count_so_the_list_cannot_read_as_complete() -> None:
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="Partly unresolved",
        snapshots=(
            _snapshot(
                [
                    _node(template=_model_field({"provider": "OpenAI"})),
                    _node(template=_model_field("gpt-4o-mini")),
                ],
                name="Mixed",
            ),
        ),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    assert manifest["required_providers"] == ["openai"]
    assert manifest["unresolved_model_fields"] == 1
    assert manifest["flows"][0]["unresolved_model_fields"] == 1


def test_manifest_keeps_the_earlier_schema_version_when_no_provider_is_selected() -> None:
    """A project needing no provider must still package as a version older readers accept."""
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="No providers",
        snapshots=(_snapshot([_node(template={"text": {"name": "text", "type": "str", "value": "hi"}})]),),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    assert manifest["schema_version"] == 1
    assert "required_providers" not in manifest
    assert "unresolved_model_fields" not in manifest
    assert "required_providers" not in manifest["flows"][0]
    assert "unresolved_model_fields" not in manifest["flows"][0]


def test_manifest_reports_an_unresolved_count_even_with_no_resolvable_provider() -> None:
    """Every model field deferred to run time is still a requirement worth stating."""
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="All deferred",
        snapshots=(_snapshot([_node(template=_model_field("gpt-4o-mini"))]),),
        limits=ProjectArtifactLimits(),
    )

    manifest = _manifest_of(artifact)
    # No provider is known, so nothing an older reader would have to provision:
    # the version stays where it was and only the count is added.
    assert manifest["schema_version"] == 1
    assert manifest["required_providers"] == []
    assert manifest["unresolved_model_fields"] == 1


def test_models_typed_in_one_flow_and_untyped_in_another_still_package() -> None:
    """The merged set holds both forms of one model; ordering must not compare a type with None."""
    selection = {"provider": "OpenAI", "name": "gpt-4o"}
    artifact = _build_archive(
        project_id=uuid4(),
        project_name="Mixed types",
        snapshots=(
            _snapshot([_node(template=_model_field([selection], model_type="language"))], name="Typed"),
            _snapshot([_node(template=_model_field([selection]))], name="Untyped"),
        ),
        limits=ProjectArtifactLimits(),
    )

    assert _manifest_of(artifact)["required_models"] == [
        {"provider": "openai", "name": "gpt-4o"},
        {"provider": "openai", "name": "gpt-4o", "model_type": "llm"},
    ]


def test_deployment_snapshot_reports_the_same_providers_as_the_manifest() -> None:
    snapshots = (
        _snapshot([_node(template=_model_field({"provider": "OpenAI", "name": "gpt-4o"}))], name="Chat"),
        _snapshot(
            [
                _node(template=_model_field({"provider": "Anthropic"})),
                _node(template=_model_field("gpt-4o-mini")),
            ],
            name="Summarize",
        ),
    )

    _, _, _, snapshot_models = _build_deployment_snapshot_flows(snapshots, limits=ProjectArtifactLimits())
    manifest = _manifest_of(
        _build_archive(
            project_id=uuid4(),
            project_name="Both paths",
            snapshots=snapshots,
            limits=ProjectArtifactLimits(),
        )
    )

    assert snapshot_models.providers == ("anthropic", "openai")
    assert snapshot_models.unresolved_fields == 1
    assert list(snapshot_models.providers) == manifest["required_providers"]
    assert snapshot_models.unresolved_fields == manifest["unresolved_model_fields"]
    assert [model.name for model in snapshot_models.models] == ["gpt-4o"]
    assert [_model_entry(model) for model in snapshot_models.models] == manifest["required_models"]


def test_shipped_starter_projects_select_no_provider_and_defer_every_model_field() -> None:
    """The templates ship with the model unset, so the honest answer is a count, not a list.

    This is the regression that keeps the collector from inventing a provider
    out of a bare model name: the day a starter starts resolving to one, that
    is a real change in what deploying it requires, and it should be noticed
    here rather than in a refusal.
    """
    files = sorted(STARTER_PROJECTS.glob("*.json"))
    assert files, f"no starter projects found under {STARTER_PROJECTS}"

    providers: set[str] = set()
    unresolved = 0
    for path in files:
        requirements = _collect_model_requirements(json.loads(path.read_text())["data"])
        providers |= set(requirements.providers)
        unresolved += requirements.unresolved_fields

    assert providers == set()
    assert unresolved > 0
