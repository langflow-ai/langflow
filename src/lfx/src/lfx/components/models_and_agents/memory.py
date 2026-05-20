from typing import Any, cast
from uuid import UUID

from lfx.custom.custom_component.component import Component
from lfx.helpers.data import data_to_text
from lfx.inputs.inputs import DropdownInput, HandleInput, IntInput, MessageTextInput, MultilineInput, TabInput
from lfx.log.logger import logger
from lfx.memory import aget_messages, astore_message
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx.schema.dotdict import dotdict
from lfx.schema.message import Message
from lfx.template.field.base import Output
from lfx.utils.component_utils import set_current_fields, set_field_display
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_NAME_AI, MESSAGE_SENDER_USER

# Cap on rows we will pull from the DB when the caller has not supplied an
# explicit ``n_messages`` limit. This is a guardrail against unbounded fetches
# (DB pressure, memory) on sessions that accumulate huge histories. The
# trade-off is that sessions with more rows than this cap will not surface
# their oldest messages when no ``n_messages`` is set. See ``aget_messages``
# usage sites below for how this interacts with ordering.
MAX_CHAT_HISTORY_FETCH_LIMIT = 10_000


def _coerce_flow_id_to_uuid(flow_id: str | UUID | None) -> UUID | None:
    """Coerce a graph flow_id (typically str) to UUID for DB filtering.

    Returns ``None`` when ``flow_id`` is missing or cannot be parsed. The
    caller then falls back to the previous **unscoped** retrieval, which
    re-introduces the cross-flow leak that motivated PR #13087. We emit a
    structured ``error`` log on that path (rather than ``warning``) so
    observability can alert on it — see issue #13059 / PR #13087.
    """
    if flow_id is None or flow_id == "":
        return None
    if isinstance(flow_id, UUID):
        return flow_id
    try:
        return UUID(str(flow_id))
    except (ValueError, TypeError, AttributeError):
        # Loud, structured signal — this path means chat history is being
        # served without flow-scoping, which is the privacy bug PR #13087
        # was created to close. Anything matching this event is a candidate
        # for an observability alert.
        logger.error(
            "memory_flow_id_unscoped: flow_id %r is not a valid UUID; "
            "chat history will NOT be scoped by flow_id. This re-enables "
            "cross-flow leakage (issue #13059) for this request.",
            flow_id,
            extra={"event": "memory_flow_id_unscoped", "flow_id_repr": repr(flow_id)},
        )
        return None


def _safe_graph_flow_id(component: Component) -> str | UUID | None:
    """Best-effort lookup of the component's graph flow_id.

    ``Component.graph`` is a property that reaches into ``self._vertex.graph``;
    when a MemoryComponent is constructed ad-hoc (e.g. by the Agent component
    via ``MemoryComponent(**self.get_base_args())``), ``_vertex`` is ``None`` and
    accessing the property raises ``AttributeError``. Swallow that here so
    retrieval falls back to the previous unscoped behavior rather than crashing.
    """
    try:
        graph = component.graph
    except AttributeError:
        return None
    return getattr(graph, "flow_id", None)


async def aget_agent_chat_history(
    *,
    session_id: str | UUID | None,
    flow_id: str | UUID | None,
    context_id: str | None = None,
    n_messages: int | None = None,
) -> list[Message]:
    """Fetch chat history for an agent, scoped to a single flow.

    Centralizes the contract previously implemented by
    ``MemoryComponent.retrieve_messages`` for agent callers:

    * Returns ``[]`` when ``n_messages == 0`` (memory explicitly disabled).
      Without this short-circuit, the bounded query would still execute and
      the caller's ``messages[-0:]`` would return everything.
    * Scopes by ``flow_id`` (coerced to ``UUID``) so default playground
      session names cannot leak history across flows (issue #13059).
    * Returns up to ``n_messages`` most recent messages in ascending order.
      Queries in ``DESC`` order with ``limit=n_messages`` so sessions with
      more than ``MAX_CHAT_HISTORY_FETCH_LIMIT`` rows still see the genuine
      most-recent slice, not the chronological first window.
    """
    if n_messages == 0:
        return []
    fetch_limit = n_messages if n_messages else MAX_CHAT_HISTORY_FETCH_LIMIT
    messages = await aget_messages(
        session_id=session_id,
        context_id=context_id,
        flow_id=_coerce_flow_id_to_uuid(flow_id),
        limit=fetch_limit,
        order="DESC",
    )
    if not n_messages and len(messages) == MAX_CHAT_HISTORY_FETCH_LIMIT:
        # We hit the unbounded-fetch ceiling. The caller will likely see
        # stale "most-recent" history. Flag this so on-call has something
        # to grep when a user reports forgotten context.
        logger.warning(
            "memory_chat_history_limit_reached: hit MAX_CHAT_HISTORY_FETCH_LIMIT=%d "
            "without an explicit n_messages; older messages were not returned.",
            MAX_CHAT_HISTORY_FETCH_LIMIT,
            extra={"event": "memory_chat_history_limit_reached"},
        )
    # ``aget_messages`` returned DESC; reverse to ASC for the agent's prompt.
    return list(reversed(messages))


class MemoryComponent(Component):
    display_name = "Message History"
    description = "Stores or retrieves stored chat messages from Langflow tables or an external memory."
    documentation: str = "https://docs.langflow.org/message-history"
    icon = "message-square-more"
    name = "Memory"
    default_keys = ["mode", "memory", "session_id", "context_id"]
    mode_config = {
        "Store": ["message", "memory", "sender", "sender_name", "session_id", "context_id"],
        "Retrieve": ["n_messages", "order", "template", "memory", "session_id", "context_id"],
    }

    inputs = [
        TabInput(
            name="mode",
            display_name="Mode",
            options=["Retrieve", "Store"],
            value="Retrieve",
            info="Operation mode: Store messages or Retrieve messages.",
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="message",
            display_name="Message",
            info="The chat message to be stored.",
            tool_mode=True,
            dynamic=True,
            show=False,
        ),
        HandleInput(
            name="memory",
            display_name="External Memory",
            input_types=["Memory"],
            info="Retrieve messages from an external memory. If empty, it will use the Langflow tables.",
            advanced=True,
        ),
        DropdownInput(
            name="sender_type",
            display_name="Sender Type",
            options=[MESSAGE_SENDER_AI, MESSAGE_SENDER_USER, "Machine and User"],
            value="Machine and User",
            info="Filter by sender type.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender",
            display_name="Sender",
            info="The sender of the message. Might be Machine or User. "
            "If empty, the current sender parameter will be used.",
            advanced=True,
        ),
        MessageTextInput(
            name="sender_name",
            display_name="Sender Name",
            info="Filter by sender name.",
            advanced=True,
            show=False,
        ),
        IntInput(
            name="n_messages",
            display_name="Number of Messages",
            value=100,
            info="Number of messages to retrieve.",
            advanced=True,
            show=True,
        ),
        MessageTextInput(
            name="session_id",
            display_name="Session ID",
            info="The session ID of the chat. If empty, the current session ID parameter will be used.",
            value="",
            advanced=True,
        ),
        MessageTextInput(
            name="context_id",
            display_name="Context ID",
            info="The context ID of the chat. Adds an extra layer to the local memory.",
            value="",
            advanced=True,
        ),
        DropdownInput(
            name="order",
            display_name="Order",
            options=["Ascending", "Descending"],
            value="Ascending",
            info="Order of the messages.",
            advanced=True,
            tool_mode=True,
            required=True,
        ),
        MultilineInput(
            name="template",
            display_name="Template",
            info="The template to use for formatting the data. "
            "It can contain the keys {text}, {sender} or any other key in the message data.",
            value="{sender_name}: {text}",
            advanced=True,
            show=False,
        ),
    ]

    outputs = [
        Output(
            display_name="Messages",
            name="messages_text",
            method="retrieve_messages_as_text",
            types=["Message"],
            selected="Message",
            dynamic=True,
        ),
        Output(
            display_name="Table",
            name="dataframe",
            method="retrieve_messages_dataframe",
            types=["Table"],
            selected="Table",
            dynamic=True,
        ),
    ]

    def update_outputs(self, frontend_node: dict, field_name: str, field_value: Any) -> dict:
        """Dynamically show only the relevant output based on the selected output type."""
        if field_name == "mode":
            # Start with empty outputs
            frontend_node["outputs"] = []
            if field_value == "Store":
                frontend_node["outputs"] = [
                    Output(
                        display_name="Stored Messages",
                        name="stored_messages",
                        method="store_message",
                        types=["Message"],
                        selected="Message",
                        hidden=True,
                        dynamic=True,
                    )
                ]
            if field_value == "Retrieve":
                frontend_node["outputs"] = [
                    Output(
                        display_name="Messages",
                        name="messages_text",
                        method="retrieve_messages_as_text",
                        types=["Message"],
                        selected="Message",
                        dynamic=True,
                    ),
                    Output(
                        display_name="Table",
                        name="dataframe",
                        method="retrieve_messages_dataframe",
                        types=["Table"],
                        selected="Table",
                        dynamic=True,
                    ),
                ]
        return frontend_node

    async def store_message(self) -> Message:
        message = Message(text=self.message) if isinstance(self.message, str) else self.message

        message.context_id = self.context_id or message.context_id
        message.session_id = self.session_id or message.session_id
        message.sender = self.sender or message.sender or MESSAGE_SENDER_AI
        message.sender_name = self.sender_name or message.sender_name or MESSAGE_SENDER_NAME_AI

        stored_messages: list[Message] = []

        if self.memory:
            self.memory.context_id = message.context_id
            self.memory.session_id = message.session_id
            lc_message = message.to_lc_message()
            await self.memory.aadd_messages([lc_message])

            stored_messages = await self.memory.aget_messages() or []

            stored_messages = [Message.from_lc_message(m) for m in stored_messages] if stored_messages else []

            if message.sender:
                stored_messages = [m for m in stored_messages if m.sender == message.sender]
        else:
            # Single coerced scope used for both the write and the read-back,
            # so a missing/ad-hoc ``_vertex`` cannot crash the write half while
            # the read half degrades gracefully. See PR #13087 review I1.
            flow_id_scope = _coerce_flow_id_to_uuid(_safe_graph_flow_id(self))
            await astore_message(message, flow_id=flow_id_scope)
            stored_messages = (
                await aget_messages(
                    session_id=message.session_id,
                    context_id=message.context_id,
                    sender_name=message.sender_name,
                    sender=message.sender,
                    flow_id=flow_id_scope,
                )
                or []
            )

        if not stored_messages:
            msg = "No messages were stored. Please ensure that the session ID and sender are properly set."
            raise ValueError(msg)

        stored_message = stored_messages[0]
        self.status = stored_message
        return stored_message

    async def retrieve_messages(self) -> Data:
        sender_type = self.sender_type
        sender_name = self.sender_name
        session_id = self.session_id
        context_id = self.context_id
        n_messages = self.n_messages
        order = "DESC" if self.order == "Descending" else "ASC"

        if sender_type == "Machine and User":
            sender_type = None

        if self.memory and not hasattr(self.memory, "aget_messages"):
            memory_name = type(self.memory).__name__
            err_msg = f"External Memory object ({memory_name}) must have 'aget_messages' method."
            raise AttributeError(err_msg)
        # Check if n_messages is None or 0
        if n_messages == 0:
            stored = []
        elif self.memory:
            # override session_id
            self.memory.session_id = session_id
            self.memory.context_id = context_id

            stored = await self.memory.aget_messages()
            # langchain memories are supposed to return messages in ascending order

            if n_messages:
                stored = stored[-n_messages:]  # Get last N messages first

            if order == "DESC":
                stored = stored[::-1]  # Then reverse if needed

            stored = [Message.from_lc_message(m) for m in stored]
            if sender_type:
                expected_type = MESSAGE_SENDER_AI if sender_type == MESSAGE_SENDER_AI else MESSAGE_SENDER_USER
                stored = [m for m in stored if m.type == expected_type]
        else:
            # For internal memory, fetch the last N messages by ordering DESC at the
            # DB layer so sessions with more than ``MAX_CHAT_HISTORY_FETCH_LIMIT``
            # rows still return the genuine most-recent slice rather than the
            # chronological first window. See PR #13087 review I2.
            #
            # Scope by flow_id so default session names (e.g. "New Session 0") do not
            # leak chat history across unrelated flows. See issue #13059.
            flow_id_scope = _coerce_flow_id_to_uuid(_safe_graph_flow_id(self))
            fetch_limit = n_messages if n_messages else MAX_CHAT_HISTORY_FETCH_LIMIT
            stored = await aget_messages(
                sender=sender_type,
                sender_name=sender_name,
                session_id=session_id,
                context_id=context_id,
                flow_id=flow_id_scope,
                limit=fetch_limit,
                order="DESC",
            )
            if not n_messages and len(stored) == MAX_CHAT_HISTORY_FETCH_LIMIT:
                logger.warning(
                    "memory_chat_history_limit_reached: hit MAX_CHAT_HISTORY_FETCH_LIMIT=%d "
                    "without an explicit n_messages; older messages were not returned.",
                    MAX_CHAT_HISTORY_FETCH_LIMIT,
                    extra={"event": "memory_chat_history_limit_reached"},
                )
            # Honor the user-selected order: we fetched DESC, reverse if ASC requested.
            if order == "ASC":
                stored = list(reversed(stored))

        # self.status = stored
        return cast("Data", stored)

    async def retrieve_messages_as_text(self) -> Message:
        stored_text = data_to_text(self.template, await self.retrieve_messages())
        # self.status = stored_text
        return Message(text=stored_text)

    async def retrieve_messages_dataframe(self) -> DataFrame:
        """Convert the retrieved messages into a DataFrame.

        Returns:
            DataFrame: A DataFrame containing the message data.
        """
        messages = await self.retrieve_messages()
        return DataFrame(messages)

    def update_build_config(
        self,
        build_config: dotdict,
        field_value: Any,  # noqa: ARG002
        field_name: str | None = None,  # noqa: ARG002
    ) -> dotdict:
        return set_current_fields(
            build_config=build_config,
            action_fields=self.mode_config,
            selected_action=build_config["mode"]["value"],
            default_fields=self.default_keys,
            func=set_field_display,
        )
