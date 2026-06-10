"""AG-UI translator.

Converts Langflow ``EventManager`` events into AG-UI protocol events. The
``EventManager`` queue is Langflow's internal event seam; this translator is the
one place that maps that vocabulary onto AG-UI, so the v2 workflows endpoint can
stream a standard AG-UI event stream.

One Langflow event may map to several AG-UI events, so ``translate`` returns a
list. The translator is stateful: one instance per run.
"""

from __future__ import annotations

import json

from ag_ui.core import (
    BaseEvent,
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

# Langflow content-block types with no standard AG-UI primitive. They ride as
# CUSTOM events namespaced ``langflow.*``; generic AG-UI clients ignore them.
_CUSTOM_CONTENT_TYPES = frozenset({"json", "code", "media", "error"})


class AGUITranslator:
    """Translates Langflow ``EventManager`` events into AG-UI protocol events.

    Use one instance per run. Call :meth:`start` once to open the run, then
    :meth:`translate` for each ``EventManager`` event.
    """

    def __init__(self, run_id: str, thread_id: str) -> None:
        self.run_id = run_id
        self.thread_id = thread_id
        # Id of the text message currently being streamed by ``token`` events,
        # or ``None`` when no message is open.
        self._open_message_id: str | None = None
        # Message ids already emitted as a complete (non-streamed) text message.
        self._emitted_text_message_ids: set[str] = set()
        # Tool-call ids already emitted as TOOL_CALL_START / already resolved
        # with a TOOL_CALL_RESULT. ``add_message`` can re-fire with the same
        # (append-only) content_blocks, so emissions must be deduplicated.
        self._started_tool_calls: set[str] = set()
        self._resulted_tool_calls: set[str] = set()
        # Custom content blocks already emitted as CUSTOM events, mapped to a
        # fingerprint of their last-emitted payload so in-place updates re-emit.
        self._emitted_content_state: dict[str, str] = {}

    def start(self) -> list[BaseEvent]:
        """Open the run.

        Emits ``RUN_STARTED`` and an empty node-graph ``STATE_SNAPSHOT``. The
        snapshot establishes ``/nodes`` so every later node ``STATE_DELTA`` has a
        parent to patch, regardless of which execution path drives the run.
        """
        return [
            RunStartedEvent(run_id=self.run_id, thread_id=self.thread_id),
            StateSnapshotEvent(snapshot={"nodes": {}}),
        ]

    def translate(self, event_type: str, data: dict) -> list[BaseEvent]:
        """Map one ``EventManager`` event to zero or more AG-UI events."""
        if event_type == "token":
            return self._translate_token(data)
        if event_type == "vertices_sorted":
            return self._translate_vertices_sorted(data)
        if event_type == "build_start":
            return self._translate_build_start(data)
        if event_type == "end_vertex":
            return self._translate_end_vertex(data)
        if event_type == "add_message":
            return self._translate_add_message(data)
        if event_type == "log":
            return [CustomEvent(name="langflow.log", value=data)]
        if event_type == "remove_message":
            return [CustomEvent(name="langflow.message.removed", value={"message_id": str(data.get("id") or "")})]

        # Only terminal events close an open text message. Non-terminal events
        # (build_start, end_vertex, log, ...) interleave with tokens of the same
        # streamed message and must stay transparent, or the message would be
        # split into multiple START/END pairs reusing an already-ended id.
        if event_type == "end":
            events = self._close_open_message()
            events.append(RunFinishedEvent(run_id=self.run_id, thread_id=self.thread_id))
            return events
        if event_type == "error":
            events = self._close_open_message()
            # The ``error`` payload varies by emission path: a full ErrorMessage
            # dump carries the reason in ``text``; the minimal path sends
            # ``{"error": str}``.
            message = data.get("text") or data.get("error") or "Unknown error"
            events.append(RunErrorEvent(message=str(message)))
            return events
        return []

    def _translate_token(self, data: dict) -> list[BaseEvent]:
        """Map a ``token`` event to text-message events.

        The first token of a message opens it with ``TEXT_MESSAGE_START``; a
        token for a different message id closes the previous one first. A
        token whose id was already ended via ``add_message`` (or a prior
        token boundary) is dropped: re-opening it would emit a second
        ``TEXT_MESSAGE_START`` for an id the protocol considers closed.
        """
        message_id = str(data.get("id") or "")
        if not message_id:
            # Without a stable id the AG-UI lifecycle (START/CONTENT/END) cannot
            # be correlated. Dropping the event is preferable to emitting a
            # malformed stream with empty message_ids.
            return []
        if message_id in self._emitted_text_message_ids and self._open_message_id != message_id:
            return []
        chunk = data.get("chunk", "")
        events: list[BaseEvent] = []
        if self._open_message_id != message_id:
            events.extend(self._close_open_message())
            events.append(TextMessageStartEvent(message_id=message_id, role="assistant"))
            self._open_message_id = message_id
        events.append(TextMessageContentEvent(message_id=message_id, delta=chunk))
        return events

    def _translate_vertices_sorted(self, data: dict) -> list[BaseEvent]:
        """Map ``vertices_sorted`` to a ``STATE_SNAPSHOT`` of the node graph.

        Seeds every node that will run with ``pending`` status so the canvas can
        render the graph before execution begins. ``to_run`` is the full run set;
        ``ids`` (the first layer only) is the fallback.
        """
        node_ids = data.get("to_run") or data.get("ids") or []
        snapshot = {"nodes": {node_id: {"status": "pending", "output": None} for node_id in node_ids}}
        return [StateSnapshotEvent(snapshot=snapshot)]

    def _translate_build_start(self, data: dict) -> list[BaseEvent]:
        """Map a per-node ``build_start`` to a ``STEP_STARTED`` + a running ``STATE_DELTA``.

        The graph-level ``build_start`` (the ``/build`` path) carries no ``id`` and
        is a no-op here: ``RUN_STARTED`` already signals the run beginning.
        """
        node_id = data.get("id")
        if not node_id:
            return []
        return [
            StepStartedEvent(step_name=node_id),
            StateDeltaEvent(delta=[self._set_node(node_id, "running", None)]),
        ]

    def _translate_end_vertex(self, data: dict) -> list[BaseEvent]:
        """Map ``end_vertex`` to a ``STEP_FINISHED`` + a ``STATE_DELTA`` for status and output."""
        build_data = data.get("build_data") or {}
        node_id = build_data.get("id")
        if not node_id:
            return []
        status = "success" if build_data.get("valid") else "error"
        return [
            StepFinishedEvent(step_name=node_id),
            StateDeltaEvent(delta=[self._set_node(node_id, status, build_data.get("data"))]),
        ]

    def _translate_add_message(self, data: dict) -> list[BaseEvent]:
        """Map an ``add_message`` to text-message and tool-call events.

        ``add_message`` can fire repeatedly for one message as its content grows;
        emissions are deduplicated by message id and tool-call id.
        """
        message_id = str(data.get("id") or "")
        events: list[BaseEvent] = []

        # Content blocks: tool_use becomes tool-call events, the Langflow-specific
        # content types become namespaced CUSTOM events.
        for block_index, block in enumerate(data.get("content_blocks") or []):
            if not isinstance(block, dict):
                continue
            for content_index, content in enumerate(block.get("contents") or []):
                if not isinstance(content, dict):
                    continue
                content_type = content.get("type")
                if content_type == "tool_use":
                    events.extend(self._translate_tool_use(message_id, block_index, content_index, content))
                elif content_type in _CUSTOM_CONTENT_TYPES:
                    events.extend(
                        self._translate_custom_content(message_id, block, block_index, content_index, content)
                    )

        # Message text.
        if message_id and message_id == self._open_message_id:
            # Finalizer of a token-streamed message: close it. The text was
            # already streamed token by token, so it must not be re-emitted now
            # or by any later add_message that re-fires for the same id.
            self._emitted_text_message_ids.add(message_id)
            events.extend(self._close_open_message())
        else:
            text = data.get("text") or ""
            # Skip text-message lifecycle emission without a stable message_id;
            # tool-call events above are namespaced by block/content index so
            # they can still ride a missing id, but TEXT_MESSAGE_* cannot.
            if text and message_id and message_id not in self._emitted_text_message_ids:
                self._emitted_text_message_ids.add(message_id)
                events.append(TextMessageStartEvent(message_id=message_id, role="assistant"))
                events.append(TextMessageContentEvent(message_id=message_id, delta=text))
                events.append(TextMessageEndEvent(message_id=message_id))
        return events

    def _translate_tool_use(
        self, message_id: str, block_index: int, content_index: int, content: dict
    ) -> list[BaseEvent]:
        """Map one ``tool_use`` content block to tool-call lifecycle events.

        ``ToolContent`` has no id, so a stable tool-call id is derived from the
        tool's position in the (append-only) content_blocks structure.
        """
        tool_call_id = f"{message_id}:tool:{block_index}:{content_index}"
        events: list[BaseEvent] = []

        if tool_call_id not in self._started_tool_calls:
            self._started_tool_calls.add(tool_call_id)
            tool_input = content.get("tool_input")
            if tool_input is None:
                tool_input = content.get("input")
            events.append(
                ToolCallStartEvent(
                    tool_call_id=tool_call_id,
                    tool_call_name=content.get("name") or "tool",
                    parent_message_id=message_id,
                )
            )
            events.append(ToolCallArgsEvent(tool_call_id=tool_call_id, delta=json.dumps(tool_input)))
            events.append(ToolCallEndEvent(tool_call_id=tool_call_id))

        if tool_call_id not in self._resulted_tool_calls:
            error = content.get("error")
            result = error if error is not None else content.get("output")
            if result is not None:
                self._resulted_tool_calls.add(tool_call_id)
                events.append(
                    ToolCallResultEvent(
                        message_id=message_id,
                        tool_call_id=tool_call_id,
                        content=result if isinstance(result, str) else json.dumps(result),
                    )
                )
        return events

    def _translate_custom_content(
        self, message_id: str, block: dict, block_index: int, content_index: int, content: dict
    ) -> list[BaseEvent]:
        """Map a Langflow-specific content block to a namespaced CUSTOM event.

        Deduplicated by content state: a re-fired ``add_message`` whose block is
        unchanged emits nothing, but an in-place update to the block re-emits.
        """
        key = f"{message_id}:content:{block_index}:{content_index}"
        fingerprint = json.dumps(content, sort_keys=True, default=str)
        if self._emitted_content_state.get(key) == fingerprint:
            return []
        self._emitted_content_state[key] = fingerprint
        return [
            CustomEvent(
                name=f"langflow.content.{content['type']}",
                value={"message_id": message_id, "block_title": block.get("title"), "content": content},
            )
        ]

    @staticmethod
    def _set_node(node_id: str, status: str, output: object) -> dict:
        """Build the RFC 6902 op that writes a node's state.

        ``add`` on ``/nodes/{id}`` is create-or-replace: it applies whether or not
        the node was pre-seeded by a ``vertices_sorted`` snapshot, so the
        translator does not depend on event ordering across execution paths.
        """
        return {"op": "add", "path": f"/nodes/{node_id}", "value": {"status": status, "output": output}}

    def _close_open_message(self) -> list[BaseEvent]:
        """Emit ``TEXT_MESSAGE_END`` for the open message, if any.

        The closed id is recorded in ``_emitted_text_message_ids`` so a later
        token (e.g. an interleaved ``A, B, A`` sequence) cannot re-open it
        and emit a second ``TEXT_MESSAGE_START`` for an id the protocol
        already considers closed.
        """
        if self._open_message_id is None:
            return []
        closed_id = self._open_message_id
        end = TextMessageEndEvent(message_id=closed_id)
        self._emitted_text_message_ids.add(closed_id)
        self._open_message_id = None
        return [end]
