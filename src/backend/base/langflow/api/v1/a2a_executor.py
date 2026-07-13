"""Protocol-pure A2A AgentExecutor for Langflow flows.

Deliberately free of langflow imports (only the a2a SDK, ``lfx.schema.workflow``,
and stdlib) so it can move to lfx when the A2A protocol layer is extracted. The
langflow-bound seam (flow lookup, v2 execution, gating) lives in ``a2a.py`` and
is injected as the ``run_flow`` callable.

The a2a-sdk 1.x server stack is protobuf-based (``a2a.types.a2a_pb2``); the
spec-name methods ``message/send`` / ``tasks/get`` reach it through the v0.3
compat adapter wired up in ``a2a.py``.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from a2a.helpers.proto_helpers import get_data_parts, new_data_part, new_text_part
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import a2a_pb2 as pb
from lfx.schema.workflow import JobStatus, OutputReason, WorkflowExecutionResponse

logger = logging.getLogger(__name__)

# (flow_id, task_id, input_text, context_id) -> the v2 sync run result.
# context_id scopes the run's chat memory (the A2A conversation = the flow session).
RunFlow = Callable[[UUID, str, str, str | None], Awaitable[WorkflowExecutionResponse]]
# (flow_id, task_id, decision_text) -> the run result after applying a human decision to a
# paused (input-required) task. The text carries the chosen action for the HumanInput node.
ResumeFlow = Callable[[UUID, str, str], Awaitable[WorkflowExecutionResponse]]


def _json_safe(content: object) -> object:
    """Coerce a data-output payload to a JSON-native value for ``new_data_part``.

    ``new_data_part`` serializes via ``ParseDict`` into a protobuf ``Value``, which rejects
    non-JSON-native values (datetime, UUID, a pydantic model such as lfx ``OutputValue``). Round-trip
    through json, dumping pydantic models and str-ifying anything else, so a data-typed flow output
    can't raise a ParseError mid-artifact and leave the task with no terminal event.
    """

    def _default(obj: object) -> object:
        dump = getattr(obj, "model_dump", None)
        return dump(mode="json") if callable(dump) else str(obj)

    return json.loads(json.dumps(content, default=_default))


def _answer_parts(response: WorkflowExecutionResponse) -> list[pb.Part]:
    """The run's answer as A2A artifact parts: text for string channels, data for the rest.

    SINGLE is the canonical agent shape (one ChatOutput); preserve its text, including an
    intentional "". Otherwise read each ``outputs`` channel: a string message/text becomes a
    text part, and anything else that carries content (a ``data``-typed output, or a non-string
    payload) becomes an ``application/json`` data part, so a structured / data-only flow emits
    its JSON instead of being silently dropped to an empty text answer. The card already
    advertises ``application/json`` output, so this makes that contract real.
    """
    if response.output.reason == OutputReason.SINGLE:
        return [new_text_part(response.output.text or "")]
    parts: list[pb.Part] = []
    for output in response.outputs.values():
        if output.content is None:
            continue
        if output.type in {"message", "text"} and isinstance(output.content, str):
            parts.append(new_text_part(output.content))
        else:
            parts.append(new_data_part(_json_safe(output.content), media_type="application/json"))
    return parts


class FlowAgentExecutor(AgentExecutor):
    """Runs a Langflow flow for one A2A ``message/send`` and reports a terminal Task."""

    def __init__(self, run_flow: RunFlow, resume_flow: ResumeFlow) -> None:
        self._run_flow = run_flow
        self._resume_flow = resume_flow

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        flow_id = context.call_context.state["flow_id"]

        # A follow-up message on an input-required task resumes the paused run with the
        # message as the human decision; a first message starts a fresh run. The SDK only
        # routes a follow-up here when the existing (owner-scoped) task is non-terminal.
        existing = context.current_task
        resuming = existing is not None and existing.status.state == pb.TaskState.TASK_STATE_INPUT_REQUIRED

        if not resuming:
            # DefaultRequestHandlerV2 rejects a status/artifact event before a Task
            # event ("Agent should enqueue Task before TaskStatusUpdateEvent"), and
            # this SDK version has no new_task helper, so enqueue the proto Task first.
            # On resume the Task already exists, so don't re-submit it.
            await event_queue.enqueue_event(
                pb.Task(
                    id=context.task_id,
                    context_id=context.context_id,
                    status=pb.TaskStatus(state=pb.TaskState.TASK_STATE_SUBMITTED),
                )
            )
        updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        await updater.start_work()

        text = context.get_user_input()
        if not text and context.message is not None:
            # A caller can send structured input as DataPart(s) with no text. The flow input is
            # a text channel, so serialize the data to JSON so it reaches the flow rather than
            # being dropped. Plain-text input is untouched (the common case).
            data = get_data_parts(context.message.parts)
            if data:
                text = json.dumps(data[0] if len(data) == 1 else data)
        try:
            if resuming:
                response = await self._resume_flow(UUID(flow_id), context.task_id, text)
            else:
                response = await self._run_flow(UUID(flow_id), context.task_id, text, context.context_id)
        except asyncio.CancelledError:
            # tasks/cancel preempted this live run (the SDK cancels the producer task). Emit a
            # terminal CANCELED on this producer's OWN queue before it closes, so the original
            # message/send / message/stream consumer gets a terminal event instead of hanging on the
            # last 'working' state, then propagate the cancellation (never swallow it, or the task
            # won't wind down). The durable store is set to CANCELED by the request handler.
            with contextlib.suppress(Exception):
                await updater.cancel()
            raise
        except Exception:
            # Unexpected build/timeout/system failures become a failed Task, not a 500.
            # The endpoint is unauthenticated, so don't hand the caller raw exception
            # text (graph-build internals, DB errors); log it server-side instead.
            logger.exception("A2A flow execution failed for task %s", context.task_id)
            await updater.failed(updater.new_agent_message([new_text_part("Flow execution failed")]))
            return

        # The run paused for human input: park the task as input-required carrying the prompt,
        # so a follow-up message resumes it. Not terminal, so the task stays open.
        if response.status == JobStatus.SUSPENDED:
            prompt = (response.human_request or {}).get("prompt") or "Input required"
            await updater.requires_input(updater.new_agent_message([new_text_part(prompt)]))
            return

        # Component/runtime errors come back in-band as a FAILED status, not raised.
        # ponytail: this in-band branch needs a flow that builds then errors at a
        # component to exercise; left to the suite's raised-failure coverage this slice.
        if response.status == JobStatus.FAILED or response.has_errors:
            detail = "; ".join(error.error for error in response.errors) or "Flow execution failed"
            await updater.failed(updater.new_agent_message([new_text_part(detail)]))
            return

        # Emit the answer artifact and complete. This runs OUTSIDE the try above, and _answer_parts
        # serializes arbitrary flow output, so guard it: an unexpected serialization failure here
        # would escape execute() and leave the task with no terminal event (stuck 'working'). Downgrade
        # any such failure to a terminal 'failed' instead.
        try:
            parts = _answer_parts(response)
            await updater.add_artifact(parts or [new_text_part("")], name="result")
            await updater.complete()
        except Exception:
            logger.exception("A2A artifact emission failed for task %s", context.task_id)
            await updater.failed(updater.new_agent_message([new_text_part("Flow execution failed")]))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        # The durable terminal CANCELED is written by the request handler (see a2a.py); here we only
        # emit the terminal cancel event so a live message/stream subscriber sees it. Must not raise:
        # the SDK marks the task FAILED if agent cancel raises, so suppress a failed emit (e.g. an
        # already-closed queue). Only invoked for a live producer; a parked (finished) task's cancel
        # is handled entirely in the handler.
        with contextlib.suppress(Exception):
            await TaskUpdater(event_queue, context.task_id, context.context_id).cancel()
