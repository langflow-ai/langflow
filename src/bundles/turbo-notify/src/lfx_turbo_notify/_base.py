"""Inputs and client shared by every Turbo Notify component."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import MessageTextInput, SecretStrInput

from lfx_turbo_notify._client import DEFAULT_BASE_URL, DEFAULT_NUMBER_ALIAS, TurboNotifyClient


def connection_inputs() -> list:
    """Return the API key, number alias and base URL inputs that open every component."""
    return [
        SecretStrInput(
            name="api_key",
            display_name="Turbo Notify API Key",
            required=True,
            password=True,
            info="Your Turbo Notify API key, created in the Turbo Notify dashboard under API keys.",
        ),
        MessageTextInput(
            name="number_alias",
            display_name="Number",
            value=DEFAULT_NUMBER_ALIAS,
            info="The WhatsApp number to use: main, the alias of an extra number, or its num_ id.",
        ),
    ]


def base_url_input() -> MessageTextInput:
    """Return the advanced Base URL input, kept last so it stays out of the way."""
    return MessageTextInput(
        name="base_url",
        display_name="Base URL",
        value=DEFAULT_BASE_URL,
        advanced=True,
        info="The Turbo Notify API address. Change it only if Turbo Notify gave you another one.",
    )


def idempotency_key_input() -> MessageTextInput:
    """Return the advanced Idempotency Key input shared by the components that send."""
    return MessageTextInput(
        name="idempotency_key",
        display_name="Idempotency Key",
        advanced=True,
        info=(
            "Optional, 1 to 255 printable characters. If a send is repeated with the same key on the same number, "
            "the message is not sent again. Use a value that is unique per message, such as an order ID, and "
            "reuse it when you repeat that send."
        ),
    )


class TurboNotifyComponent(Component):
    """Base class: builds the client from the shared inputs."""

    icon = "TurboNotify"

    def client(self) -> TurboNotifyClient:
        """Return a client for the configured key, number and base URL."""
        return TurboNotifyClient(
            api_key=self.api_key,
            base_url=getattr(self, "base_url", None),
            number_alias=getattr(self, "number_alias", None),
        )
