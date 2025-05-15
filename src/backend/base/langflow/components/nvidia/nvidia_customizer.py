import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from io import BytesIO

import httpx
import pandas as pd
from huggingface_hub import HfApi

from langflow.custom import Component
from langflow.io import (
    DataInput,
    DropdownInput,
    FloatInput,
    IntInput,
    Output,
    StrInput,
)
from langflow.schema import Data
from langflow.services.deps import get_settings_service

logger = logging.getLogger(__name__)


class NvidiaCustomizerComponent(Component):
    display_name = "NeMo Customizer"
    description = "LLM fine-tuning using NeMo customizer microservice"
    icon = "NVIDIA"
    name = "NVIDIANeMoCustomizer"
    beta = True

    headers = {"accept": "application/json", "Content-Type": "application/json"}
    chunk_number = 1

    inputs = [
        StrInput(
            name="namespace",
            display_name="Namespace",
            info="Namespace for the dataset and output model",
            advanced=True,
            value="default",
            required=True,
        ),
        StrInput(
            name="fine_tuned_model_name",
            display_name="Output Model Name",
            info="Enter the name to reference the output fine tuned model, ex: `imdb-data@v1`",
            required=True,
        ),
        DataInput(
            name="training_data",
            display_name="Training Data",
            is_list=True,
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Base Model Name",
            info="Base model to fine tune",
            refresh_button=True,
            required=True,
        ),
        DropdownInput(
            name="training_type",
            display_name="Training Type",
            info="Select the type of training to use",
            refresh_button=True,
            required=True,
        ),
        DropdownInput(
            name="fine_tuning_type",
            display_name="Fine Tuning Type",
            info="Select the fine tuning type to use",
            required=True,
        ),
        IntInput(
            name="epochs",
            display_name="Fine tuning cycles",
            info="Number of cycle to run through the training data.",
            value=5,
        ),
        IntInput(
            name="batch_size",
            display_name="Batch size",
            info="The number of samples used in each training iteration",
            value=16,
            advanced=True,
        ),
        FloatInput(
            name="learning_rate",
            display_name="Learning Rate",
            info="The number of samples used in each training iteration",
            value=0.0001,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Job Info", name="job_info", method="customize"),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Updates the component's configuration based on the selected option or refresh button."""
        settings_service = get_settings_service()
        nemo_customizer_url = settings_service.settings.nemo_customizer_url
        models_url = f"{nemo_customizer_url}/v1/customization/configs"
        try:
            if field_name == "model_name" and nemo_customizer_url != "":
                self.log(f"Refreshing model names from endpoint {models_url}, value: {field_value}")

                # Use a synchronous HTTP client
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(models_url, headers=self.headers)
                    response.raise_for_status()

                    models_data = response.json()
                    model_names = [model["base_model"] for model in models_data.get("data", [])]

                    build_config["model_name"]["options"] = model_names

                self.log("Updated model_name dropdown options.")

            elif field_name == "training_type" and nemo_customizer_url != "":
                # Use a synchronous HTTP client
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(models_url, headers=self.headers)
                    response.raise_for_status()

                    models_data = response.json()

                    # Logic to update `training_type` dropdown based on selected model
                    selected_model_name = getattr(self, "model_name", None)
                    if selected_model_name:
                        # Find the selected model in the response
                        selected_model = next(
                            (
                                model
                                for model in models_data.get("data", [])
                                if model["base_model"] == selected_model_name
                            ),
                            None,
                        )

                        if selected_model:
                            # Update `training_type` dropdown with training types of the selected model
                            training_types = selected_model.get("training_types", [])
                            build_config["training_type"]["options"] = training_types
                            self.log(f"Updated training_type dropdown options: {training_types}")
                            fine_tuning_type = selected_model.get("finetuning_types", [])
                            build_config["fine_tuning_type"]["options"] = fine_tuning_type
                            self.log(f"Updated fine_tuning_type dropdown options: {fine_tuning_type}")

        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on {models_url}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc
        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"Error refreshing model names: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        return build_config

    async def customize(self) -> dict:
        settings_service = get_settings_service()
        nemo_customizer_url = settings_service.settings.nemo_customizer_url
        nemo_data_store_url = settings_service.settings.nemo_data_store_url
        nemo_entity_store_url = settings_service.settings.nemo_entity_store_url

        fine_tuned_model_name = self.fine_tuned_model_name

        if not fine_tuned_model_name:
            error_msg = "Missing Output Model Name"
            raise ValueError(error_msg)

        namespace = self.namespace
        if not self.namespace:
            error_msg = "Missing Namespace"
            raise ValueError(error_msg)

        if not (nemo_customizer_url and nemo_data_store_url and nemo_entity_store_url):
            error_msg = "Missing NeMo service info, provide customizer or data store and entity store url"
            raise ValueError(error_msg)

        if not self.model_name:
            error_msg = "Missing Base Model Name"
            raise ValueError(error_msg)

        if not (self.training_type and self.fine_tuning_type):
            error_msg = "Refresh and select the training type and fine tuning type"
            raise ValueError(error_msg)

        # Process and upload the dataset if training_data is provided
        if self.training_data is None:
            error_msg = "Training data is empty, cannot customize the model"
            raise ValueError(error_msg)

        dataset_name = await self.process_dataset(nemo_data_store_url, nemo_entity_store_url)
        customizations_url = f"{nemo_customizer_url}/v1/customization/jobs"
        error_code_already_present = 409
        output_model = f"{namespace}/{fine_tuned_model_name}"

        description = f"Fine tuning base model {self.model_name} using dataset {dataset_name}"
        # Build the data payload
        data = {
            "config": self.model_name,
            "dataset": {"name": dataset_name, "namespace": namespace},
            "description": description,
            "hyperparameters": {
                "training_type": self.training_type,
                "finetuning_type": self.fine_tuning_type,
                "epochs": int(self.epochs),
                "batch_size": int(self.batch_size),
                "learning_rate": float(self.learning_rate),
            },
            "output_model": output_model,
        }

        # Add `adapter_dim` if fine tuning type is "lora"
        if self.fine_tuning_type == "lora":
            data["hyperparameters"]["lora"] = {"adapter_dim": 16}
        try:
            formatted_data = json.dumps(data, indent=2)
            self.log(f"Sending customization request with data: {formatted_data}")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(customizations_url, headers=self.headers, json=data)

            # For non-409 responses, raise for any HTTP error status
            response.raise_for_status()

            # Process a successful response
            result = response.json()
            formatted_result = json.dumps(result, indent=2)
            self.log(f"Received successful response: {formatted_result}")

            result_dict = {**result}
            id_value = result_dict["id"]
            result_dict["url"] = f"{customizations_url}/{id_value}/status"

        except httpx.TimeoutException as exc:
            error_msg = f"Request to {customizations_url} timed out"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except httpx.HTTPStatusError as exc:
            # Check if the error is due to a 409 Conflict

            if exc.response.status_code == error_code_already_present:
                self.log("Received HTTP 409. Conflict output model name. Retry with a different output model name")
                error_msg = (
                    f"There is already a fined tuned model with name {fine_tuned_model_name} "
                    f"Please choose a different Output Model Name."
                )
                raise ValueError(error_msg) from exc
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} on URL: {customizations_url}. Response content: {response_content}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except (httpx.RequestError, ValueError) as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred on URL {customizations_url}: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc
        else:
            return result_dict

    async def create_namespace(self, namespace: str, nemo_data_store_url: str):
        """Checks and creates namespace in datastore.

        Args:
            namespace (str): The namespace to be created.
            nemo_data_store_url (str): Data store api url to create namespace.
        """
        url = f"{nemo_data_store_url}/v1/datastore/namespaces"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/{namespace}")
                http_status_code_non_found = 404
                if response.status_code == http_status_code_non_found:
                    self.log(f"Namespace not found, creating namespace:  {namespace}")
                    create_payload = {"namespace": namespace}
                    create_response = await client.post(url, json=create_payload)
                    create_response.raise_for_status()
                else:
                    response.raise_for_status()

        except httpx.HTTPStatusError as e:
            exception_str = str(e)
            error_msg = f"Error processing namespace: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from e

    async def process_dataset(self, nemo_data_store_url: str, nemo_entity_store_url: str) -> str:
        """Asynchronously processes and uploads the dataset for training(90%) and validation(10%).

        If the total valid record count is less than 10, at least one record is added to validation.

        Args:
            nemo_data_store_url (str): Data store api url to create dataset.
            nemo_entity_store_url (str): Entity store api url to register dataset.
        """
        try:
            # Inputs and repo setup
            dataset_name = str(uuid.uuid4())

            hf_api = HfApi(endpoint=f"{nemo_data_store_url}/v1/hf", token="")
            await self.create_namespace(self.namespace, nemo_data_store_url)
            repo_id = f"{self.namespace}/{dataset_name}"
            repo_type = "dataset"
            hf_api.create_repo(repo_id, repo_type=repo_type, exist_ok=True)
        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred while creating repo: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        try:
            chunk_size = 100000  # Ensure chunk_size is an integer
            self.log(f"repo_id : {repo_id}")

            tasks = []

            # =====================================================
            # STEP 1: Build a list of valid records from training_data
            # =====================================================
            valid_records = []
            for data_obj in self.training_data or []:
                # Skip non-Data objects
                if not isinstance(data_obj, Data):
                    self.log(f"Skipping non-Data object in training data, but got: {data_obj}")
                    continue

                # Extract only "prompt" and "completion" fields if present
                filtered_data = {
                    "prompt": getattr(data_obj, "prompt", None),
                    "completion": getattr(data_obj, "completion", None),
                }
                if filtered_data["prompt"] is not None and filtered_data["completion"] is not None:
                    valid_records.append(filtered_data)

            total_records = len(valid_records)
            min_records_process = 2
            min_records_validation = 10
            if total_records < min_records_process:
                error_msg = f"Not enough records for processing. Record count : {total_records}"
                raise ValueError(error_msg)

            # =====================================================
            # STEP 2: Split into validation (10%) and training (90%)
            # =====================================================
            # If the total size is less than 10, force at least one record into validation.
            validation_count = 1 if total_records < min_records_validation else max(1, int(round(total_records * 0.1)))

            # For simplicity, we take the first validation_count records for validation.
            # (You could also randomize the order if needed.)
            validation_records = valid_records[:validation_count]
            training_records = valid_records[validation_count:]

            # =====================================================
            # STEP 3: Process training data in chunks (90%)
            # =====================================================
            chunk = []
            is_validation = False
            for record in training_records:
                chunk.append(record)
                if len(chunk) == chunk_size:
                    chunk_df = pd.DataFrame(chunk)
                    task = self.upload_chunk(
                        chunk_df,
                        self.chunk_number,
                        dataset_name,
                        repo_id,
                        hf_api,
                        is_validation,
                    )
                    tasks.append(task)
                    chunk = []  # Reset the chunk
                    self.chunk_number += 1

            # Process any remaining training records
            if chunk:
                chunk_df = pd.DataFrame(chunk)
                task = self.upload_chunk(
                    chunk_df,
                    self.chunk_number,
                    dataset_name,
                    repo_id,
                    hf_api,
                    is_validation,
                )
                tasks.append(task)

            # Await all training upload tasks
            await asyncio.gather(*tasks)

            # =====================================================
            # STEP 4: Upload validation data (without chunking)
            # =====================================================
            if validation_records:
                is_validation = True
                validation_df = pd.DataFrame(validation_records)
                await self.upload_chunk(validation_df, 1, dataset_name, repo_id, hf_api, is_validation)

        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred during processing/upload: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        # =====================================================
        # STEP 5: Post dataset info to the entity registry
        # =====================================================
        try:
            file_url = f"hf://datasets/{repo_id}"
            description = f"Dataset loaded using the input data {dataset_name}"
            entity_registry_url = f"{nemo_entity_store_url}/v1/datasets"
            create_payload = {
                "name": dataset_name,
                "namespace": self.namespace,
                "description": description,
                "files_url": file_url,
                "format": "jsonl",
                "project": dataset_name,
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(entity_registry_url, json=create_payload)

            success_status_code = 200
            if response.status_code == success_status_code:
                logger.info("Dataset uploaded successfully in %s chunks", self.chunk_number)
            else:
                logger.warning("Failed to upload files. Status code: %s", response.status_code)
                response.raise_for_status()

            logger.info("All data has been processed and uploaded successfully.")
        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error occurred while posting to entity service: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        return dataset_name

    async def upload_chunk(self, chunk_df, chunk_number, file_name_prefix, repo_id, hf_api, is_validation):
        """Asynchronously uploads a chunk of data to the REST API."""
        try:
            json_data = chunk_df.to_json(orient="records", lines=True)

            # Build file paths
            if is_validation:
                file_name_training = f"validation/{file_name_prefix}_validation.jsonl"
            else:
                file_name_training = f"training/{file_name_prefix}_chunk_{chunk_number}.jsonl"

            # Prepare BytesIO objects
            training_file_obj = BytesIO(json_data.encode("utf-8"))
            commit_message = f"Updated training file at time: {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            try:
                hf_api.upload_file(
                    path_or_fileobj=training_file_obj,
                    path_in_repo=file_name_training,
                    repo_id=repo_id,
                    repo_type="dataset",
                    commit_message=commit_message,
                )
            finally:
                training_file_obj.close()

        except Exception:
            logger.exception("An error occurred while uploading chunk %s", chunk_number)
