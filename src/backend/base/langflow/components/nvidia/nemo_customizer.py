import httpx
import json
from langflow.custom import Component
from langflow.io import MessageTextInput, Output, DropdownInput, IntInput, FloatInput, StrInput, DataInput
from langflow.schema import Data, DataFrame
import pandas as pd
import asyncio

class NVIDIANeMoCustomizerComponent(Component):
    display_name = "Customizer"
    description = "Train models"
    icon = "NVIDIA"
    name = "NVIDIANeMoCustomizer"
    beta = True

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    chunk_number = 1

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
            advanced=True
        ),
        StrInput(
            name="tenant_id",
            display_name="Tenant ID",
            info="Tenant id for dataset creation, if not provided default value `tenant` is used.",
            advanced=True
        ),
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Enter the dataset ID or name used to train the model",
            value="dataset-RWZGSkCGdeP35SDAxqTtvy"
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
            options=[
                "codellama-70b",
                "gemma-7b",
                "gpt-43b-002",
                "gpt8b-4k",
                "llama-2-13b",
                "llama-2-70b",
                "llama-2-7b",
                "meta/llama-3_1-70b-instruct",
                "meta/llama-3_1-8b-instruct",
                "meta/llama3-70b-instruct",
                "meta/llama3-8b-instruct",
                "mistral-7b",
                "mixtral-8x7b"
            ],
            value="mixtral-8x7b",
            refresh_button=True
        ),
        DropdownInput(
            name="training_type",
            display_name="Training Type",
            info="Select the type of training to use",
            options=["p-tuning", "lora", "fine-tuning"],
            value="lora",  # Default value
        ),
        IntInput(
            name="epochs",
            display_name="Epochs",
            info="Number of times to cycle through the training data",
            value=5
        ),
        IntInput(
            name="batch_size",
            display_name="Batch size",
            info="The number of samples used in each training iteration",
            value=16
        ),
        FloatInput(
            name="learning_rate",
            display_name="Learning rate",
            info="The number of samples used in each training iteration",
            value=0.0001
        ),
    ]

    outputs = [
        Output(display_name="Job Result", name="data", method="customize"),
    ]

    async def update_build_config(self, build_config, field_value, field_name=None):
        """
        Updates the component's configuration based on the selected option or refresh button.
        """
        models_url = f"{self.base_url}/v2/availableParentModels"

        try:
            if field_name == "model_name":
                self.log(f"Refreshing model names from endpoint {models_url}", name="NVIDIANeMoCustomizerComponent")

                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(models_url, headers=self.headers)
                    response.raise_for_status()

                    models_data = response.json()
                    model_names = [model["name"] for model in models_data.get("models", [])]

                    build_config["model_name"]["options"] = model_names

                    self.log("Updated model_name dropdown options.", name="NVIDIANeMoCustomizerComponent")
            return build_config
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on {models_url}"
            self.log(error_msg, name="NVIDIANeMoCustomizerComponent")
            raise ValueError(error_msg)
        except Exception as exc:
            error_msg = f"Error refreshing model names: {str(exc)}"
            self.log(error_msg, name="NVIDIANeMoCustomizerComponent")
            raise ValueError(error_msg)

    async def customize(self) -> dict:
        dataset_name = self.dataset
        if self.training_data is not None:
            dataset_name = await self.process_and_upload_dataset()
        self.log(f"dataset_name: {dataset_name}", name="NVIDIANeMoCustomizerComponent")
        data = {
            "parent_model_id": self.model_name,
            "dataset": dataset_name,
            "hyperparameters": {
                "training_type": self.training_type,
                "epochs": int(self.epochs),
                "batch_size": int(self.batch_size),
                "learning_rate": float(self.learning_rate),
                "adapter_dim": 16
            },
            "sha": "main"
        }
        customizations_url = f"{self.base_url}/v2/customizations"
        try:
            formatted_data = json.dumps(data, indent=2)

            self.log(f"Sending customization request to endpoint {customizations_url} with data: {formatted_data}", name="NVIDIANeMoCustomizerComponent")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(customizations_url, headers=self.headers, json=data)
                response.raise_for_status()

                result = response.json()
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}", name="NVIDIANeMoCustomizerComponent")

                result_dict = {**result}
                id = result_dict["id"]
                result_dict["url"] = f"{customizations_url}/{id}"
                return result_dict

        except httpx.TimeoutException:
            error_msg = f"Request to {customizations_url} timed out"
            self.log(error_msg, name="NVIDIANeMoCustomizerComponent")
            raise ValueError(error_msg)

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} on URL: {customizations_url}. Response content: {response_content}"
            self.log(error_msg, name="NVIDIANeMoCustomizerComponent")
            raise ValueError(error_msg)

        except Exception as exc:
            error_msg = f"An unexpected error occurred on URL {customizations_url}: {str(exc)}"
            self.log(error_msg, name="NVIDIANeMoCustomizerComponent")
            raise ValueError(error_msg)

    def get_dataset_name(self, user_dataset_name=None):
        # Generate a default dataset name using the current date and time
        default_name = f"dataset-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Use the user-provided name if available, otherwise the default
        dataset_name = user_dataset_name if user_dataset_name else default_name

        return dataset_name

    async def get_dataset_id(self, tenant_id: str, user_dataset_name: str) -> str:
        """
        Fetches the dataset ID by checking if a dataset with the constructed name exists.
        If the dataset does not exist, creates a new dataset and returns its ID.

        Args:
            tenant_id (str): The tenant ID.

        Returns:
            str: The dataset ID if found or created, or None if an error occurs.
        """
        appender = self.get_dataset_name(user_dataset_name)
        dataset_name = f"{tenant_id}-{appender}"

        url = f"{self.datastore_base_url}/v1/datasets"
        page = 1

        try:
            async with httpx.AsyncClient() as client:
                while True:
                    response = await client.get(f"{url}?page_size=10&page={page}")
                    if response.status_code == 422:
                        self.log(f"No more pages to fetch, page: {page}", name="NVIDIANeMoCustomizerComponent")
                        break;
                    response.raise_for_status()

                    datasets = response.json().get("datasets", [])
                    for dataset in datasets:
                        if dataset.get("name") == dataset_name:
                            return dataset.get("id")
                    if not datasets:
                        break  # No more datasets to process

                    page += 1

                # If dataset not found, create it
                create_payload = {
                    "name": dataset_name,
                    "description": f"{dataset_name} for {tenant_id}"
                }
                create_response = await client.post(url, json=create_payload)
                create_response.raise_for_status()
                created_dataset = create_response.json()
                return created_dataset.get("id")

        except httpx.HTTPStatusError as e:
            self.log(f"Error processing datasets: {e}", name="NVIDIANeMoCustomizerComponent")
            return None

    async def process_and_upload_dataset(self) -> str:
        """
        Asynchronously processes and uploads the dataset to the API in chunks.
        Returns the upload status.
        """
        try:
            # Inputs
            user_dataset_name = getattr(self, 'dataset', None)
            dataset_name = await self.get_dataset_id(self.tenant_id, user_dataset_name)
            chunk_size = 10000  # Ensure chunk_size is an integer
            self.log(f"dataset_name : {dataset_name}", name="NVIDIANeMoCustomizerComponent")
            if not dataset_name:
                raise ValueError("dataset_name must be provided.")

            # Endpoint configuration
            url = f"{self.datastore_base_url}/v1"
            tasks = []

            chunk = []
            file_name_appender = user_dataset_name if user_dataset_name else "dataset"
            # Ensure DataFrame is iterable correctly
            for data_obj in self.training_data or []:
                # Check if the object is an instance of Data
                if not isinstance(data_obj, Data):
                    self.log(f"Skipping non-Data object in training data, but got: {data_obj}", name="NVIDIANeMoCustomizerComponent")
                    continue

                # Extract only 'input' and 'completion' fields if present
                filtered_data = {
                    "input": getattr(data_obj, "input", None),
                    "completion": getattr(data_obj, "completion", None)
                }

                # Check if both fields are present
                if filtered_data["input"] is not None and filtered_data["completion"] is not None:
                    chunk.append(filtered_data)

                # Process the chunk when it reaches the specified size
                if len(chunk) == chunk_size:
                    chunk_df = pd.DataFrame(chunk)
                    task = self.upload_chunk(chunk_df, self.chunk_number, file_name_appender, dataset_name, url)
                    tasks.append(task)
                    chunk = []  # Reset the chunk
                    self.chunk_number += 1

            # Process the remaining rows in the last chunk
            if chunk:
                chunk_df = pd.DataFrame(chunk)
                task = self.upload_chunk(chunk_df, self.chunk_number, file_name_appender, dataset_name, url)
                tasks.append(task)

            # Await all upload tasks
            await asyncio.gather(*tasks)

            logger.info("All data has been processed and uploaded successfully.", name="NVIDIANeMoCustomizerComponent")
            return dataset_name

        except Exception as e:
            logger.error(f"An error occurred: {str(e)}", name="NVIDIANeMoCustomizerComponent")
            return f"An error occurred: {str(e)}"

    async def upload_chunk(self, chunk_df, chunk_number, file_name_prefix, dataset_id, base_url):
        """
        Asynchronously uploads a chunk of data to the REST API.
        """
        try:
            # Serialize the chunk DataFrame to JSONL format
            json_content = chunk_df.to_json(orient="records", lines=True)
            file_name = f"{file_name_prefix}_chunk_{chunk_number}.jsonl"
            file_in_memory = BytesIO(json_content.encode('utf-8'))

            filepath = f"training/{file_name}"
            url = f"{base_url}/datasets/{dataset_id}/files/contents/{filepath}"

            files = {'file': (file_name, file_in_memory, 'application/json')}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, files=files)

            if response.status_code == 200:
                logger.info(f"Chunk {chunk_number} uploaded successfully!", name="NVIDIANeMoCustomizerComponent")
            else:
                logger.warning(f"Failed to upload chunk {chunk_number}. Status code: {response.status_code}", name="NVIDIANeMoCustomizerComponent")
                logger.warning(response.text, name="NVIDIANeMoCustomizerComponent")

        except Exception as e:
            logger.error(f"An error occurred while uploading chunk {chunk_number}: {str(e)}", name="NVIDIANeMoCustomizerComponent")
        finally:
            file_in_memory.close()