from langflow.custom import Component
from langflow.io import DropdownInput, StrInput, IntInput, FloatInput, MultiselectInput, SecretStrInput, BoolInput, \
    SliderInput, Output
from langflow.field_typing.range_spec import RangeSpec
import json
import os


class NVIDIANeMoEvaluatorComponent(Component):
    display_name = "NVIDIA NeMo Evaluator"
    description = "Evaluate models with flexible evaluation configurations."
    icon = "NVIDIA"
    name = "NVIDIANeMoEvaluator"
    beta = True

    # Endpoint configuration
    endpoint = os.getenv("NVIDIA_EVALUATOR_BASE_URL", "http://35.223.81.140:11000")
    model_endpoint = os.getenv("NVIDIA_MODELS_BASE_URL", "http://35.223.81.140:10000")
    datastore_base_url = os.getenv("NVIDIA_DATA_STORE_BASE_URL", "http://35.223.81.140:8000")
    url = f"{endpoint}/v1/evaluations"
    model_url = f"{model_endpoint}/v1/models"
    inference_url = "http://nemo-nim.default.svc.cluster.local:8000/v1"

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    # Define initial static inputs
    inputs = [
        DropdownInput(
            name="000_llm_name",
            display_name="LLM Name",
            info="Select the model for evaluation",
            options=[],  # Dynamically populated
            refresh_button=True
        ),
        StrInput(
            name="001_tag",
            display_name="Tag",
            info="Any user-provided value. Generated results will be stored in the NeMo Data Store under this name."
        ),
        DropdownInput(
            name="002_evaluation_type",
            display_name="Evaluation Type",
            info="Select the type of evaluation",
            options=["LM Evaluation Harness", "BigCode Evaluation Harness", "Custom Evaluation", "LLM-as-a-Judge"],
            value="LM Evaluation Harness",
            real_time_refresh=True  # Ensure dropdown triggers update on change
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
            info="Task selected from https://github.com/EleutherAI/lm-evaluation-harness/tree/v0.4.3/lm_eval/tasks#tasks",
        ),
        IntInput(
            name="112_few_shot_examples",
            display_name="Few-shot Examples",
            info="The number of few-shot examples before the input.",
            advanced=True,
            value=5
        ),
        IntInput(
            name="113_batch_size",
            display_name="Batch Size",
            info="The batch size used for evaluation.",
            value=16
        ),
        IntInput(
            name="114_bootstrap_iterations",
            display_name="Bootstrap Iterations",
            info="The number of iterations for bootstrap statistics.",
            advanced=True,
            value=100000
        ),
        FloatInput(
            name="115_limit",
            display_name="Limit",
            info="Limits the number of documents to evaluate for debugging, or limits to X% of documents.",
            advanced=True,
            value=-1
        ),
        BoolInput(
            name="150_greedy",
            display_name="Few-shot Examples",
            info="The number of few-shot examples before the input.",
            advanced=True,
            value=True
        ),
        FloatInput(
            name="151_top_p",
            display_name="Top_p",
            info="Threshold to select from most probable tokens until cumulative probability exceeds this value",
            advanced=True,
            value=0.0
        ),
        IntInput(
            name="152_top_k",
            display_name="Top_k",
            info="The top_k value to be used during generation sampling.",
            value=1
        ),
        SliderInput(
            name="153_temperature",
            display_name="Temperature",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0)."
        ),
        IntInput(
            name="155_tokens_to_generate",
            display_name="Tokens to Generate",
            info="Max number of tokens to generate during inference.",
            value=1024
        ),
    ]

    # Inputs for Custom Evaluation
    custom_evaluation_inputs = [
        IntInput(
            name="350_num_of_samples",
            display_name="Number of Samples",
            info="Number of samples to run inference on from the input_file.",
            value=-1
        ),
        MultiselectInput(
            name="351_scorers",
            display_name="Scorers",
            info="List of Scorers for evaluation.",
            options=["accuracy", "bleu", "rouge", "em", "bert", "f1"],
            value=["accuracy", "bleu", "rouge", "em", "bert", "f1"]
        ),
        DropdownInput(
            name="310_run_inference",
            display_name="Run Inference",
            info="Select 'True' to run inference on the provided input_file or 'False' to use an output_file.",
            options=["True", "False"],
            value="True",
            real_time_refresh=True
        ),
        # Conditional inputs for run_inference = True
        IntInput(
            name="311_tokens_to_generate",
            display_name="Tokens to Generate",
            info="Max number of tokens to generate during inference.",
            value=1024
        ),
        SliderInput(
            name="312_temperature",
            display_name="Temperature",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0)."
        ),
        IntInput(
            name="313_top_k",
            display_name="Top_k",
            info="Top_k value for generation sampling.",
            value=1
        ),
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Enter the dataset ID or name used to train the model",
            value="testing",
        ), DataInput(
            name="evaluation_data",
            display_name="Training Data",
            is_list=True,
        ),
    ]

    # Inputs for Custom Evaluation
    llm_as_judge = [
        MultiselectInput(
            name="evaluation_stages",
            display_name="Evaluation Stages",
            info="List of Evaluation Stages for evaluation.",
            options=["generation", "judgement"],
            value=["generation", "judgement"]
        ),
        # Conditional inputs for run_inference = True
        IntInput(
            name="tokens_to_generate",
            display_name="Tokens to Generate",
            info="Max number of tokens to generate during inference.",
            value=1024
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0)."
        ),
        IntInput(
            name="top_k",
            display_name="Top_k",
            info="Top_k value for generation sampling.",
            value=1
        ),
        FloatInput(
            name="top_p",
            display_name="Top_p",
            info="Top_p value for generation sampling.",
            value=1.0
        ),
        # Conditional inputs for run_inference = True
        DropdownInput(
            name="judge_llm_name",
            display_name="LLM Name for judge",
            info="Select the model for evaluation judge",
            options=[],  # Dynamically populated
            refresh_button=True
        ),
        # Conditional inputs for run_inference = True
        IntInput(
            name="judge_tokens_to_generate",
            display_name="Judge Tokens to Generate",
            info="Max number of tokens to generate during inference for the judge.",
            value=1024
        ),
        SliderInput(
            name="judge_temperature",
            display_name="Temperature for Judge",
            range_spec=RangeSpec(min=0.0, max=1.0, step=0.01),
            min_label="Precise",
            max_label="Creative",
            value=0.1,
            info="The temperature to be used during generation sampling (0.0 to 2.0) for the judge."
        ),
        IntInput(
            name="judge_top_k",
            display_name="Top_k for Judge",
            info="Top_k value for generation sampling for the judge.",
            value=1
        ),
        FloatInput(
            name="judge_top_p",
            display_name="Top_p for Judge",
            info="Threshold to select from most probable tokens until cumulative probability exceeds this value",
            value=1.0
        ),
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Enter the dataset ID or name used to train the model",
            value="testing",
        ), DataInput(
            name="evaluation_data",
            display_name="Training Data",
            is_list=True,
        ),
    ]

    def fetch_models(self):
        """
        Fetch models from the specified API endpoint and return a list of model names.
        """
        try:
            response = httpx.get(self.model_url, headers=self.headers)
            response.raise_for_status()
            models_data = response.json()
            models = [model['id'] for model in models_data.get("data", [])]
            return models
        except httpx.RequestError as exc:
            self.log(f"An error occurred while requesting models: {exc}")
            return []
        except httpx.HTTPStatusError as exc:
            self.log(f"Error response {exc.response.status_code} while requesting models: {exc}")
            return []

    def clear_dynamic_inputs(self, build_config, saved_values):
        """
        Clears dynamically added fields by referring to a special marker in build_config.
        """
        dynamic_fields = build_config.get("_dynamic_fields", [])
        print(f"Clearing dynamic inputs. Number of fields to remove: {len(dynamic_fields)}")

        for field in dynamic_fields:
            if field in build_config:
                print(f"Removing dynamic field: {field}")
                saved_values[field] = build_config[field].get("value", None)
                del build_config[field]

        build_config["_dynamic_fields"] = []

    def add_inputs_with_saved_values(self, build_config, input_definitions, saved_values):
        """
        Adds inputs to build_config and restores any saved values.
        """
        for input_def in input_definitions:
            # Check if input_def is already a dict or needs conversion
            input_dict = input_def if isinstance(input_def, dict) else input_def.to_dict()
            input_name = input_dict["name"]
            input_dict["value"] = saved_values.get(input_name, input_dict.get("value"))
            build_config[input_name] = input_dict
            build_config.setdefault("_dynamic_fields", []).append(input_name)

    def add_evaluation_inputs(self, build_config, saved_values, evaluation_type):
        """
        Adds inputs based on the evaluation type (LM Evaluation or Custom Evaluation).
        """
        if evaluation_type == "LM Evaluation Harness":
            self.add_inputs_with_saved_values(build_config, self.lm_evaluation_inputs, saved_values)
        elif evaluation_type == "Custom Evaluation":
            self.add_inputs_with_saved_values(build_config, self.custom_evaluation_inputs, saved_values)
        elif evaluation_type == "LLM-as-a-Judge":
            self.add_inputs_with_saved_values(build_config, self.llm_as_judge, saved_values)

    def update_build_config(self, build_config, field_value, field_name=None):
        """
        Updates the component's configuration based on the selected option.
        """
        try:
            print(f"Updating build config: field_name={field_name}, field_value={field_value}")

            saved_values = {}

            if field_name == "000_llm_name":
                # Refresh model options for LLM Name dropdown
                build_config["000_llm_name"]["options"] = self.fetch_models()
                print("Updated LLM Name options:", build_config["000_llm_name"]["options"])

            elif field_name == "judge_llm_name":
                # Refresh model options for LLM Name dropdown
                build_config["judge_llm_name"]["options"] = self.fetch_models()
                print("Updated LLM Name options:", build_config["judge_llm_name"]["options"])

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
            print("Build config update completed successfully.")
        except Exception as e:
            print(f"Error occurred during build config update: {e}")

        return build_config

    async def evaluate(self) -> dict:
        evaluation_type = getattr(self, "002_evaluation_type", "LM Evaluation Harness")

        # Generate the request data based on evaluation type
        if evaluation_type == "LM Evaluation Harness":
            data = self._generate_lm_evaluation_body()
        elif evaluation_type == "Custom Evaluation":
            data = await self._generate_custom_evaluation_body()
        elif evaluation_type == "LLM-as-a-Judge":
            data = await self._generate_llm_as_judge_body()
        else:
            raise ValueError(f"Unsupported evaluation type: {evaluation_type}")
        self.log(f"data {data}")

        # Send the request and log the output
        try:
            # Format the data as a JSON string for logging
            formatted_data = json.dumps(data, indent=2)
            self.log(f"Sending evaluation request to NeMo API with data: {formatted_data}",
                     name="NeMoEvaluatorComponent")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.url, headers=self.headers, json=data)
                response.raise_for_status()
                result = response.json()

                # Log the successful response
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful evaluation response: {formatted_result}",
                         name="NeMoEvaluatorComponent")
                return result
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on URL {self.url}."
            self.log(error_msg, name="NeMoEvaluatorComponent")
            raise ValueError(error_msg)
        except Exception as exc:
            error_msg = f"Unexpected error on URL {self.url}: {str(exc)}"
            self.log(error_msg, name="NeMoEvaluatorComponent")
            raise ValueError(error_msg)

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

    async def _generate_custom_evaluation_body(self) -> dict:
        dataset_path = await self.process_and_upload_dataset()
        input_file = f"nds:{dataset_path}/input/input.json"
        # Handle run_inference as a boolean
        run_inference = getattr(self, "310_run_inference", "True").lower() == "true"
        self.log(f"run_inference: {run_inference}, type: {type(run_inference)}")

        # Set output_file based on run_inference
        output_file = ""
        if not run_inference:  # Only set output_file if run_inference is False
            output_file = f"nds:{dataset_path}/output/output.json"

        self.log(f"input_file: {input_file}, output_file: {output_file}")
        inference_params = {
            "tokens_to_generate": getattr(self, "311_tokens_to_generate", 1024),
            "temperature": getattr(self, "312_temperature", 0.0),
            "top_k": getattr(self, "313_top_k", 1),
        } if getattr(self, "310_run_inference", True) else None

        # Construct inference_configs dynamically to exclude output_file if empty
        inference_config = {
            "model": {
                "llm_name": getattr(self, "000_llm_name", ""),
            },
            "run_inference": run_inference,
            "inference_params": inference_params,
        }

        if output_file:  # Add output_file only if it's not an empty string
            inference_config = {
                "model": {
                    "llm_name": getattr(self, "000_llm_name", ""),
                },
                "run_inference": run_inference,
                "inference_params": inference_params,
                "output_file": output_file,
                "input_file": input_file,
            }

        return {
            "model": {
                "llm_name": getattr(self, "000_llm_name", ""),
                "inference_url": self.inference_url,
            },
            "evaluations": [
                {
                    "eval_type": "automatic",
                    "eval_subtype": "custom_eval",
                    "input_file": input_file,
                    "num_of_samples": getattr(self, "350_num_of_samples", -1),
                    "scorers": getattr(self, "351_scorers", ["accuracy", "bleu", "rouge", "em", "bert", "f1"]),
                    "inference_configs": [inference_config],
                }
            ],
            "tag": getattr(self, "001_tag", ""),
        }

    async def _generate_llm_as_judge_body(self) -> dict:
        dataset_path = await self.process_and_upload_dataset()
        input_file = f"nds:{dataset_path}/input/input.json"
        # Handle run_inference as a boolean
        self.log(f"input_file: {input_file}")
        inference_params = {
            "tokens_to_generate": getattr(self, "tokens_to_generate", 1024),
            "temperature": getattr(self, "temperature", 0.0),
            "top_k": getattr(self, "top_k", 1),
            "top_p": getattr(self, "top_p", 1),
        }
        judge_llm_name = getattr(self, "judge_llm_name", "")

        judge_model = {
            "llm_type": "nvidia-nemo-nim",
            "llm_name": judge_llm_name,
            "model_type": "llm",
            "inference_url": self.inference_url
        }

        judge_inference_params = {
            "tokens_to_generate": getattr(self, "judge_tokens_to_generate", 1024),
            "temperature": getattr(self, "judge_temperature", 0.0),
            "top_k": getattr(self, "judge_top_k", 1),
            "top_p": getattr(self, "judge_top_p", 1),
        }

        return {
            "model": {
                "llm_type": "nvidia-nemo-nim",
                "llm_name": getattr(self, "000_llm_name", ""),
                "inference_url": self.inference_url,
            },
            "evaluations": [
                {
                    "eval_type": "llm_as_a_judge",
                    "eval_subtype": "mtbench",
                    "bench_name": "mt_bench",
                    "mode": "single",
                    "evaluation_stages": getattr(self, "evaluation_stages", ["generation", "judgement"]),
                    "inference_params": inference_params,
                    "judge_model": judge_model,
                    "judge_inference_params": judge_inference_params,
                }
            ],
            "tag": getattr(self, "001_tag", ""),
        }

    def get_dataset_name(self, user_dataset_name=None):
        # Generate a default dataset name using the current date and time
        default_name = f"dataset-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        # Use the user-provided name if available, otherwise the default
        return user_dataset_name if user_dataset_name else default_name

    async def get_dataset_id(self, dataset_name: str) -> str:
        """Fetches the dataset ID by checking if a dataset with the constructed name exists.

        If the dataset does not exist, creates a new dataset and returns its ID.

        Args:
            dataset_name (str): Provided dataset name.

        Returns:
            str: The dataset ID if found or created, or None if an error occurs.
        """

        url = f"{self.datastore_base_url}/v1/datasets"
        page = 1

        try:
            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(f"{url}?page_size=10&page={page}")
                    no_more_pages = 422
                    if response.status_code == no_more_pages:
                        self.log(f"No more pages to fetch, page: {page}")
                        break
                    response.raise_for_status()
                    self.log(f"returned data {response}")
                    datasets = response.json().get("datasets", [])
                    for dataset in datasets:
                        if dataset.get("name") == dataset_name:
                            return dataset.get("id")
                    if not datasets:
                        break  # No more datasets to process

                    page += 1

                # If dataset not found, create it
                create_payload = {"name": dataset_name, "description": f"{dataset_name} for Nemo custom eval"}
                create_response = await client.post(url, json=create_payload)
                create_response.raise_for_status()
                created_dataset = create_response.json()
                return created_dataset.get("id")

        except httpx.HTTPStatusError as e:
            self.log(f"Error processing datasets: {e}")
            return None

    async def process_and_upload_dataset(self) -> str:
        """Asynchronously processes and uploads the dataset to the API in chunks.

        Returns the upload status.
        """
        try:
            # Inputs
            user_dataset_name = getattr(self, "dataset", None)
            dataset_name = self.get_dataset_name(user_dataset_name)
            dataset_id = await self.get_dataset_id(dataset_name)
            self.log(f"dataset_name : {dataset_name}")
            generate_output_file = getattr(self, "310_run_inference", None) == "False"
            if not dataset_id:
                err_msg = "dataset_name must be provided."
                raise ValueError(err_msg)

            # Endpoint configuration
            url = f"{self.datastore_base_url}/v1"
            # Initialize lists for the two JSON structures
            file1_data = []
            file2_data = []

            file_name_appender = user_dataset_name if user_dataset_name else "dataset"
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
                    "category": getattr(data_obj, "category", None) or "",
                    "source": getattr(data_obj, "source", None) or "",
                    "response": getattr(data_obj, "response", None) or "",
                    "llm_name": getattr(data_obj, "llm_name", None) or "",
                }
                self.log(f"filtered_data : {filtered_data}")
                # Check if both fields are present
                if filtered_data["prompt"] is not None and filtered_data["ideal_response"] is not None:
                    # Create data for the first file
                    file1_data.append({
                        "prompt": filtered_data["prompt"],
                        "ideal_response": filtered_data["ideal_response"],
                        "category": filtered_data["category"],
                        "source": filtered_data["source"],
                    })
                    if generate_output_file:
                        # Create data for the second file
                        file2_data.append({
                            "input": {
                                "prompt": filtered_data["prompt"],
                                "ideal_response": filtered_data["ideal_response"],
                                "category": filtered_data["category"],
                                "source": filtered_data["source"],
                            },
                            "response": filtered_data["response"],
                            "llm_name": filtered_data["llm_name"],
                        })
            # Create in-memory JSON files
            file1_buffer = io.StringIO(json.dumps(file1_data, indent=4))

            file_name1 = "input.json"

            filepath = f"input/{file_name1}"
            url = f"{self.datastore_base_url}/datasets/{dataset_id}/eval/{filepath}"

            files = {"file": (file_name1, file1_buffer.getvalue(), "application/json")}
            async with httpx.AsyncClient() as client:
                response = await client.post(url, files=files)

            status_ok = 200
            if response.status_code == status_ok:
                logger.info("Input file uploaded successfully!")
            else:
                logger.warning("Failed to upload input file. Status code: %s",  response.status_code)
                logger.warning(response.text)

            if generate_output_file:
                file_name2 = "output.json"
                file2_buffer = io.StringIO(json.dumps(file2_data, indent=4))
                # Create files for API upload
                files = {
                    "file": (file_name2, file2_buffer.getvalue(), "application/json"),
                }

                filepath = f"output/{file_name2}"
                url = f"{self.datastore_base_url}/datasets/{dataset_id}/eval/{filepath}"

                async with httpx.AsyncClient() as client:
                    response = await client.post(url, files=files)

                status_ok = 200
                if response.status_code == status_ok:
                    logger.info("Output file uploaded successfully!")
                else:
                    logger.warning("Failed to upload output file. Status code: %s",  response.status_code)
                    logger.warning(response.text)

            logger.info("All data has been processed and uploaded successfully.")
        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred on URL : {exception_str}"
            self.log(error_msg)
            return "An error occurred"

        return f"{dataset_name}/eval"
