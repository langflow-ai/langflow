"""Pydantic models mirroring the Langflow REST API request/response shapes."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Flow models
# ---------------------------------------------------------------------------


class FlowCreate(BaseModel):
    """Payload for creating a new flow."""

    name: str
    description: str | None = None
    data: dict[str, Any] | None = None
    is_component: bool = False
    endpoint_name: str | None = None
    tags: list[str] | None = None
    folder_id: UUID | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    locked: bool = False
    mcp_enabled: bool = False


class FlowUpdate(BaseModel):
    """Payload for partially updating a flow (all fields optional)."""

    name: str | None = None
    description: str | None = None
    data: dict[str, Any] | None = None
    endpoint_name: str | None = None
    tags: list[str] | None = None
    folder_id: UUID | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    locked: bool | None = None
    mcp_enabled: bool | None = None


class Flow(BaseModel):
    """A flow returned by the Langflow API."""

    id: UUID
    name: str
    description: str | None = None
    data: dict[str, Any] | None = None
    is_component: bool = False
    updated_at: datetime | None = None
    endpoint_name: str | None = None
    tags: list[str] | None = None
    folder_id: UUID | None = None
    user_id: UUID | None = None
    icon: str | None = None
    icon_bg_color: str | None = None
    locked: bool = False
    mcp_enabled: bool = False
    webhook: bool = False
    access_type: str = "PRIVATE"


# ---------------------------------------------------------------------------
# Project (Folder) models
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    """Payload for creating a new project (folder)."""

    name: str
    description: str | None = None
    flows_list: list[UUID] | None = None
    components_list: list[UUID] | None = None


class ProjectUpdate(BaseModel):
    """Payload for updating a project."""

    name: str | None = None
    description: str | None = None


class Project(BaseModel):
    """A project (folder) returned by the Langflow API."""

    id: UUID
    name: str
    description: str | None = None
    parent_id: UUID | None = None


class ProjectWithFlows(Project):
    """A project with its flows included."""

    flows: list[Flow] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Run models
# ---------------------------------------------------------------------------


class RunInput(BaseModel):
    """A single named input for a flow run."""

    components: list[str] = Field(default_factory=list)
    input_value: str = ""
    type: str = "chat"


class RunRequest(BaseModel):
    """Payload for running a flow via the API."""

    input_value: str = ""
    input_type: str = "chat"
    output_type: str = "chat"
    tweaks: dict[str, Any] | None = None
    stream: bool = False


class RunOutput(BaseModel):
    """A single output from a flow run."""

    results: dict[str, Any] = Field(default_factory=dict)
    artifacts: dict[str, Any] = Field(default_factory=dict)
    outputs: list[dict[str, Any]] = Field(default_factory=list)
    session_id: str | None = None
    timedelta: float | None = None

    def first_text(self) -> str | None:
        """Extract the first text value from this output block.

        Tries the standard chat message path (``results.message.text``) then
        a direct ``results.text`` path across each component output.
        Returns ``None`` if no text is found.
        """
        for component_out in self.outputs:
            results = component_out.get("results", {})
            # Standard Langflow chat output: results -> message -> text
            msg = results.get("message")
            if isinstance(msg, dict):
                text = msg.get("text")
                if text is not None:
                    return str(text)
            # Direct text result (some custom components)
            text = results.get("text")
            if text is not None:
                return str(text)
        return None

    def has_errors(self) -> bool:
        """Return ``True`` if any component output in this block contains an error.

        Checks each component output dict for an ``"error"`` key, and also
        inspects the top-level ``artifacts`` dict.

        Adapted from ``WorkflowResponse.has_errors()`` in langflow-ai/sdk
        (Janardan Singh Kavia, IBM Corp., Apache 2.0).
        """
        for component_out in self.outputs:
            if component_out.get("error"):
                return True
        return bool(self.artifacts.get("error"))


class RunResponse(BaseModel):
    """The full response from a flow run."""

    session_id: str | None = None
    outputs: list[RunOutput] = Field(default_factory=list)

    def first_text_output(self) -> str | None:
        """Return the first text extracted from any output block, or ``None``.

        Convenience shortcut for the common case of reading a single chat
        response::

            text = response.first_text_output()
            assert text is not None
        """
        for output in self.outputs:
            text = output.first_text()
            if text is not None:
                return text
        return None

    def all_text_outputs(self) -> list[str]:
        """Return all text values across every output block.

        Useful when a flow produces multiple outputs::

            texts = response.all_text_outputs()
            assert len(texts) == 2
        """
        return [text for output in self.outputs if (text := output.first_text()) is not None]

    # ------------------------------------------------------------------
    # WorkflowResponse-style helpers
    # (adapted from langflow-ai/sdk, Janardan Singh Kavia, IBM Corp.,
    #  Apache 2.0 — https://github.com/langflow-ai/sdk/pull/1)
    # ------------------------------------------------------------------

    def get_chat_output(self) -> str | None:
        """Return the first chat text output, or ``None``.

        Convenience alias for :meth:`first_text_output` using the naming
        convention from the Langflow V2 SDK::

            text = response.get_chat_output()
        """
        return self.first_text_output()

    def get_all_outputs(self) -> list[RunOutput]:
        """Return all output blocks as a list.

        Useful when iterating over every component's output::

            for out in response.get_all_outputs():
                print(out.first_text())
        """
        return list(self.outputs)

    def get_text_outputs(self) -> list[str]:
        """Return all non-empty text values across every output block.

        Alias for :meth:`all_text_outputs` using V2-SDK naming::

            texts = response.get_text_outputs()
        """
        return self.all_text_outputs()

    def has_errors(self) -> bool:
        """Return ``True`` if any output block reports an error.

        Adapted from ``WorkflowResponse.has_errors()`` in langflow-ai/sdk
        (Janardan Singh Kavia, IBM Corp., Apache 2.0).
        """
        return any(output.has_errors() for output in self.outputs)

    def is_completed(self) -> bool:
        """Return ``True`` when the run finished with at least one output and no errors.

        For V1 synchronous runs this is equivalent to checking that the
        server returned usable output.  Adapted from
        ``WorkflowResponse.is_completed()`` in langflow-ai/sdk
        (Janardan Singh Kavia, IBM Corp., Apache 2.0).
        """
        return bool(self.outputs) and not self.has_errors()

    def is_failed(self) -> bool:
        """Return ``True`` when the run produced no outputs or contains errors.

        Adapted from ``WorkflowResponse.is_failed()`` in langflow-ai/sdk
        (Janardan Singh Kavia, IBM Corp., Apache 2.0).
        """
        return not self.outputs or self.has_errors()

    def is_in_progress(self) -> bool:
        """Always ``False`` for V1 synchronous runs.

        Included for API parity with :class:`BackgroundJob` and the Langflow
        V2 SDK (Janardan Singh Kavia, IBM Corp., Apache 2.0) so that callers
        can use a uniform status-check pattern across both sync and background
        execution paths.
        """
        return False


# ---------------------------------------------------------------------------
# Streaming models
# ---------------------------------------------------------------------------


class StreamChunk(BaseModel):
    """A single event chunk from a streaming flow run.

    Events emitted by the Langflow backend:

    - ``token`` — incremental LLM token; ``data["chunk"]`` holds the text.
    - ``add_message`` — a complete message was added to the session.
    - ``end_vertex`` — a vertex finished executing.
    - ``end`` — the flow finished; ``data["result"]`` holds the full
      :class:`RunResponse` payload.
    - ``error`` — an error occurred; ``data["error"]`` holds the message.

    Example::

        for chunk in client.stream("my-flow", input_value="Hello"):
            if chunk.is_token:
                print(chunk.text, end="", flush=True)
    """

    event: str
    data: dict[str, Any] = Field(default_factory=dict)

    @property
    def text(self) -> str | None:
        """The text content of this chunk, if any.

        Returns ``data["chunk"]`` for ``token`` events and the message text
        for ``add_message`` events.  ``None`` for all other event types.
        """
        if self.event == "token":
            return self.data.get("chunk")
        if self.event == "add_message":
            msg = self.data.get("message", {})
            if isinstance(msg, dict):
                return msg.get("text")
        return None

    @property
    def is_token(self) -> bool:
        """``True`` for incremental LLM token events."""
        return self.event == "token"

    @property
    def is_end(self) -> bool:
        """``True`` for the final ``end`` event."""
        return self.event == "end"

    @property
    def is_error(self) -> bool:
        """``True`` for ``error`` events."""
        return self.event == "error"

    def final_response(self) -> RunResponse | None:
        """Parse and return the :class:`RunResponse` from an ``end`` event.

        Returns ``None`` for all other event types.
        """
        if self.event == "end":
            result = self.data.get("result")
            if result:
                return RunResponse.model_validate(result)
        return None
