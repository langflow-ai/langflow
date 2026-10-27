"""Streaming transport defaults must preserve explicit component tweaks."""

from copy import deepcopy
from unittest.mock import patch

import pytest
from lfx.exceptions.tweaks import TweakRefusedError
from lfx.processing.process import process_tweaks
from lfx.schema.graph import Tweaks


def _graph() -> dict:
    return {
        "nodes": [
            {
                "id": node_id,
                "data": {
                    "node": {
                        "display_name": name,
                        "template": {
                            "stream": {"type": "bool", "value": False},
                            "temperature": {"type": "float", "value": 0.5},
                        },
                    }
                },
            }
            for node_id, name in [("Model-a", "Model"), ("ChatOutput-b", "Chat Output")]
        ]
    }


@pytest.mark.parametrize("target", ["Model-a", "Model"])
@pytest.mark.parametrize("transport_stream", [True, False])
@pytest.mark.parametrize("as_model", [True, False])
def test_targeted_stream_tweak_overrides_transport_default(target, transport_stream, as_model):
    """Respect an explicit node stream value while defaulting other nodes."""
    graph = _graph()
    tweaks = {target: {"stream": not transport_stream}}
    original = deepcopy(tweaks)

    process_tweaks(graph, Tweaks(root=tweaks) if as_model else tweaks, stream=transport_stream)

    model, output = [node["data"]["node"]["template"] for node in graph["nodes"]]
    assert model["stream"]["value"] is not transport_stream
    assert output["stream"]["value"] is transport_stream
    assert tweaks == original


@pytest.mark.parametrize("transport_stream", [True, False])
def test_explicit_global_stream_tweak_keeps_existing_precedence(transport_stream):
    """A caller's explicit all-node stream setting still overrides node tweaks."""
    graph = _graph()
    explicit_stream = not transport_stream

    process_tweaks(
        graph,
        {"Model-a": {"stream": transport_stream}, "stream": explicit_stream},
        stream=transport_stream,
    )

    for node in graph["nodes"]:
        assert node["data"]["node"]["template"]["stream"]["value"] is explicit_stream


def test_other_global_tweak_precedence_is_unchanged():
    """Changing the runtime stream default does not reorder caller overrides."""
    graph = _graph()

    process_tweaks(graph, {"Model-a": {"temperature": 0.2}, "temperature": 0.7}, stream=True)

    for node in graph["nodes"]:
        template = node["data"]["node"]["template"]
        assert template["temperature"]["value"] == 0.7
        assert template["stream"]["value"] is True


def test_refused_tweak_does_not_apply_the_runtime_stream_default():
    """Validate every pending change before mutating any component."""
    graph = _graph()
    node = graph["nodes"][0]
    node["data"]["type"] = "SQLComponent"
    node["data"]["node"]["template"]["database_url"] = {
        "type": "str",
        "value": "postgresql://stored.example/db",
    }
    before = deepcopy(graph)

    with pytest.raises(TweakRefusedError, match="database_url"):
        process_tweaks(
            graph,
            {"Model-a": {"database_url": "postgresql://other.example/db", "stream": False}},
            stream=True,
        )

    assert graph == before


@pytest.mark.parametrize("policy", ["off", "declared"])
@pytest.mark.parametrize("target", ["Model-a", "Model"])
def test_targeted_stream_tweak_obeys_deployment_policy(policy, target):
    """An injected default must not exempt the caller's targeted stream tweak."""
    graph = _graph()
    graph["nodes"][0]["data"]["node"]["template"]["temperature"]["api_editable"] = True
    before = deepcopy(graph)

    with (
        patch("lfx.processing.process._resolve_tweak_policy", return_value=policy),
        pytest.raises(TweakRefusedError, match="stream"),
    ):
        process_tweaks(graph, {target: {"stream": False}}, stream=True)

    assert graph == before


def test_declared_stream_tweak_overrides_the_runtime_default():
    """A field explicitly exposed by the flow can still override the default."""
    graph = _graph()
    graph["nodes"][0]["data"]["node"]["template"]["stream"]["api_editable"] = True

    with patch("lfx.processing.process._resolve_tweak_policy", return_value="declared"):
        process_tweaks(graph, {"Model-a": {"stream": False}}, stream=True)

    assert graph["nodes"][0]["data"]["node"]["template"]["stream"]["value"] is False
    assert graph["nodes"][1]["data"]["node"]["template"]["stream"]["value"] is True
