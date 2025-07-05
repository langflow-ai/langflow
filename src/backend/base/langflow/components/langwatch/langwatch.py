import json
import os
from functools import lru_cache
from typing import Any

import httpx
from loguru import logger

from langflow.custom.custom_component.component import Component
from langflow.inputs.inputs import MultilineInput
from langflow.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MessageTextInput,
    NestedDictInput,
    Output,
    SecretStrInput,
)
from langflow.schema.data import Data
from langflow.schema.dotdict import dotdict


class LangWatchComponent(Component):
    display_name: str = "LangWatch Evaluator"
    description: str = "Evaluates various aspects of language models using LangWatch's evaluation endpoints."
    documentation: str = "https://docs.langwatch.ai/langevals/documentation/introduction"
    icon: str = "Langwatch"
    name: str = "LangWatchEvaluator"

    inputs = [
        DropdownInput(
            name="evaluator_name",
            display_name="Evaluator Name",
            options=[],
            required=True,
            info="Select an evaluator.",
            refresh_button=True,
            real_time_refresh=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            required=True,
            info="Enter your LangWatch API key.",
        ),
        MessageTextInput(
            name="input",
            display_name="Input",
            required=False,
            info="The input text for evaluation.",
        ),
        MessageTextInput(
            name="output",
            display_name="Output",
            required=False,
            info="The output text for evaluation.",
        ),
        MessageTextInput(
            name="expected_output",
            display_name="Expected Output",
            required=False,
            info="The expected output for evaluation.",
        ),
        MessageTextInput(
            name="contexts",
            display_name="Contexts",
            required=False,
            info="The contexts for evaluation (comma-separated).",
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The maximum time (in seconds) allowed for the server to respond before timing out.",
            value=30,
            advanced=True,
        ),
    ]

    outputs = [
        Output(name="evaluation_result", display_name="Evaluation Result", method="evaluate"),
    ]

    @lru_cache(maxsize=1)
    def get_evaluators(self, endpoint: str = "https://app.langwatch.ai") -> dict[str, Any]:
        url = f"{endpoint}/api/evaluations/list"
        try:
            response = httpx.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("evaluators", {})
        except httpx.RequestError as e:
            self.status = f"Error fetching evaluators: {e}"
            return {}

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: str | None = None) -> dotdict:
        try:
            logger.info(f"Updating build config. Field name: {field_name}, Field value: {field_value}")

            if field_name is None or field_name == "evaluator_name":
                self.evaluators = self.get_evaluators(os.getenv("LANGWATCH_ENDPOINT", "https://app.langwatch.ai"))
                build_config["evaluator_name"]["options"] = list(self.evaluators.keys())

                # Set a default evaluator if none is selected
                if not self.current_evaluator and self.evaluators:
                    self.current_evaluator = next(iter(self.evaluators))
                    build_config["evaluator_name"]["value"] = self.current_evaluator

                # Define default keys that should always be present
                default_keys = ["code", "_type", "evaluator_name", "api_key", "input", "output", "timeout"]

                if field_value and field_value in self.evaluators and self.current_evaluator != field_value:
                    self.current_evaluator = field_value
                    evaluator = self.evaluators[field_value]

                    # Clear previous dynamic inputs
                    keys_to_remove = [key for key in build_config if key not in default_keys]
                    for key in keys_to_remove:
                        del build_config[key]

                    # Clear component's dynamic attributes
                    for attr in list(self.__dict__.keys()):
                        if attr not in default_keys and attr not in {
                            "evaluators",
                            "dynamic_inputs",
                            "_code",
                            "current_evaluator",
                        }:
                            delattr(self, attr)

                    # Add new dynamic inputs
                    self.dynamic_inputs = self.get_dynamic_inputs(evaluator)
                    for name, input_config in self.dynamic_inputs.items():
                        build_config[name] = input_config.to_dict()

                    # Update required fields
                    required_fields = {"api_key", "evaluator_name"}.union(evaluator.get("requiredFields", []))
                    for key in build_config:
                        if isinstance(build_config[key], dict):
                            build_config[key]["required"] = key in required_fields

                # Validate presence of default keys
                missing_keys = [key for key in default_keys if key not in build_config]
                if missing_keys:
                    logger.warning(f"Missing required keys in build_config: {missing_keys}")
                    # Add missing keys with default values
                    for key in missing_keys:
                        build_config[key] = {"value": None, "type": "str"}

            # Ensure the current_evaluator is always set in the build_config
            build_config["evaluator_name"]["value"] = self.current_evaluator

            logger.info(f"Current evaluator set to: {self.current_evaluator}")
            return build_config

        except (KeyError, AttributeError, ValueError) as e:
            self.status = f"Error updating component: {e!s}"
            return build_config
        else:
            return build_config

    def get_dynamic_inputs(self, evaluator: dict[str, Any]):
        try:
            dynamic_inputs = {}

            input_fields = [
                field
                for field in evaluator.get("requiredFields", []) + evaluator.get("optionalFields", [])
                if field not in {"input", "output"}
            ]

            for field in input_fields:
                input_params = {
                    "name": field,
                    "display_name": field.replace("_", " ").title(),
                    "required": field in evaluator.get("requiredFields", []),
                }
                if field == "contexts":
                    dynamic_inputs[field] = MultilineInput(**input_params, multiline=True)
                else:
                    dynamic_inputs[field] = MessageTextInput(**input_params)

            settings = evaluator.get("settings", {})
            for setting_name, setting_config in settings.items():
                schema = evaluator.get("settings_json_schema", {}).get("properties", {}).get(setting_name, {})

                input_params = {
                    "name": setting_name,
                    "display_name": setting_name.replace("_", " ").title(),
                    "info": setting_config.get("description", ""),
                    "required": False,
                }

                if schema.get("type") == "object":
                    input_type = NestedDictInput
                    input_params["value"] = schema.get("default", setting_config.get("default", {}))
                elif schema.get("type") == "boolean":
                    input_type = BoolInput
                    input_params["value"] = schema.get("default", setting_config.get("default", False))
                elif schema.get("type") == "number":
                    is_float = isinstance(schema.get("default", setting_config.get("default")), float)
                    input_type = FloatInput if is_float else IntInput
                    input_params["value"] = schema.get("default", setting_config.get("default", 0))
                elif "enum" in schema:
                    input_type = DropdownInput
                    input_params["options"] = schema["enum"]
                    input_params["value"] = schema.get("default", setting_config.get("default"))
                else:
                    input_type = MessageTextInput
                    default_value = schema.get("default", setting_config.get("default"))
                    input_params["value"] = str(default_value) if default_value is not None else ""

                dynamic_inputs[setting_name] = input_type(**input_params)

        except (KeyError, AttributeError, ValueError, TypeError) as e:
            self.status = f"Error creating dynamic inputs: {e!s}"
            return {}
        return dynamic_inputs

    async def evaluate(self) -> Data:
        if not self.api_key:
            return Data(data={"error": "API key is required"})

        self.evaluators = self.get_evaluators(os.getenv("LANGWATCH_ENDPOINT", "https://app.langwatch.ai"))
        self.dynamic_inputs = {}
        if getattr(self, "current_evaluator", None) is None and self.evaluators:
            self.current_evaluator = next(iter(self.evaluators))

        # Prioritize evaluator_name if it exists
        evaluator_name = getattr(self, "evaluator_name", None) or self.current_evaluator

        if not evaluator_name:
            if self.evaluators:
                evaluator_name = next(iter(self.evaluators))
                logger.info(f"No evaluator was selected. Using default: {evaluator_name}")
            else:
                return Data(
                    data={"error": "No evaluator selected and no evaluators available. Please choose an evaluator."}
                )

        try:
            evaluator = self.evaluators.get(evaluator_name)
            if not evaluator:
                return Data(data={"error": f"Selected evaluator '{evaluator_name}' not found."})

            logger.info(f"Evaluating with evaluator: {evaluator_name}")

            endpoint = f"/api/evaluations/{evaluator_name}/evaluate"
            url = f"{os.getenv('LANGWATCH_ENDPOINT', 'https://app.langwatch.ai')}{endpoint}"

            headers = {"Content-Type": "application/json", "X-Auth-Token": self.api_key}

            payload = {
                "data": {
                    "input": self.input,
                    "output": self.output,
                    "expected_output": self.expected_output,
                    "contexts": self.contexts.split(",") if self.contexts else [],
                },
                "settings": {},
            }

            if self._tracing_service:
                tracer = self._tracing_service.get_tracer("langwatch")
                if tracer is not None and hasattr(tracer, "trace_id"):
                    payload["settings"]["trace_id"] = str(tracer.trace_id)

            for setting_name in self.dynamic_inputs:
                payload["settings"][setting_name] = getattr(self, setting_name, None)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)

            response.raise_for_status()
            result = response.json()

            formatted_result = json.dumps(result, indent=2)
            self.status = f"Evaluation completed successfully. Result:\n{formatted_result}"
            return Data(data=result)

        except (httpx.RequestError, KeyError, AttributeError, ValueError) as e:
            error_message = f"Evaluation error: {e!s}"
            self.status = error_message
            return Data(data={"error": error_message})
