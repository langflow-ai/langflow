import asyncio
import json
import logging
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
    MessageTextInput,
    Output,
    StrInput,
)
from langflow.schema import Data

from scripts.factory_restart_space import hf_api

logger = logging.getLogger(__name__)


class NVIDIANeMoCustomizerComponent(Component):
    display_name = "Customizer"
    description = "Train models"
    icon = "NVIDIA"
    name = "NVIDIANeMoCustomizer"
    beta = True

    headers = {"accept": "application/json", "Content-Type": "application/json"}
    chunk_number = 1
    hf_api = HfApi(endpoint=f"{self.datastore_base_url}/v1/hf", token="")

    inputs = [
        StrInput(
            name="base_url",
            display_name="NVIDIA NeMo Customizer Base URL",
            info="The base URL of the NVIDIA NeMo Customizer API.",
        ),
        StrInput(
            name="datastore_base_url",
            display_name="NVIDIA NeMo Datastore Base URL",
            info="The nemo datastore base URL of the NVIDIA NeMo Datastore API.",
            advanced=True,
        ),
        StrInput(
            name="entity_store_base_url",
            display_name="NVIDIA NeMo EntityStore Base URL",
            info="The nemo datastore base URL of the NVIDIA NeMo EntityStore API.",
            advanced=True,
        ),
        StrInput(
            name="tenant_id",
            display_name="Tenant ID",
            info="Tenant id for dataset creation, if not provided default value `tenant` is used.",
            advanced=True,
            value="tenant",
        ),
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Enter the dataset ID or name used to train the model",
            value="dataset-RWZGSkCGdeP35SDAxqTtvy",
        ),
        DataInput(
            name="training_data",
            display_name="Training Data",
            is_list=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="Model to train",
            refresh_button=True,
        ),
        DropdownInput(
            name="training_type",
            display_name="Training Type",
            info="Select the training type to use for fine tuning",
        ),
        DropdownInput(
            name="fine_tuning_type",
            display_name="Fine tuning Type",
            info="Select the fine tuning type to use",
        ),
        IntInput(
            name="epochs", display_name="Epochs", info="Number of times to cycle through the training data", value=5
        ),
        IntInput(
            name="batch_size",
            display_name="Batch size",
            info="The number of samples used in each training iteration",
            value=16,
        ),
        FloatInput(
            name="learning_rate",
            display_name="Learning rate",
            info="The number of samples used in each training iteration",
            value=0.0001,
        ),
    ]

    outputs = [
        Output(display_name="Job Result", name="data", method="customize"),
    ]

    def update_build_config(self, build_config, field_value, field_name=None):
        """Updates the component's configuration based on the selected option or refresh button."""
        models_url = f"{self.base_url}/v1/customization/configs"
        try:
            if field_name == "model_name":
                self.log(f"Refreshing model names from endpoint {models_url}, value: {field_value}")

                # Use a synchronous HTTP client
                with httpx.Client(timeout=5.0) as client:
                    response = client.get(models_url, headers=self.headers)
                    response.raise_for_status()

                    models_data = response.json()
                    model_names = [model["base_model"] for model in models_data.get("models", [])]

                    build_config["model_name"]["options"] = model_names

                self.log("Updated model_name dropdown options.")

            if field_name == "training_type":
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
                            (model for model in models_data.get("models", []) if model["base_model"] == selected_model_name),
                            None
                        )

                        if selected_model:
                            # Update `training_type` dropdown with training types of the selected model
                            training_types = selected_model.get("training_types", [])
                            build_config["training_type"]["options"] = training_types
                            self.log(f"Updated training_type dropdown options: {training_types}")
                            fine_tuning_type = selected_model.get("finetuning_types", [])
                            build_config["fine_tuning_type"]["options"] = fine_tuning_type
                            self.log(f"Updated training_type dropdown options: {fine_tuning_type}")

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
        dataset_name = self.dataset
        if self.training_data is not None:
            dataset_name = await self.process_and_upload_dataset()
        output_model = dataset_name + "_" + self.model_name
        self.log(f"dataset_name: {dataset_name}")
        data = {
            "config": self.model_name,
            "dataset": {
                "name": dataset_name,
               "namespace": self.tenant_id if self.tenant_id else "tenant"
            },
            "description" : self.description,
            "hyperparameters": {
                "training_type": self.training_type,
                "finetuning_type": self.fine_tuning_type,
                "epochs": int(self.epochs),
                "batch_size": int(self.batch_size),
                "learning_rate": float(self.learning_rate),
            },
            "output_model": output_model,
        }

        # Add `adapter_dim` only if training_type is "lora"
        if self.fine_tuning_type == "lora":
            data["hyperparameters"]["lora"] = {"adapter_dim": 16}

        customizations_url = f"{self.base_url}/v1/customization/jobs"
        try:
            formatted_data = json.dumps(data, indent=2)

            self.log(f"Sending customization request to endpoint {customizations_url} with data: {formatted_data}")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(customizations_url, headers=self.headers, json=data)
                response.raise_for_status()

                result = response.json()
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}")

                result_dict = {**result}
                id_value = result_dict["id"]
                result_dict["url"] = f"{customizations_url}/{id_value}/status"
                return result_dict

        except httpx.TimeoutException as exc:
            error_msg = f"Request to {customizations_url} timed out"
            self.log(error_msg)
            raise ValueError(error_msg) from exc

        except httpx.HTTPStatusError as exc:
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

    def get_dataset_name(self, user_dataset_name=None):
        # Generate a default dataset name using the current date and time
        default_name = f"dataset-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        # Use the user-provided name if available, otherwise the default
        return user_dataset_name if user_dataset_name else default_name

    async def get_repo_id(self, tenant_id: str, user_dataset_name: str) -> str:
        """Fetches the repo id by checking if a dataset with the constructed name exists.

        If the dataset does not exist, creates a new dataset and returns its ID.

        Args:
            tenant_id (str): The tenant ID.
            user_dataset_name (str): The user-provided dataset name.

        Returns:
            str: The dataset ID if found or created, or None if an error occurs.
        """
        dataset_name = self.get_dataset_name(user_dataset_name)
        namespace = tenant_id if tenant_id else "tenant"

        url = f"{self.datastore_base_url}/v1/datastore/namespaces"
        page = 1

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/{namespace}")
                response.raise_for_status()
                self.log(f"returned data {response}")

                namespace_from_ds = response.get("namespace", None)
                # namespace not found, create it
                if not namespace_from_ds:
                    create_payload = {"namespace": namespace}
                    create_response = await client.post(url, json=create_payload)
                    create_response.raise_for_status()
                    created_namespace_response = create_response.json()

                repo_id = f"{namespace}/{dataset_name}"
                repo_type = "dataset"
                self.hf_api.create_repo(repo_id, repo_type=repo_type, exist_ok=True)

                return repo_id
        except httpx.HTTPStatusError as e:
            exception_str = str(exc)
            error_msg = f"Error processing namespace: {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc


    async def process_and_upload_dataset(self) -> str:
        """Asynchronously processes and uploads the dataset to the API in chunks.

        Returns the upload status.
        """
        try:
            # Inputs
            user_dataset_name = getattr(self, "dataset", None)
            repo_id = await self.get_repo_id(self.tenant_id, user_dataset_name)
            chunk_size = 10000  # Ensure chunk_size is an integer
            self.log(f"repo_id : {repo_id}")
            if not repo_id:
                err_msg = "repo_id must be provided."
                raise ValueError(err_msg)

            # Endpoint configuration
            url = f"{self.datastore_base_url}/v1"
            tasks = []

            chunk = []
            file_name_appender = user_dataset_name if user_dataset_name else "dataset"
            # Ensure DataFrame is iterable correctly
            for data_obj in self.training_data or []:
                # Check if the object is an instance of Data
                if not isinstance(data_obj, Data):
                    self.log(f"Skipping non-Data object in training data, but got: {data_obj}")
                    continue

                # Extract only "prompt" and "completion" fields if present
                filtered_data = {
                    "prompt": getattr(data_obj, "prompt", None),
                    "completion": getattr(data_obj, "completion", None),
                }

                # Check if both fields are present
                if filtered_data["prompt"] is not None and filtered_data["completion"] is not None:
                    chunk.append(filtered_data)

                # Process the chunk when it reaches the specified size
                if len(chunk) == chunk_size:
                    chunk_df = pd.DataFrame(chunk)
                    task = self.upload_chunk(chunk_df, self.chunk_number, file_name_appender, repo_id, url)
                    tasks.append(task)
                    chunk = []  # Reset the chunk
                    self.chunk_number += 1

            # Process the remaining rows in the last chunk
            if chunk:
                chunk_df = pd.DataFrame(chunk)
                task = self.upload_chunk(chunk_df, self.chunk_number, file_name_appender, repo_id, url)
                tasks.append(task)

            # Await all upload tasks
            await asyncio.gather(*tasks)

            file_url = f"hf://datasets/{repo_id}"

            entity_registry_url = f"https://{self.entity_store_base_url}/v1/datasets"
            create_payload = {
                "name": user_dataset_name,
                "namespace": self.tenant_id,
                "description": f"Dataset loaded using the input data {user_dataset_name}",
                "files_url": file_url,
                "project": "user_dataset_name"
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(entity_registry_url, json=create_payload)

            status_ok = 200
            if response.status_code == status_ok:
                logger.info("Chunk %s uploaded successfully!", chunk_number)
            else:
                logger.warning("Failed to upload chunk %s. Status code: %s", chunk_number, response.status_code)
                logger.warning(response.text)

            logger.info("All data has been processed and uploaded successfully.")
        except Exception as exc:
            exception_str = str(exc)
            error_msg = f"An unexpected error : {exception_str}"
            self.log(error_msg)
            raise ValueError(error_msg) from exc
        return repo_id

    async def upload_chunk(self, chunk_df, chunk_number, file_name_prefix, repo_id, base_url):
        """Asynchronously uploads a chunk of data to the REST API."""
        try:
            # Serialize the chunk DataFrame to JSONL format
            json_content = chunk_df.to_json(orient="records", lines=True)
            file_name = f"{file_name_prefix}_chunk_{chunk_number}.jsonl"
            file_in_memory = BytesIO(json_content.encode("utf-8"))
            try:
                self.hf_api.upload_file(
                    path_or_fileobj=file_in_memory,
                    path_in_repo=file_name,
                    repo_id=repo_id,
                    repo_type="dataset",
                    commit_message=f"Updated file at time: {datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
                )
            finally:
                file_in_memory.close()

        except Exception:
            logger.exception("An error occurred while uploading chunk %s", chunk_number)
