import json
import logging

import httpx

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import (
    BoolInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MultiselectInput,
    Output,
    SecretStrInput,
    SliderInput,
    StrInput,
)

logger = logging.getLogger(__name__)


class NVIDIANeMoEvaluatorComponent(Component):
    display_name = "NVIDIA NeMo Evaluator"
    description = "Evaluate models with flexible evaluation configurations."
    icon = "NVIDIA"
    name = "NVIDIANeMoEvaluator"
    beta = True

    # Endpoint configuration
    endpoint = "localhost:11000"
    model_endpoint = "localhost:10000"
    url = f"http://{endpoint}/v1/evaluations"
    model_url = f"http://{model_endpoint}/v1/models"
    inference_url = "http://nemo-nim.default.svc.cluster.local:8000/v1"

    headers = {"accept": "application/json", "Content-Type": "application/json"}

    # Define initial static inputs
    inputs = [
        DropdownInput(
            name="000_llm_name",
            display_name="LLM Name",
            info="Select the model for evaluation",
            options=[],  # Dynamically populated
            refresh_button=True,
        ),
        StrInput(
            name="001_tag",
            display_name="Tag",
            info="Any user-provided value. Generated results will be stored in the NeMo Data Store under this name.",
        ),
        DropdownInput(
            name="002_evaluation_type",
            display_name="Evaluation Type",
            info="Select the type of evaluation",
            options=["LM Evaluation Harness", "BigCode Evaluation Harness", "Custom Evaluation", "LLM-as-a-Judge"],
            value="LM Evaluation Harness",
            real_time_refresh=True,  # Ensure dropdown triggers update on change
        ),
    ]

    outputs = [
        Output(display_name="Job Result", name="job_result", method="evaluate"),
    ]

    # Inputs for LM Evaluation
    lm_evaluation_inputs = [
        SecretStrInput(
            name="100_huggingface_token",
            display_name="HuggingFace Token",
            info="Token for accessing HuggingFace models if required.",
        ),
        StrInput(
            name="110_task_name",
            display_name="Task Name",
            info="Task from https://github.com/EleutherAI/lm-evaluation-harness/tree/v0.4.3/lm_eval/tasks#tasks",
        ),
        IntInput(
            name="112_few_shot_examples",
            display_name="Few-shot Examples",
            info="The number of few-shot examples before the input.",
            advanced=True,
            value=5,
        ),
        IntInput(
            name="113_batch_size", display_name="Batch Size", info="The batch size used for evaluation.", value=16
        ),
        IntInput(
            name="114_bootstrap_iterations",
            display_name="Bootstrap Iterations",
            info="The number of iterations for bootstrap statistics.",
            advanced=True,
            value=100000,
        ),
        FloatInput(
            name="115_limit",
            display_name="Limit",
            info="Limits the number of documents to evaluate for debugging, or limits to X% of documents.",
            advanced=True,
            value=-1,
        ),
        BoolInput(
            name="150_greedy",
            display_name="Few-shot Examples",
            info="The number of few-shot examples before the input.",
            advanced=True,
            value=True,
        ),
        FloatInput(
            name="151_top_p",
            display_name="Top_p",
            info="Threshold to select from most probable tokens until cumulative probability exceeds this value",
            advanced=True,
            value=0.0,
        ),
        IntInput(
            name="152_top_k",
            display_name="Top_k",
            info="The top_k value to be used during generation sampling.",
            value=1,
        ),
        SliderInput(
            name="153_temperature",
            display_name="Temperature",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0).",
        ),
        IntInput(
            name="155_tokens_to_generate",
            display_name="Tokens to Generate",
            info="Max number of tokens to generate during inference.",
            value=1024,
        ),
    ]

    # Inputs for Custom Evaluation
    custom_evaluation_inputs = [
        StrInput(
            name="300_input_file",
            display_name="Input File",
            info="Path in NeMo Data Store as nds:<dataset>/<json input file>.",
            value="",
        ),
        IntInput(
            name="350_num_of_samples",
            display_name="Number of Samples",
            info="Number of samples to run inference on from the input_file.",
            value=-1,
        ),
        MultiselectInput(
            name="351_scorers",
            display_name="Scorers",
            info="List of Scorers for evaluation.",
            options=["accuracy", "bleu", "rouge", "em", "bert", "f1"],
            value=["accuracy", "bleu", "rouge", "em", "bert", "f1"],
        ),
        DropdownInput(
            name="310_run_inference",
            display_name="Run Inference",
            info="Select 'True' to run inference on the provided input_file or 'False' to use an output_file.",
            options=["True", "False"],
            value="True",
            real_time_refresh=True,
        ),
        # Conditional inputs for run_inference = True
        IntInput(
            name="311_tokens_to_generate",
            display_name="Tokens to Generate",
            info="Max number of tokens to generate during inference.",
            value=1024,
        ),
        SliderInput(
            name="312_temperature",
            display_name="Temperature",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0).",
        ),
        IntInput(name="313_top_k", display_name="Top_k", info="Top_k value for generation sampling.", value=1),
        # Conditional input for run_inference = False
        StrInput(
            name="320_output_file",
            display_name="Output File",
            info="Path of the output file in NeMo Data Store in nds:<dataset>/<json output file>.",
        ),
    ]

    def fetch_models(self):
        """Fetch models from the specified API endpoint and return a list of model names."""
        try:
            response = httpx.get(self.model_url, headers=self.headers)
            response.raise_for_status()
            models_data = response.json()
            return [model["id"] for model in models_data.get("data", [])]
        except httpx.RequestError as exc:
            self.log(f"An error occurred while requesting models: {exc}")
            return []
        except httpx.HTTPStatusError as exc:
            self.log(f"Error response {exc.response.status_code} while requesting models: {exc}")
            return []

    def clear_dynamic_inputs(self, build_config, saved_values):
        """Clears dynamically added fields by referring to a special marker in build_config."""
        dynamic_fields = build_config.get("_dynamic_fields", [])
        length_dynamic_fields = len(dynamic_fields)
        message = f"Clearing dynamic inputs. Number of fields to remove: {length_dynamic_fields}"
        logger.info(message)

        for field in dynamic_fields:
            if field in build_config:
                message = f"Removing dynamic field: {field}"
                logger.info(message)
                saved_values[field] = build_config[field].get("value", None)
                del build_config[field]

        build_config["_dynamic_fields"] = []

    def add_inputs_with_saved_values(self, build_config, input_definitions, saved_values):
        """Adds inputs to build_config and restores any saved values."""
        for input_def in input_definitions:
            # Check if input_def is already a dict or needs conversion
            input_dict = input_def if isinstance(input_def, dict) else input_def.to_dict()
            input_name = input_dict["name"]
            input_dict["value"] = saved_values.get(input_name, input_dict.get("value"))
            build_config[input_name] = input_dict
            build_config.setdefault("_dynamic_fields", []).append(input_name)

    def add_evaluation_inputs(self, build_config, saved_values, evaluation_type):
        """Adds inputs based on the evaluation type (LM Evaluation or Custom Evaluation)."""
        if evaluation_type == "LM Evaluation Harness":
            self.add_inputs_with_saved_values(build_config, self.lm_evaluation_inputs, saved_values)
        elif evaluation_type == "Custom Evaluation":
            self.add_inputs_with_saved_values(build_config, self.custom_evaluation_inputs, saved_values)

    def update_build_config(self, build_config, field_value, field_name=None):
        """Updates the component's configuration based on the selected option."""
        try:
            message = f"Updating build config: field_name={field_name}, field_value={field_value}"
            logger.info(message)

            saved_values = {}

            if field_name == "000_llm_name":
                # Refresh model options for LLM Name dropdown
                build_config["000_llm_name"]["options"] = self.fetch_models()

            elif field_name == "002_evaluation_type":
                self.clear_dynamic_inputs(build_config, saved_values)
                self.add_evaluation_inputs(build_config, saved_values, field_value)

            elif field_name == "310_run_inference":
                run_inference = field_value == "True"
                self.clear_dynamic_inputs(build_config, saved_values)
                # Run Inference Toggle
                self.add_inputs_with_saved_values(build_config, [self.custom_evaluation_inputs[3]], saved_values)
                if run_inference:
                    # Inference params
                    self.add_inputs_with_saved_values(build_config, self.custom_evaluation_inputs[4:7], saved_values)
                else:
                    # Output file
                    self.add_inputs_with_saved_values(build_config, [self.custom_evaluation_inputs[7]], saved_values)

            logger.info("Build config update completed successfully.")
        except (httpx.RequestError, ValueError) as exc:
            error_msg = f"Unexpected error on URL {self.url}"
            logger.exception(error_msg)
            raise ValueError(error_msg) from exc
        return build_config

    async def evaluate(self) -> dict:
        evaluation_type = getattr(self, "002_evaluation_type", "LM Evaluation Harness")

        # Generate the request data based on evaluation type
        if evaluation_type == "LM Evaluation Harness":
            data = self._generate_lm_evaluation_body()
        elif evaluation_type == "Custom Evaluation":
            data = self._generate_custom_evaluation_body()
        else:
            error_message = f"Unsupported evaluation type: {evaluation_type}"
            raise ValueError(error_message)

        # Send the request and log the output
        try:
            # Format the data as a JSON string for logging
            formatted_data = json.dumps(data, indent=2)
            self.log(
                f"Sending evaluation request to NeMo API with data: {formatted_data}", name="NeMoEvaluatorComponent"
            )

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.url, headers=self.headers, json=data)
                response.raise_for_status()
                result = response.json()

                # Log the successful response
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful evaluation response: {formatted_result}", name="NeMoEvaluatorComponent")
                return result
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on URL {self.url}."
            self.log(error_msg)
            raise ValueError(error_msg) from exc
        except Exception as exc:
            error_msg = f"Unexpected error on URL {self.url}"
            logger.exception(error_msg)
            raise ValueError(error_msg) from exc

    def _generate_lm_evaluation_body(self) -> dict:
        hf_token = getattr(self, "100_huggingface_token", None)
        return {
            "model": {
                "llm_name": getattr(self, "000_llm_name", ""),
                "inference_url": self.inference_url,
            },
            "evaluations": [
                {
                    "eval_type": "automatic",
                    "eval_subtype": "lm_eval_harness",
                    "hf_token": hf_token or None,  # Pass null if token is empty
                    "native_args": None,  # not exposing this for now, would be 101_native_args
                    "tasks": [
                        {
                            "task_name": getattr(self, "110_task_name", ""),
                            "task_config": None,  # not exposing this for now, would be 111_task_config
                            "num_fewshot": getattr(self, "112_few_shot_examples", 5),
                            "batch_size": getattr(self, "113_batch_size", 16),
                            "bootstrap_iters": getattr(self, "114_bootstrap_iterations", 100000),
                            "limit": getattr(self, "115_limit", -1),
                        }
                    ],
                    "inference_params": {
                        "use_greedy": getattr(self, "150_greedy", True),
                        "top_p": getattr(self, "151_top_p", 0.0),
                        "top_k": getattr(self, "152_top_k", 1),
                        "temperature": getattr(self, "153_temperature", 0.0),
                        "stop": [],  # not exposing this for now, would be 154_stop
                        "tokens_to_generate": getattr(self, "155_tokens_to_generate", 1024),
                    },
                }
            ],
            "tag": getattr(self, "001_tag", ""),
        }

    def _generate_custom_evaluation_body(self) -> dict:
        inference_params = (
            {
                "tokens_to_generate": getattr(self, "311_tokens_to_generate", 1024),
                "temperature": getattr(self, "312_temperature", 0.0),
                "top_k": getattr(self, "313_top_k", 1),
            }
            if getattr(self, "310_run_inference", True)
            else None
        )

        return {
            "model": {
                "llm_name": getattr(self, "000_llm_name", ""),
                "inference_url": self.inference_url,
            },
            "evaluations": [
                {
                    "eval_type": "automatic",
                    "eval_subtype": "custom_eval",
                    "input_file": getattr(self, "300_input_file", ""),
                    "num_of_samples": getattr(self, "350_num_of_samples", -1),
                    "scorers": getattr(self, "351_scorers", ["accuracy", "bleu", "rouge", "em", "bert", "f1"]),
                    "inference_configs": [
                        {
                            "model": {
                                "llm_name": getattr(self, "000_llm_name", ""),
                            },
                            "run_inference": getattr(self, "310_run_inference", True),
                            "inference_params": inference_params,
                            "output_file": getattr(self, "320_output_file", "")
                            if not getattr(self, "310_run_inference", True)
                            else None,
                        }
                    ],
                }
            ],
            "tag": getattr(self, "001_tag", ""),
        }
