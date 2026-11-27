"""Properties and Source schema classes copied from langflow for lfx package."""

from typing import Literal

from pydantic import BaseModel, Field, field_serializer, field_validator


class Source(BaseModel):
    id: str | None = Field(default=None, description="The id of the source component.")
    display_name: str | None = Field(default=None, description="The display name of the source component.")
    source: str | None = Field(
        default=None,
        description="The source of the message. Normally used to display the model name (e.g. 'gpt-4o')",
    )


class Usage(BaseModel):
    """Token usage information from LLM responses."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class ContextEvent(BaseModel):
    """A change to the context of an Agent run: a session fold or an in-run compaction.

    The same event (same ``id``) moves from ``running`` to ``done`` or ``failed``. ``messages`` is the number
    of folded messages. ``tokens_before`` and ``tokens_after`` give the size of a compaction. ``duration``
    is in milliseconds. The UI writes the text, so the event holds no prose.
    """

    id: str
    kind: Literal["fold", "compaction"]
    state: Literal["running", "done", "failed"] = "running"
    messages: int | None = None
    tokens_before: int | None = None
    tokens_after: int | None = None
    duration: int | None = None


class Properties(BaseModel):
    text_color: str | None = None
    background_color: str | None = None
    edited: bool = False
    source: Source = Field(default_factory=Source)
    icon: str | None = None
    allow_markdown: bool = False
    positive_feedback: bool | None = None
    state: Literal["partial", "complete"] = "complete"
    targets: list = []
    usage: Usage | None = None
    build_duration: float | None = None
    # Agent "Auto" chat history mode: folds and compactions of this run, shown in the chat.
    context_events: list[ContextEvent] | None = None

    @field_validator("source", mode="before")
    @classmethod
    def validate_source(cls, v):
        if isinstance(v, str):
            return Source(id=v, display_name=v, source=v)
        if v is None:
            return Source()
        return v

    @field_serializer("source")
    def serialize_source(self, value):
        if isinstance(value, Source):
            return value.model_dump()
        return value
