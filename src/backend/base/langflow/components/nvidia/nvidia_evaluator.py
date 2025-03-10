import io
import json
import logging
import uuid
from datetime import datetime, timezone

import httpx
from huggingface_hub import HfApi

from langflow.custom import Component
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import (
    BoolInput,
    DataInput,
    DropdownInput,
    FloatInput,
    IntInput,
    MultiselectInput,
    Output,
    SecretStrInput,
    SliderInput,
    StrInput,
)
from langflow.schema import Data

logger = logging.getLogger(__name__)


class NvidiaEvaluatorComponent(Component):
    display_name = "NVIDIA Evaluator"
    description = "Evaluate models with flexible evaluation configurations."
    icon = "NVIDIA"
    name = "NVIDIANeMoEvaluator"
    beta = True

    # This assumes that the inference URL is a Kubernetes service in the same namespace as the evaluator
    inference_url = "http://nemo-nim.model-training.svc.cluster.local:8000/v1"

    headers = {"accept": "application/json", "Content-Type": "application/json"}

    # Define initial static inputs
    inputs = [
        StrInput(
            name="evaluator_base_url",
            display_name="Evaluator Base URL",
            info="The base URL of the NVIDIA NeMo Evaluator API.",
            advanced=True,
        ),
        StrInput(
            name="entity_service_base_url",
            display_name="Entity service URL",
            info="The base URL of the NVIDIA Entity service to obtain models that can be evaluated.",
            advanced=True,
        ),
        StrInput(
            name="nemo_model_base_url",
            display_name="Base model inference URL",
            info="The base URL of the NVIDIA NIM to run evaluation inference.",
            advanced=True,
        ),
        StrInput(
            name="datastore_base_url",
            display_name="Datastore Base URL",
            info="The nemo datastore base URL of the NVIDIA NeMo Datastore API.",
            advanced=True,
        ),
        StrInput(
            name="tenant_id",
            display_name="Tenant ID",
            info="Tenant id for dataset creation, if not provided default value `tenant` is used.",
            advanced=True,
            value="tenant",
        ),
        DropdownInput(
            name="000_llm_name",
            display_name="Model to be evaluated",
            info="Select the model for evaluation",
            options=[],  # Dynamically populated
            refresh_button=True,
        ),
        StrInput(
            name="001_tag",
            display_name="Tag name",
            info="Any user-provided value. Generated results are stored in the NeMo Data Store with this name.",
            value="default",
            required=True,
        ),
        DropdownInput(
            name="002_evaluation_type",
            display_name="Evaluation Type",
            info="Select the type of evaluation",
            options=["LM Evaluation Harness", "Similarity Metrics"],
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
            info="Token for accessing HuggingFace to fet the evaluation dataset.",
        ),
        StrInput(
            name="110_task_name",
            display_name="Task Name",
            info="Task from https://github.com/EleutherAI/lm-evaluation-harness/tree/v0.4.3/lm_eval/tasks#tasks",
            value="gsm8k",
            required=True,
        ),
        IntInput(
            name="112_few_shot_examples",
            display_name="Few-shot Examples",
            info="The number of few-shot examples before the input.",
            advanced=True,
            value=5,
        ),
        IntInput(
            name="113_batch_size",
            display_name="Batch Size",
            info="The batch size used for evaluation.",
            value=16,
        ),
        IntInput(
            name="114_bootstrap_iterations",
            display_name="Bootstrap Iterations",
            info="The number of iterations for bootstrap statistics.",
            advanced=True,
            value=100000,
        ),
        IntInput(
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

    # Inputs for Similarity Metrics
    custom_evaluation_inputs = [
        IntInput(
            name="350_num_of_samples",
            display_name="Number of Samples",
            info="Number of samples to run inference on from the input_file.",
            value=-1,
            advanced=True,
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
            display_name="Run Inference for response",
            info="Select 'True' to run inference or 'False' to use an `response` field in the dataset.",
            options=["True", "False"],
            value="True",
            real_time_refresh=True,
            advanced=True,
        ),
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
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0).",
        ),
        IntInput(
            name="313_top_k",
            display_name="Top_k",
            info="Top_k value for generation sampling.",
            value=1,
            advanced=True,
        ),
        DataInput(
            name="evaluation_data",
            display_name="Evaluation Data",
            info="Dataset for evaluation, expecting 2 fields `prompt` and `ideal_response` in dataset",
            is_list=True,
        ),
    ]

    def fetch_models(self):
        """Fetch models from the specified API endpoint and return a list of model names."""
        namespace = self.tenant_id if self.tenant_id else "tenant"
        model_url = f"{self.entity_service_base_url}/v1/models"
        params = {
            "filter[namespace]": namespace,  # This ensures proper encoding
            "page_size": 100,
        }
        try:
            response = httpx.get(model_url, headers=self.headers, params=params)
            response.raise_for_status()
            models_data = response.json()
            return [model["name"] for model in models_data.get("data", [])]

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
        """Adds inputs based on the evaluation type (LM Evaluation or Similarity Metrics)."""
        if evaluation_type == "LM Evaluation Harness":
            self.add_inputs_with_saved_values(build_config, self.lm_evaluation_inputs, saved_values)
        elif evaluation_type == "Similarity Metrics":
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
                options = build_config["000_llm_name"]["options"]
                msg = f"Updated LLM Name options: {options}"
                logger.info(msg)

            elif field_name == "002_evaluation_type":
                self.clear_dynamic_inputs(build_config, saved_values)
                self.add_evaluation_inputs(build_config, saved_values, field_value)
            elif field_name == "310_run_inference":
                run_inference = field_value == "True"
                # Always include inputs 1, 2, 3, 7, and 8
                always_included_inputs = self.custom_evaluation_inputs[:3] + self.custom_evaluation_inputs[6:8]
                self.clear_dynamic_inputs(build_config, saved_values)
                self.add_inputs_with_saved_values(build_config, always_included_inputs, saved_values)
                # Conditionally add fields 4 to 6 if Run Inference is True
                if run_inference:
                    conditional_inputs = self.custom_evaluation_inputs[3:6]
                    self.add_inputs_with_saved_values(build_config, conditional_inputs, saved_values)
            logger.info("Build config update completed successfully.")
        except (httpx.RequestError, ValueError) as exc:
            error_msg = f"Unexpected error on URL {self.evaluator_base_url}"
            logger.exception(error_msg)
            raise ValueError(error_msg) from exc
        return build_config

    async def evaluate(self) -> dict:
        evaluation_type = getattr(self, "002_evaluation_type", "LM Evaluation Harness")

        if not self.tenant_id:
            error_msg = "Provide tenant id to process"
            raise ValueError(error_msg)

        model_name = getattr(self, "000_llm_name", "")
        if not model_name:
            error_msg = "Refresh and select the model name to be evaluated"
            raise ValueError(error_msg)

        if not (self.evaluator_base_url and self.entity_service_base_url and self.datastore_base_url):
            error_msg = "Provide evaluator, data store, entity store url to process"
            raise ValueError(error_msg)

        # Generate the request data based on evaluation type
        if evaluation_type == "LM Evaluation Harness":
            data = await self._generate_lm_evaluation_body()
        elif evaluation_type == "Similarity Metrics":
            data = await self._generate_custom_evaluation_body()
        else:
            error_msg = f"Unsupported evaluation type: {evaluation_type}"
            raise ValueError(error_msg)

        # Send the request and log the output
        evaluator_url = f"{self.evaluator_base_url}/v1/evaluation/jobs"
        try:
            # Format the data as a JSON string for logging
            formatted_data = json.dumps(data, indent=2)
            self.log(f"Sending evaluation request to NeMo API with data: {formatted_data}")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(evaluator_url, headers=self.headers, json=data)
                response.raise_for_status()
                result = response.json()

                # Log the successful response
                formatted_result = json.dumps(result, indent=2)
                msg = f"Received successful evaluation response: {formatted_result}"
                self.log(msg)
                return result
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on URL {evaluator_url}."
            self.log(error_msg, name="NeMoEvaluatorComponent")
            raise ValueError(error_msg) from exc
        except (httpx.RequestError, ValueError) as exc:
            error_str = str(exc)
            error_msg = f"Unexpected error on {error_str} : {evaluator_url} {msg}"
            self.log(error_msg, name="NeMoEvaluatorComponent")
            raise ValueError(error_msg) from exc
        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error : {exception_str} {msg}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

    async def _generate_lm_evaluation_body(self) -> dict:
        target_id = await self.create_eval_target(None)
        hf_token = getattr(self, "100_huggingface_token", None)
        if not hf_token:
            error_msg = "Provide hf token to process"
            raise ValueError(error_msg)
        namespace = self.tenant_id
        config_data = {
            "type": "lm_eval_harness",
            "namespace": namespace,
            "tasks": [
                {
                    "type": getattr(self, "110_task_name", ""),
                    "params": {
                        "num_fewshot": getattr(self, "112_few_shot_examples", 5),
                        "batch_size": getattr(self, "113_batch_size", 16),
                        "bootstrap_iters": getattr(self, "114_bootstrap_iterations", 100000),
                        "limit": getattr(self, "115_limit", -1),
                    },
                }
            ],
            "params": {
                "hf_token": hf_token or None,
                "use_greedy": getattr(self, "150_greedy", True),
                "top_p": getattr(self, "151_top_p", 0.0),
                "top_k": getattr(self, "152_top_k", 1),
                "temperature": getattr(self, "153_temperature", 0.0),
                "stop": [],  # not exposing this for now, would be 154_stop
                "tokens_to_generate": getattr(self, "155_tokens_to_generate", 1024),
            },
        }

        eval_config_url = f"{self.evaluator_base_url}/v1/evaluation/configs"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(eval_config_url, headers=self.headers, json=config_data)
                response.raise_for_status()

                result = response.json()  # ✅ Convert response to a dictionary

                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}")

                config_id = result.get("id")  # ✅ Extract "id" safely
                if not config_id:
                    err_msg = f"Missing 'id' in response: {result}"
                    raise ValueError(err_msg)  # Ensure "id" exists

                return {
                    "tags": [getattr(self, "001_tag", "")],
                    "namespace": namespace,
                    "target": f"{namespace}/{target_id}",
                    "config": f"{namespace}/{config_id}",
                }

        except httpx.TimeoutException as exc:
            error_msg = f"Request to {eval_config_url} timed out"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} Config: {config_data}, Response content: {response_content}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred on URL {eval_config_url}: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

    async def _generate_custom_evaluation_body(self) -> dict:
        # Process and upload the dataset if training_data is provided
        if self.evaluation_data is None:
            error_msg = "Evaluation data is empty, cannot evaluate the model"
            raise ValueError(error_msg)

        repo_id = await self.process_eval_dataset()
        input_file = f"nds:{repo_id}/input.json"
        # Handle run_inference as a boolean
        run_inference = getattr(self, "310_run_inference", "True").lower() == "true"

        if run_inference and not self.nemo_model_base_url:
            error_msg = "Provide the nim url for evaluation inference to be processed"
            raise ValueError(error_msg)

        namespace = self.tenant_id
        # Set output_file based on run_inference
        output_file = None
        if not run_inference:  # Only set output_file if run_inference is False
            output_file = f"nds:{repo_id}/output.json"
        self.log(f"input_file: {input_file}, output_file: {output_file}")

        target_id = await self.create_eval_target(output_file)
        scores = getattr(self, "351_scorers", ["accuracy", "bleu", "rouge", "em", "bert", "f1"])

        # Transform the list into the desired format
        metrics_to_eval = [{"name": score} for score in scores]
        config_data = {
            "type": "similarity_metrics",
            "namespace": namespace,
            "tasks": [
                {
                    "type": "default",
                    "metrics": metrics_to_eval,
                    "dataset": {"files_url": input_file},
                    "params": {
                        "tokens_to_generate": getattr(self, "311_tokens_to_generate", 1024),
                        "temperature": getattr(self, "312_temperature", 0.0),
                        "top_k": getattr(self, "313_top_k", 0.0),
                        "n_samples": getattr(self, "350_num_of_samples", -1),
                    },
                }
            ],
        }

        eval_config_url = f"{self.evaluator_base_url}/v1/evaluation/configs"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(eval_config_url, headers=self.headers, json=config_data)
                response.raise_for_status()

                result = response.json()
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}")

                config_id = result.get("id")
                return {
                    "namespace": namespace,
                    "target": f"{namespace}/{target_id}",
                    "config": f"{namespace}/{config_id}",
                    "tags": [getattr(self, "001_tag", "")],
                }

        except httpx.TimeoutException as exc:
            error_msg = f"Request to {eval_config_url} timed out"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} Response content: {response_content} Request: {config_data}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred on URL {eval_config_url}: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

    async def create_eval_target(self, output_file) -> str:
        eval_target_url = f"{self.evaluator_base_url}/v1/evaluation/targets"
        namespace = self.tenant_id if self.tenant_id else "tenant"
        try:
            if output_file:
                request_body = {
                    "type": "model",
                    "namespace": namespace,
                    "model": {"cached_outputs": {"files_url": output_file}},
                }
            else:
                request_body = {
                    "type": "model",
                    "namespace": namespace,
                    "model": {
                        "api_endpoint": {
                            "url": f"{self.nemo_model_base_url}/v1/completions",
                            "model_id": getattr(self, "000_llm_name", ""),
                        }
                    },
                }
            self.log(f"Sending eval target creation to {eval_target_url} with data: {request_body}")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(eval_target_url, headers=self.headers, json=request_body)
                response.raise_for_status()

                result = response.json()
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}")

                return result.get("id")

        except httpx.TimeoutException as exc:
            error_msg = f"Request to {eval_target_url} timed out"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} on URL: {eval_target_url}. Response content: {response_content}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred on URL {eval_target_url}: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

    async def process_eval_dataset(self) -> str:
        """Asynchronously processes and uploads the dataset to the API in chunks.

        Returns the upload status.
        """
        try:
            # Inputs
            dataset_name = str(uuid.uuid4())
            hf_api = HfApi(endpoint=f"{self.datastore_base_url}/v1/hf", token="")
            await self.create_namespace(self.tenant_id)
            repo_id =  f"{self.tenant_id}/{dataset_name}"
            repo_type = "dataset"
            hf_api.create_repo(repo_id, repo_type=repo_type, exist_ok=True)
            self.log(f"repo_id : {repo_id}")
            generate_output_file = getattr(self, "310_run_inference", None) == "False"

            # Initialize lists for the two JSON structures
            input_file_data = []
            output_file_data = []

            # Ensure DataFrame is iterable correctly
            for data_obj in self.evaluation_data or []:
                # Check if the object is an instance of Data
                if not isinstance(data_obj, Data):
                    self.log(f"Skipping non-Data object in training data, but got: {data_obj}")
                    continue

                # Extract and transform fields
                filtered_data = {
                    "prompt": getattr(data_obj, "prompt", None) or "",
                    "ideal_response": getattr(data_obj, "ideal_response", None) or "",
                    "category": getattr(data_obj, "category", "Generation") or "Generation",
                    "source": getattr(data_obj, "source", None) or "",
                    "response": getattr(data_obj, "response", None) or "",
                    "llm_name": getattr(data_obj, "llm_name", None) or "",
                }
                # Check if both fields are present
                if filtered_data["prompt"] is not None and filtered_data["ideal_response"] is not None:
                    # Create data for the first file
                    input_file_data.append(
                        {
                            "prompt": filtered_data["prompt"],
                            "ideal_response": filtered_data["ideal_response"],
                            "category": filtered_data["category"],
                            "source": filtered_data["source"],
                        }
                    )
                    if generate_output_file:
                        # Create data for the second file
                        output_file_data.append(
                            {
                                "input": {
                                    "prompt": filtered_data["prompt"],
                                    "ideal_response": filtered_data["ideal_response"],
                                    "category": filtered_data["category"],
                                    "source": filtered_data["source"],
                                },
                                "response": filtered_data["response"],
                                "llm_name": filtered_data["llm_name"],
                            }
                        )
            # Create in-memory JSON files
            input_file_buffer = io.BytesIO(json.dumps(input_file_data, indent=4).encode("utf-8"))
            input_file_name = "input.json"
            try:
                hf_api.upload_file(
                    path_or_fileobj=input_file_buffer,
                    path_in_repo=input_file_name,
                    repo_id=repo_id,
                    repo_type="dataset",
                    commit_message=f"Input file at time: {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                )
            finally:
                input_file_buffer.close()

            if generate_output_file:
                output_file_buffer = io.BytesIO(json.dumps(output_file_data, indent=4).encode("utf-8"))
                output_file_name = "input.json"
                try:
                    hf_api.upload_file(
                        path_or_fileobj=output_file_buffer,
                        path_in_repo=output_file_name,
                        repo_id=repo_id,
                        repo_type="dataset",
                        commit_message=f"Output file at time: {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
                    )
                finally:
                    input_file_buffer.close()

            logger.info("All data has been processed and uploaded successfully.")
        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error : {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        return repo_id

    async def create_namespace(self, tenant_id: str):
        """Checks and creates namespace in datastore.
        Args:
            tenant_id (str): The tenant ID.

        """
        namespace = tenant_id

        url = f"{self.datastore_base_url}/v1/datastore/namespaces"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/{namespace}")
                response.raise_for_status()
                self.log(f"returned data {response}")
                http_code_namespace_missing = 404
                if response.status_code == http_code_namespace_missing:
                    create_payload = {"namespace": namespace}
                    create_response = await client.post(url, json=create_payload)
                    create_response.raise_for_status()

        except httpx.HTTPStatusError as e:
            exception_str = str(e)
            error_msg = f"Error processing namespace: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from e
