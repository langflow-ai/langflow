import httpx
import json
from langflow.custom import Component
from langflow.io import MessageTextInput, Output, DropdownInput, IntInput, FloatInput

class NVIDIANeMoCustomizerComponent(Component):
    display_name = "NVIDIA NeMo Customizer"
    description = "Train models"
    icon = "NVIDIA"
    name = "NVIDIANeMoCustomizer"
    beta = True

    # TODO allow override via advanced properties
    endpoint = "localhost:9000"
    url = f"http://{endpoint}/v2/customizations"
    models_url = f"http://{endpoint}/v2/availableParentModels"

    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }

    inputs = [
        MessageTextInput(
            name="dataset",
            display_name="Dataset",
            info="Enter the dataset ID or name used to train the model",
            value="dataset-RWZGSkCGdeP35SDAxqTtvy"
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
        try:
            if field_name == "model_name":
                self.log("Refreshing model names from availableParentModels endpoint.", name="NeMoCustomizerComponent")

                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(self.models_url, headers=self.headers)
                    response.raise_for_status()

                    models_data = response.json()
                    model_names = [model["name"] for model in models_data.get("models", [])]

                    build_config["model_name"]["options"] = model_names

                    self.log("Updated model_name dropdown options.", name="NeMoCustomizerComponent")
            return build_config
        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTP error {exc.response.status_code} on {self.models_url}"
            self.log(error_msg, name="NeMoCustomizerComponent")
            raise ValueError(error_msg)
        except Exception as exc:
            error_msg = f"Error refreshing model names: {str(exc)}"
            self.log(error_msg, name="NeMoCustomizerComponent")
            raise ValueError(error_msg)

    async def customize(self) -> dict:
        data = {
            "parent_model_id": self.model_name,
            "dataset": self.dataset,
            "hyperparameters": {
                "training_type": self.training_type,
                "epochs": int(self.epochs),
                "batch_size": int(self.batch_size),
                "learning_rate": float(self.learning_rate),
                "adapter_dim": 16
            },
            "sha": "main"
        }

        try:
            formatted_data = json.dumps(data, indent=2)
            self.log(f"Sending request to NeMo API with data: {formatted_data}", name="NeMoCustomizerComponent")

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self.url, headers=self.headers, json=data)
                response.raise_for_status()

                result = response.json()
                formatted_result = json.dumps(result, indent=2)
                self.log(f"Received successful response: {formatted_result}", name="NeMoCustomizerComponent")

                result_dict = {**result}
                id = result_dict["id"]
                result_dict["url"] = f"{self.url}/{id}"
                return result_dict

        except httpx.TimeoutException:
            error_msg = f"Request to {self.url} timed out"
            self.log(error_msg, name="NeMoCustomizerComponent")
            raise ValueError(error_msg)

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_content = exc.response.text
            error_msg = f"HTTP error {status_code} on URL: {self.url}. Response content: {response_content}"
            self.log(error_msg, name="NeMoCustomizerComponent")
            raise ValueError(error_msg)

        except Exception as exc:
            error_msg = f"An unexpected error occurred on URL {self.url}: {str(exc)}"
            self.log(error_msg, name="NeMoCustomizerComponent")
            raise ValueError(error_msg)
