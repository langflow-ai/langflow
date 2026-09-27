"""Contract tests for the HITL graph checkpoint data model (LE-1440).

GraphCheckpoint/VertexCheckpointData must round-trip through Pydantic AND raw
JSON including set-typed fields, because the durable store (LE-1441) persists
checkpoints as JSON and a lossy round-trip would corrupt resume state.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from lfx.graph.checkpoint.schema import (
    GraphCheckpoint,
    VertexCheckpointData,
    deserialize_value,
    serialize_value,
    wire_has_opaque_drop,
)
from lfx.schema.message import Message


def _checkpoint(**overrides) -> GraphCheckpoint:
    base = {
        "run_id": "run-1",
        "flow_id": "flow-1",
        "session_id": "sess-1",
        "job_id": "job-1",
        "flow_payload": {"nodes": [{"id": "n1"}], "edges": []},
        "run_map": {"n1": ["n2"]},
        "run_predecessors": {"n2": ["n1"]},
        "vertices_to_run": {"n1", "n2"},
        "vertices_being_run": {"n1"},
        "ran_at_least_once": {"n1"},
        "run_queue": ["n2"],
        "call_order": ["n1"],
        "vertices_layers": [["n1"], ["n2"]],
        "first_layer": ["n1"],
        "inactivated_vertices": {"n3"},
        "branch_inactivation_sources": {"n1": {"n3"}},
        "activated_vertices": ["n2"],
        "vertex_results": {
            "n1": VertexCheckpointData(vertex_id="n1", built=True, results={"text": "hello"}),
        },
        "pause_context": {"reason": "human_input_required", "data": {"options": ["a", "b"]}},
    }
    base.update(overrides)
    return GraphCheckpoint(**base)


def test_checkpoint_round_trips_via_pydantic():
    cp = _checkpoint()
    restored = GraphCheckpoint.model_validate(cp.model_dump())
    assert restored == cp
    assert restored.vertices_to_run == {"n1", "n2"}
    assert restored.vertex_results["n1"].built is True


def test_checkpoint_round_trips_via_json_with_sets_preserved():
    cp = _checkpoint()
    payload = json.loads(cp.model_dump_json())
    restored = GraphCheckpoint.model_validate(payload)
    assert restored.vertices_to_run == {"n1", "n2"}
    assert restored.vertices_being_run == {"n1"}
    assert restored.ran_at_least_once == {"n1"}
    assert restored.inactivated_vertices == {"n3"}
    assert restored.branch_inactivation_sources == {"n1": {"n3"}}
    assert restored.run_queue == ["n2"]
    assert restored.call_order == ["n1"]
    assert restored.pause_context == {"reason": "human_input_required", "data": {"options": ["a", "b"]}}


def test_checkpoint_ids_default_and_expiry_optional():
    cp = _checkpoint()
    assert cp.checkpoint_id
    assert cp.expires_at is None
    assert cp.created_at.tzinfo is not None
    expiring = _checkpoint(expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    assert expiring.expires_at is not None


def test_serialize_value_round_trips_none_and_primitives():
    for value in (None, "text", 42, 3.14, True, {"k": [1, 2]}, ["a", "b"]):
        wire = serialize_value(value)
        json.dumps(wire)
        assert deserialize_value(wire) == value


def test_serialize_value_round_trips_real_message():
    msg = Message(text="hello human", sender="Machine", sender_name="AI")
    wire = serialize_value(msg)
    json.dumps(wire)
    restored = deserialize_value(wire)
    assert isinstance(restored, Message)
    assert restored.text == "hello human"
    assert restored.sender == "Machine"


def test_serialize_value_round_trips_dict_of_messages():
    payload = {"a": Message(text="one"), "b": Message(text="two")}
    wire = serialize_value(payload)
    json.dumps(wire)
    restored = deserialize_value(wire)
    assert isinstance(restored["a"], Message)
    assert restored["a"].text == "one"
    assert restored["b"].text == "two"


def test_serialize_value_returns_none_for_opaque_objects():
    class Opaque:
        pass

    assert serialize_value(Opaque()) is None
    assert serialize_value(lambda: 1) is None


def test_serialize_value_degrades_model_with_unserializable_field():
    """A model holding an opaque field (e.g. an LLM client / model class) must not raise.

    Reproduces the HITL-with-Agent crash: pausing serialized the agent's state and a
    nested model class blew up ``model_dump(mode="json")``.

    Covers only the case where the dump itself raises. A dump that *succeeds* but cannot be
    validated back is a separate failure mode -- see the round-trip test below.
    """
    from pydantic import BaseModel, ConfigDict

    class Holder(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        opaque: type = BaseModel

    assert serialize_value(Holder()) is None


def test_serialize_value_drops_model_whose_dump_does_not_round_trip():
    """A dump that succeeds is not proof the value round-trips.

    langchain-core >= 1.6.1 serializes ``BaseTool.func``/``coroutine`` to their repr with no
    warning, so an agent's tool checkpointed cleanly and then failed ``model_validate`` on every
    resume ("Input should be callable"), stranding the paused run. serialize_value must drop it.
    """
    from collections.abc import Callable

    from pydantic import BaseModel, ConfigDict, field_serializer

    class LossyDump(BaseModel):
        model_config = ConfigDict(arbitrary_types_allowed=True)
        fn: Callable[..., Any]

        @field_serializer("fn")
        def _serialize_fn(self, value: Callable[..., Any]) -> str:
            return repr(value)

    # serialize_value only encodes models declared under ``lfx.`` (importing arbitrary modules back
    # would be injection), so the double has to claim one. Nothing imports it: the drop happens first.
    LossyDump.__module__ = "lfx.graph.checkpoint._test_double"

    value = LossyDump(fn=lambda: 1)
    assert value.model_dump(mode="json") == {"fn": repr(value.fn)}  # the dump itself still succeeds
    assert serialize_value(value) is None


def test_serialize_value_drops_a_component_tool_on_every_langchain_version():
    """A live agent tool must never reach the checkpoint.

    Pinned langchain-core (1.5.1) drops it because the dump raises; 1.6.1+ drops it because the
    dump no longer round-trips. Asserting the outcome keeps the guarantee version-independent.
    """
    from lfx.base.tools.component_tool import ComponentStructuredTool
    from pydantic import BaseModel as PydanticBaseModel

    class _Args(PydanticBaseModel):
        x: str = ""

    def _run(x: str) -> str:
        return x

    async def _arun(x: str) -> str:
        return x

    tool = ComponentStructuredTool(
        name="probe_tool", description="probe", args_schema=_Args, func=_run, coroutine=_arun
    )
    assert serialize_value(tool) is None
    # A vertex holding it must be recorded as a drop so resume re-derives it from the rebuilt node.
    assert wire_has_opaque_drop(serialize_value([tool]))
