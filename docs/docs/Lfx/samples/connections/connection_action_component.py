"""Sample connection-backed action for headless LFX hosts.

The component declares a portable connection reference, asks the host to resolve
it into a short-lived credential, and reports only non-secret facts about the
result. Copy this shape for your own actions: a component never reads an access
token out of a flow field, never logs one, and never returns one.

Run it with the flow built by :func:`build_graph`:

    export LF_CONNECTION__GOOGLE__WORK='ya29.a0-example-access-token'
    uv run lfx run connection_action_component.py "describe my connection"

Serve it and inject the credential per request instead:

    uv run lfx serve connection_action_component.py --no-env-fallback
"""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.graph import Graph
from lfx.integrations import integration_action
from lfx.io import ConnectionRefInput, MessageTextInput, Output
from lfx.schema.message import Message

PROVIDER = "google"
REQUIRED_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


class ConnectionAccountComponent(Component):
    """Resolve a connection and describe the account behind it."""

    display_name = "Google: Describe Connection"
    description = "Resolve a connection reference and report the account and granted scopes."
    icon = "Google"
    name = "SampleConnectionAccount"

    inputs = [
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Ignored by this sample; present so the component can sit in a chat flow.",
            required=False,
        ),
        ConnectionRefInput(
            name="connection",
            display_name="Connection",
            provider=PROVIDER,
            required_scopes=REQUIRED_SCOPES,
            info="Portable handle such as google/work. Never a token.",
        ),
    ]

    outputs = [
        Output(display_name="Account", name="account", method="describe_connection"),
    ]

    async def describe_connection(self) -> Message:
        """Resolve the connection and return non-secret details about it.

        ``resolve_connection`` returns a lazy lease: nothing is resolved until
        ``get_credential`` (or ``get_token``) is awaited, and the lease refreshes
        under a single lock when the cached token nears expiry. Resolution failures
        arrive as the sanitized ``lfx.integrations.errors`` types, so the message
        that reaches a client or a log never contains a credential.
        """
        lease = self.resolve_connection("connection")
        async with integration_action(
            self,
            provider=PROVIDER,
            capability="drive.describe",
            owner_kind="env",
        ):
            credential = await lease.get_credential()

        account = credential.account.id if credential.account is not None else "unknown"
        scopes = ", ".join(sorted(credential.granted_scopes)) or "not reported"
        # credential.access_token is a SecretStr and ResolvedCredential refuses
        # pickling, so neither this text nor a graph snapshot can carry the token.
        text = (
            f"connection={lease.ref.to_handle()} account={account} "
            f"token_type={credential.token_type} scopes_verified={credential.scopes_verified} "
            f"granted_scopes={scopes}"
        )
        self.status = text
        return Message(text=text)


def build_graph(connection: str = "google/work") -> Graph:
    """Build the one-action flow used by the docs, ``lfx run``, and ``lfx serve``."""
    from lfx.components.input_output import ChatInput, ChatOutput

    chat_input = ChatInput()
    account = ConnectionAccountComponent().set(
        connection=connection,
        input_value=chat_input.message_response,
    )
    chat_output = ChatOutput().set(input_value=account.describe_connection)
    return Graph(chat_input, chat_output)


graph = build_graph()
