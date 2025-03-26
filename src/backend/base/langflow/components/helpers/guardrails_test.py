import logging
import uuid
from typing import Any
from urllib.parse import urljoin

import requests
from typing_extensions import override

from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema import dotdict
from langflow.schema.message import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GuardrailsTestComponent(Component):
    display_name = "Guardrails Test"
    description = "A test component for guardrails functionality."
    beta = True

    inputs = [
        MessageTextInput(
            name="input", 
            display_name="input",
            info="The input text to validate.",
            required=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="The base URL for the guardrails service.",
            required=True,
            value="http://localhost:8000",
        ),
        MessageTextInput(
            name="guard_name",
            display_name="Guard Name",
            info="The name of the guard to use for validation.",
            required=True,
        ),
        MessageTextInput(
            name="default_response",
            display_name="Default Response",
            info="The default response to return if validation fails.",
            value="I'm sorry, I can't answer that.",
            advanced=True,
        ),
    ]

    outputs = [
        # Output(display_name="output", name="output", method="validate_input"),
        Output(display_name="Success", name="success", method="on_success"),
        Output(display_name="Failure", name="failure", method="on_failure"),
    ]

    def on_success(self) -> Message:
        result, message = self.validate_input()
        if result:
            self.status = message
            self.stop("failure")
            return message
        self.stop("success")
        return Message(content="")

    def on_failure(self) -> Message:
        result, message = self.validate_input()
        if not result:
            self.status = message
            self.stop("success")
            return message
        self.stop("failure")
        return Message(content="")


    def validate_input(self) -> tuple[bool, Message]:
        input_text = self.input
        base_url = self.base_url
        guard_name = self.guard_name

        logger.info("Starting guardrails validation for input: %s, guard_name: %s", input_text, guard_name)

        endpoint = f"/guards/{guard_name}/validate"
        url = urljoin(base_url, endpoint)
        logger.debug("Constructed URL: {}", url)

        try:
            response = requests.post(
                url,
                json={"llmOutput": input_text}
            )

            if response.status_code == 400:
                logger.info("Validation failed with error: %s", response.text)
                return False, Message(text=self.default_response)

            response.raise_for_status()
            result = response.json()
            logger.debug("Guardrails response: %s", result)

            validatedOutput = result.get("validatedOutput")
            if not validatedOutput:
                # Not all validators support all on_fail behaviors. An empty response is
                # sometimes the result of an unsupported on_fail behavior.
                error_msg = "Validation successful but received an empty response."
                raise ValueError(error_msg)

            logger.info("Validation successful, received response: %s", validatedOutput)
            return True, Message(text=validatedOutput)

        except requests.RequestException as e:
            error_msg = f"Request failed with unexpected error: {str(e)}"
            raise ValueError(error_msg)