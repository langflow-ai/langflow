"""Unit tests for the AG-UI translator.

The translator consumes Langflow ``EventManager`` events and emits AG-UI
protocol events. These tests feed real ``EventManager`` event payloads and
assert on the emitted AG-UI event objects. No mocks: the translator is a pure,
stateful transformation with no I/O.
"""

from __future__ import annotations

from ag_ui.core import (
    CustomEvent,
    RunErrorEvent,
    RunFinishedEvent,
    RunStartedEvent,
    StateDeltaEvent,
    StateSnapshotEvent,
    StepFinishedEvent,
    StepStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from langflow.api.v2.agui_translator import AGUITranslator


def test_run_lifecycle_emits_started_and_finished():
    t = AGUITranslator(run_id="r1", thread_id="t1")

    started = t.start()
    ended = t.translate("end", {})

    assert isinstance(started[0], RunStartedEvent)
    assert started[0].run_id == "r1"
    assert started[0].thread_id == "t1"
    assert isinstance(ended[0], RunFinishedEvent)
    assert ended[0].run_id == "r1"
    assert ended[0].thread_id == "t1"


def test_error_emits_run_error():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("error", {"error": "boom"})

    assert isinstance(out[0], RunErrorEvent)
    assert "boom" in out[0].message


def test_error_reads_text_from_error_message_payload():
    """``error`` can carry a full ErrorMessage dump whose reason is in ``text``."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("error", {"text": "component blew up", "category": "error"})

    assert isinstance(out[0], RunErrorEvent)
    assert "component blew up" in out[0].message


def test_token_sequence_emits_start_contents_then_end_on_boundary():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    first = t.translate("token", {"chunk": "Hel", "id": "m1"})
    second = t.translate("token", {"chunk": "lo", "id": "m1"})
    ended = t.translate("end", {})

    # First token opens the message and carries its delta.
    assert isinstance(first[0], TextMessageStartEvent)
    assert first[0].message_id == "m1"
    assert isinstance(first[1], TextMessageContentEvent)
    assert first[1].message_id == "m1"
    assert first[1].delta == "Hel"

    # Subsequent tokens are content only, same message id.
    assert len(second) == 1
    assert isinstance(second[0], TextMessageContentEvent)
    assert second[0].message_id == "m1"
    assert second[0].delta == "lo"

    # The end boundary closes the open message before finishing the run.
    assert isinstance(ended[0], TextMessageEndEvent)
    assert ended[0].message_id == "m1"
    assert isinstance(ended[1], RunFinishedEvent)


def test_new_message_id_closes_previous_message_and_opens_new():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "a", "id": "m1"})
    out = t.translate("token", {"chunk": "b", "id": "m2"})

    assert isinstance(out[0], TextMessageEndEvent)
    assert out[0].message_id == "m1"
    assert isinstance(out[1], TextMessageStartEvent)
    assert out[1].message_id == "m2"
    assert isinstance(out[2], TextMessageContentEvent)
    assert out[2].message_id == "m2"
    assert out[2].delta == "b"


def test_error_boundary_closes_open_text_message():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "partial", "id": "m1"})
    out = t.translate("error", {"error": "boom"})

    assert isinstance(out[0], TextMessageEndEvent)
    assert out[0].message_id == "m1"
    assert isinstance(out[1], RunErrorEvent)


def test_interleaved_non_terminal_event_does_not_split_open_message():
    """A non-terminal event between tokens must not close the streamed message.

    Langflow's agent streams one message id for its whole response while other
    events (build_start, add_message for other messages, log) interleave. Closing
    the message on those would split it into two START/END pairs reusing an
    already-ended id, which is malformed AG-UI.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "Hel", "id": "m1"})
    interleaved = t.translate("build_start", {"id": "node-x"})
    more = t.translate("token", {"chunk": "lo", "id": "m1"})

    # The interleaved non-terminal event must not close the open message.
    assert all(not isinstance(e, TextMessageEndEvent) for e in interleaved)
    # The continuing token must not re-open an already-open message.
    assert all(not isinstance(e, TextMessageStartEvent) for e in more)
    assert isinstance(more[0], TextMessageContentEvent)
    assert more[0].message_id == "m1"
    assert more[0].delta == "lo"


def test_token_for_already_ended_message_id_is_dropped():
    """A ``token`` arriving after ``add_message`` ended that id must not re-open it.

    Some Langflow agents fire ``add_message`` with the final text first, which
    emits START/CONTENT/END for the id and records it in
    ``_emitted_text_message_ids``. Late tokens for the same id used to emit a
    fresh ``TextMessageStartEvent`` for an already-ended message id, which is
    malformed AG-UI. The translator must drop those tokens silently.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    # add_message emits START/CONTENT/END for m1 and records m1 as emitted.
    add_message_events = t.translate("add_message", {"id": "m1", "text": "hello", "sender": "AI"})
    assert any(isinstance(e, TextMessageEndEvent) for e in add_message_events)

    # A late token for the same id must not re-open the ended message.
    late = t.translate("token", {"chunk": "x", "id": "m1"})

    assert all(not isinstance(e, TextMessageStartEvent) for e in late), (
        f"Late token re-opened an already-ended message id; emitted: {late}"
    )


def test_token_after_boundary_close_is_dropped():
    """An interleaved token sequence ``A, B, A`` must not re-open id A.

    Switching from id A to id B closes A through ``_close_open_message``. A
    later token for A used to slip past the dedup guard because
    ``_close_open_message`` was the only finalizer that did not record the
    closed id in ``_emitted_text_message_ids``. The translator must treat a
    token-boundary close the same way it treats an ``add_message`` close.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    a1 = t.translate("token", {"chunk": "hi", "id": "m1"})
    assert any(isinstance(e, TextMessageStartEvent) and e.message_id == "m1" for e in a1)

    # Switching to a new id closes m1 via _close_open_message.
    b = t.translate("token", {"chunk": "yo", "id": "m2"})
    assert any(isinstance(e, TextMessageEndEvent) and e.message_id == "m1" for e in b)
    assert any(isinstance(e, TextMessageStartEvent) and e.message_id == "m2" for e in b)

    # A late token for m1 must be dropped, not re-open the ended message.
    late = t.translate("token", {"chunk": "again", "id": "m1"})
    assert all(not isinstance(e, TextMessageStartEvent) for e in late), (
        f"Token boundary did not mark m1 as ended; emitted: {late}"
    )
    assert late == [], f"Expected no events for late token after boundary close; got {late}"


def test_vertices_sorted_emits_state_snapshot_of_all_nodes():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("vertices_sorted", {"ids": ["a"], "to_run": ["a", "b", "c"]})

    assert len(out) == 1
    assert isinstance(out[0], StateSnapshotEvent)
    nodes = out[0].snapshot["nodes"]
    # The snapshot covers the full run set (to_run), not just the first layer.
    assert set(nodes) == {"a", "b", "c"}
    for node in nodes.values():
        assert node["status"] == "pending"
        assert node["output"] is None


def test_vertices_sorted_falls_back_to_ids_when_to_run_absent():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("vertices_sorted", {"ids": ["a", "b"]})

    assert isinstance(out[0], StateSnapshotEvent)
    assert set(out[0].snapshot["nodes"]) == {"a", "b"}


def test_start_establishes_empty_node_state():
    """start() must seed the state container so later node deltas always apply."""
    t = AGUITranslator(run_id="r1", thread_id="t1")

    started = t.start()

    assert isinstance(started[0], RunStartedEvent)
    snapshots = [e for e in started if isinstance(e, StateSnapshotEvent)]
    assert snapshots
    assert snapshots[0].snapshot == {"nodes": {}}


def test_build_start_for_node_emits_step_started_and_running_delta():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("build_start", {"id": "node-x"})

    assert isinstance(out[0], StepStartedEvent)
    assert out[0].step_name == "node-x"
    assert isinstance(out[1], StateDeltaEvent)
    op = out[1].delta[0]
    assert op["op"] == "add"
    assert op["path"] == "/nodes/node-x"
    assert op["value"] == {"status": "running", "output": None}


def test_graph_level_build_start_with_no_id_is_noop():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    # The graph-level build_start (the /build path) carries no node id;
    # RUN_STARTED already signals the run beginning.
    assert t.translate("build_start", {}) == []


def test_end_vertex_success_emits_step_finished_and_state_delta():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate(
        "end_vertex",
        {"build_data": {"id": "node-x", "valid": True, "data": {"outputs": {"out": "hello"}}}},
    )

    assert isinstance(out[0], StepFinishedEvent)
    assert out[0].step_name == "node-x"
    assert isinstance(out[1], StateDeltaEvent)
    op = out[1].delta[0]
    assert op["op"] == "add"
    assert op["path"] == "/nodes/node-x"
    assert op["value"] == {"status": "success", "output": {"outputs": {"out": "hello"}}}


def test_end_vertex_failure_sets_error_status():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("end_vertex", {"build_data": {"id": "node-x", "valid": False, "data": None}})

    op = out[1].delta[0]
    assert op["value"]["status"] == "error"


def test_node_state_deltas_use_add_so_they_apply_without_vertices_sorted():
    """build_start/end_vertex must not depend on vertices_sorted seeding the node.

    Per-node build events and vertices_sorted come from different Langflow
    execution paths that do not co-occur. start() establishes ``/nodes`` and node
    deltas use ``add`` on ``/nodes/{id}`` (create-or-replace), so the JSON Patch
    applies cleanly whether or not a STATE_SNAPSHOT seeded the node first.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()  # no vertices_sorted in this path

    build = t.translate("build_start", {"id": "node-x"})
    end = t.translate("end_vertex", {"build_data": {"id": "node-x", "valid": True, "data": "ok"}})

    for events in (build, end):
        delta = next(e for e in events if isinstance(e, StateDeltaEvent))
        op = delta.delta[0]
        assert op["op"] == "add"
        assert op["path"] == "/nodes/node-x"


def test_end_vertex_does_not_close_open_text_message():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "Hel", "id": "m1"})
    t.translate("end_vertex", {"build_data": {"id": "node-x", "valid": True, "data": {}}})
    more = t.translate("token", {"chunk": "lo", "id": "m1"})

    assert all(not isinstance(e, TextMessageStartEvent) for e in more)
    assert isinstance(more[0], TextMessageContentEvent)
    assert more[0].message_id == "m1"


def test_token_without_message_id_is_dropped():
    """Token events with missing ``id`` cannot drive the AG-UI lifecycle.

    A TextMessageStart/Content/End triple requires a stable id to correlate
    chunks. Emitting events with ``message_id=""`` produces malformed
    streams that some AG-UI clients reject; drop the event instead.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    no_id = t.translate("token", {"chunk": "hello"})
    none_id = t.translate("token", {"chunk": "hello", "id": None})
    empty_id = t.translate("token", {"chunk": "hello", "id": ""})

    assert no_id == []
    assert none_id == []
    assert empty_id == []


def test_add_message_without_message_id_skips_text_lifecycle():
    """``add_message`` without an id must not emit TextMessage* events.

    Tool-call sub-events can still ride a missing id (they namespace by
    block/content index), but the text lifecycle needs a stable id.
    """
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("add_message", {"text": "hello"})

    assert all(not isinstance(e, TextMessageStartEvent) for e in out)
    assert all(not isinstance(e, TextMessageContentEvent) for e in out)
    assert all(not isinstance(e, TextMessageEndEvent) for e in out)


def test_add_message_plain_text_emits_a_text_message():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("add_message", {"id": "m1", "text": "The weather is sunny."})

    assert isinstance(out[0], TextMessageStartEvent)
    assert out[0].message_id == "m1"
    assert isinstance(out[1], TextMessageContentEvent)
    assert out[1].delta == "The weather is sunny."
    assert isinstance(out[2], TextMessageEndEvent)
    assert out[2].message_id == "m1"


def test_add_message_finalizing_a_streamed_message_does_not_duplicate_text():
    """A streamed message's add_message finalizer only closes it, never re-emits text."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "The weather ", "id": "m1"})
    t.translate("token", {"chunk": "is sunny.", "id": "m1"})
    out = t.translate("add_message", {"id": "m1", "text": "The weather is sunny."})

    assert all(not isinstance(e, TextMessageStartEvent) for e in out)
    assert all(not isinstance(e, TextMessageContentEvent) for e in out)
    assert isinstance(out[0], TextMessageEndEvent)
    assert out[0].message_id == "m1"


def test_add_message_tool_use_emits_tool_call_lifecycle():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate(
        "add_message",
        {
            "id": "m1",
            "text": "",
            "content_blocks": [
                {
                    "title": "Agent Steps",
                    "contents": [
                        {
                            "type": "tool_use",
                            "name": "search",
                            "tool_input": {"query": "weather"},
                            "output": "sunny",
                            "error": None,
                        }
                    ],
                }
            ],
        },
    )

    starts = [e for e in out if isinstance(e, ToolCallStartEvent)]
    args = [e for e in out if isinstance(e, ToolCallArgsEvent)]
    ends = [e for e in out if isinstance(e, ToolCallEndEvent)]
    results = [e for e in out if isinstance(e, ToolCallResultEvent)]
    assert len(starts) == 1
    assert starts[0].tool_call_name == "search"
    assert starts[0].parent_message_id == "m1"
    assert len(args) == 1
    assert "weather" in args[0].delta
    assert len(ends) == 1
    assert len(results) == 1
    assert "sunny" in results[0].content
    # The four events share one tool_call_id.
    assert {starts[0].tool_call_id, args[0].tool_call_id, ends[0].tool_call_id, results[0].tool_call_id} == {
        starts[0].tool_call_id
    }


def test_tool_use_error_is_reported_via_tool_call_result():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate(
        "add_message",
        {
            "id": "m1",
            "content_blocks": [
                {
                    "title": "Agent Steps",
                    "contents": [
                        {
                            "type": "tool_use",
                            "name": "search",
                            "tool_input": {},
                            "output": None,
                            "error": "rate limited",
                        }
                    ],
                }
            ],
        },
    )

    results = [e for e in out if isinstance(e, ToolCallResultEvent)]
    assert len(results) == 1
    assert "rate limited" in results[0].content


def test_repeated_add_message_does_not_re_emit_the_same_tool_call():
    """A tool call already emitted is not re-emitted when add_message re-fires."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    payload = {
        "id": "m1",
        "content_blocks": [
            {
                "title": "Agent Steps",
                "contents": [
                    {"type": "tool_use", "name": "search", "tool_input": {"q": "x"}, "output": "done", "error": None}
                ],
            }
        ],
    }
    first = t.translate("add_message", payload)
    second = t.translate("add_message", payload)

    assert len([e for e in first if isinstance(e, ToolCallStartEvent)]) == 1
    assert second == []


def test_repeated_add_message_after_streamed_finalizer_does_not_duplicate_text():
    """A streamed message finalized once must not re-emit text on a later add_message."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate("token", {"chunk": "Hello", "id": "m1"})
    t.translate("add_message", {"id": "m1", "text": "Hello"})  # finalizes the streamed message
    again = t.translate("add_message", {"id": "m1", "text": "Hello"})  # re-fire

    assert again == []


def test_malformed_content_block_is_skipped_not_crashed():
    """A null or non-dict entry in content_blocks is skipped, not fatal."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("add_message", {"id": "m1", "text": "hi", "content_blocks": [None, "garbage"]})

    assert any(isinstance(e, TextMessageStartEvent) for e in out)


def test_custom_content_types_emit_langflow_custom_events():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate(
        "add_message",
        {
            "id": "m1",
            "content_blocks": [
                {
                    "title": "Steps",
                    "contents": [
                        {"type": "json", "data": {"k": "v"}},
                        {"type": "code", "code": "print(1)", "language": "python"},
                        {"type": "media", "urls": ["http://x/img.png"], "caption": "pic"},
                        {"type": "error", "reason": "boom", "traceback": "trace"},
                    ],
                }
            ],
        },
    )

    customs = {e.name: e for e in out if isinstance(e, CustomEvent)}
    assert set(customs) == {
        "langflow.content.json",
        "langflow.content.code",
        "langflow.content.media",
        "langflow.content.error",
    }
    assert customs["langflow.content.json"].value["message_id"] == "m1"
    assert customs["langflow.content.json"].value["block_title"] == "Steps"
    assert customs["langflow.content.code"].value["content"]["code"] == "print(1)"


def test_log_event_emits_langflow_log_custom_event():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("log", {"message": "hi", "type": "text", "name": "Log 1", "component_id": "c1"})

    assert len(out) == 1
    assert isinstance(out[0], CustomEvent)
    assert out[0].name == "langflow.log"
    assert out[0].value["component_id"] == "c1"


def test_remove_message_emits_langflow_removed_custom_event():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    out = t.translate("remove_message", {"id": "m9"})

    assert len(out) == 1
    assert isinstance(out[0], CustomEvent)
    assert out[0].name == "langflow.message.removed"
    assert out[0].value["message_id"] == "m9"


def test_repeated_custom_content_block_is_not_re_emitted():
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()
    payload = {
        "id": "m1",
        "content_blocks": [{"title": "Steps", "contents": [{"type": "json", "data": {"k": "v"}}]}],
    }

    first = t.translate("add_message", payload)
    second = t.translate("add_message", payload)

    assert len([e for e in first if isinstance(e, CustomEvent)]) == 1
    assert second == []


def test_updated_custom_content_block_is_re_emitted():
    """If a content block's payload changes on a later add_message, the update is emitted."""
    t = AGUITranslator(run_id="r1", thread_id="t1")
    t.start()

    t.translate(
        "add_message",
        {"id": "m1", "content_blocks": [{"title": "S", "contents": [{"type": "json", "data": {}}]}]},
    )
    out = t.translate(
        "add_message",
        {"id": "m1", "content_blocks": [{"title": "S", "contents": [{"type": "json", "data": {"k": "v"}}]}]},
    )

    customs = [e for e in out if isinstance(e, CustomEvent)]
    assert len(customs) == 1
    assert customs[0].value["content"]["data"] == {"k": "v"}


# --- Full-sequence integration coverage ---------------------------------------


def _run_sequence(translator: AGUITranslator, events: list[tuple[str, dict]]) -> list:
    """Feed start() then a list of (event_type, data) pairs, collecting all output."""
    out = list(translator.start())
    for event_type, data in events:
        out.extend(translator.translate(event_type, data))
    return out


def _assert_well_formed(events: list) -> None:
    """Assert an emitted AG-UI stream is structurally valid."""
    assert events, "expected a non-empty event stream"
    assert isinstance(events[0], RunStartedEvent)
    assert isinstance(events[-1], (RunFinishedEvent, RunErrorEvent))

    open_messages: set[str] = set()
    seen_messages: set[str] = set()
    for event in events:
        if isinstance(event, TextMessageStartEvent):
            assert event.message_id not in open_messages, "text message started while already open"
            assert event.message_id not in seen_messages, "text message id reused after it ended"
            open_messages.add(event.message_id)
            seen_messages.add(event.message_id)
        elif isinstance(event, TextMessageContentEvent):
            assert event.message_id in open_messages, "text content for a message that is not open"
        elif isinstance(event, TextMessageEndEvent):
            assert event.message_id in open_messages, "text message ended without being open"
            open_messages.discard(event.message_id)
    assert not open_messages, "text messages left unclosed"

    started_tools: set[str] = set()
    ended_tools: set[str] = set()
    for event in events:
        if isinstance(event, ToolCallStartEvent):
            assert event.tool_call_id not in started_tools, "tool call started twice"
            started_tools.add(event.tool_call_id)
        elif isinstance(event, ToolCallArgsEvent):
            assert event.tool_call_id in started_tools, "tool args before tool start"
        elif isinstance(event, ToolCallEndEvent):
            ended_tools.add(event.tool_call_id)
    assert started_tools == ended_tools, "every tool call needs a matching START and END"


_AGENT_STEPS = [
    {
        "title": "Agent Steps",
        "contents": [
            {"type": "tool_use", "name": "search", "tool_input": {"q": "weather"}, "output": "sunny", "error": None}
        ],
    }
]


def test_full_agent_flow_sequence_is_well_formed():
    """A realistic ChatInput -> Agent -> ChatOutput run yields a well-formed stream."""
    t = AGUITranslator(run_id="run-1", thread_id="sess-1")
    sequence = [
        ("vertices_sorted", {"ids": ["ChatInput-a"], "to_run": ["ChatInput-a", "Agent-b", "ChatOutput-c"]}),
        ("build_start", {}),
        ("end_vertex", {"build_data": {"id": "ChatInput-a", "valid": True, "data": {"outputs": {}}}}),
        # The agent surfaces its tool step on a partial message update.
        ("add_message", {"id": "m1", "text": "", "properties": {"state": "partial"}, "content_blocks": _AGENT_STEPS}),
        # The agent streams its final answer token by token.
        ("token", {"chunk": "It is ", "id": "m1"}),
        ("token", {"chunk": "sunny.", "id": "m1"}),
        # The complete message finalizes the streamed answer.
        (
            "add_message",
            {"id": "m1", "text": "It is sunny.", "properties": {"state": "complete"}, "content_blocks": _AGENT_STEPS},
        ),
        ("end_vertex", {"build_data": {"id": "Agent-b", "valid": True, "data": {"outputs": {}}}}),
        ("end_vertex", {"build_data": {"id": "ChatOutput-c", "valid": True, "data": {"outputs": {}}}}),
        ("end", {"build_duration": 1.23}),
    ]

    out = _run_sequence(t, sequence)

    _assert_well_formed(out)
    assert isinstance(out[-1], RunFinishedEvent)
    # The tool call appears in two add_message events but is emitted exactly once.
    assert len([e for e in out if isinstance(e, ToolCallStartEvent)]) == 1
    assert len([e for e in out if isinstance(e, ToolCallResultEvent)]) == 1
    # The streamed message has exactly one START/END pair.
    assert len([e for e in out if isinstance(e, TextMessageStartEvent)]) == 1
    assert len([e for e in out if isinstance(e, TextMessageEndEvent)]) == 1
    # Every node ran: three STEP_FINISHED events.
    assert len([e for e in out if isinstance(e, StepFinishedEvent)]) == 3


def test_full_sequence_ending_in_error_is_well_formed():
    """A run that errors mid-stream still closes the open message and ends in RUN_ERROR."""
    t = AGUITranslator(run_id="run-2", thread_id="sess-2")
    sequence = [
        ("vertices_sorted", {"ids": ["ChatInput-a"], "to_run": ["ChatInput-a", "Agent-b"]}),
        ("token", {"chunk": "partial answer", "id": "m1"}),
        ("error", {"text": "the agent crashed"}),
    ]

    out = _run_sequence(t, sequence)

    _assert_well_formed(out)
    assert isinstance(out[-1], RunErrorEvent)
    assert "the agent crashed" in out[-1].message
