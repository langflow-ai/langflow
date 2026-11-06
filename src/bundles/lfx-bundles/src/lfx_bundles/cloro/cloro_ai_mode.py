"""Ask Google AI Mode a prompt through cloro and return the answer with its sources."""

from __future__ import annotations

from lfx.custom.custom_component.component import Component
from lfx.io import FloatInput, MessageTextInput, Output, SecretStrInput
from lfx.log.logger import logger
from lfx.schema.data import Data

from lfx_bundles.cloro.cloro_common import (
    ANSWER_TIMEOUT_SECONDS,
    API_KEY_INFO,
    COUNTRY_INFO,
    DEFAULT_COUNTRY,
    DOCUMENTATION_URL,
    CloroAPIError,
    fetch_answer,
)


class CloroAIModeComponent(Component):
    """Return the answer that Google AI Mode gives to a prompt, as seen by a user in the chosen country."""

    display_name = "cloro Google AI Mode"
    description = "Ask Google AI Mode a prompt through cloro. Returns the answer in markdown and the sources it cites."
    documentation = DOCUMENTATION_URL
    icon = "Cloro"
    name = "CloroAIMode"

    inputs = [
        SecretStrInput(
            name="api_key",
            display_name="cloro API Key",
            info=API_KEY_INFO,
            required=True,
        ),
        MessageTextInput(
            name="prompt",
            display_name="Prompt",
            info="The prompt to send to Google AI Mode.",
            required=True,
            tool_mode=True,
        ),
        MessageTextInput(
            name="country",
            display_name="Country",
            info=COUNTRY_INFO,
            value=DEFAULT_COUNTRY,
            advanced=True,
        ),
        FloatInput(
            name="timeout",
            display_name="Timeout (seconds)",
            info="How long to wait for cloro to answer. AI answers can take more than a minute.",
            value=ANSWER_TIMEOUT_SECONDS,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Answer", name="answer", method="get_answer"),
    ]

    def get_answer(self) -> Data:
        """Return the answer as one ``Data``: the text holds the answer and the sources."""
        try:
            answer = fetch_answer(
                "aimode",
                "/v1/monitor/aimode",
                prompt=self.prompt,
                country=self.country,
                api_key=self.api_key,
                timeout=float(self.timeout or ANSWER_TIMEOUT_SECONDS),
            )
        except CloroAPIError as exc:
            logger.error(str(exc))
            self.status = str(exc)
            return Data(text=str(exc), data={"error": str(exc)})
        self.status = answer
        return answer
