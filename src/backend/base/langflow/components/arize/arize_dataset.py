# Standard library imports
import json
import logging

# Third-party imports
import httpx
import pandas as pd

# Local application imports
from arize.experimental.datasets import ArizeDatasetsClient

from langflow.custom import Component
from langflow.io import DictInput, DropdownInput, MessageTextInput, Output, SecretStrInput
from langflow.schema import Data

logger = logging.getLogger(__name__)


class ArizeAIDatastoreComponent(Component):
    display_name = "Arize AI Datastore"
    description = "Fetch available datasets and display details"
    icon = "Arize"
    name = "ArizeAIDatastoreComponent"
    beta = True

    # Inputs: A dropdown for dataset selection and a dictionary to store dataset metadata
    inputs = [
        SecretStrInput(
            name="developer_key",
            display_name="ArizeAI Developer Key",
            info="The ArizeAI Developer Key to use.",
            advanced=False,
        ),
        SecretStrInput(
            name="api_key",
            display_name="ArizeAI API Key",
            info="The ArizeAI API Key to use.",
            advanced=False,
        ),
        MessageTextInput(
            name="space_id",
            display_name="ArizeAI Space Id",
            info="The ArizeAI Space Id to use.",
            advanced=False,
        ),
        DropdownInput(
            name="dataset_name",
            display_name="Dataset Name",
            info="Select a dataset from the available list",
            options=[],  # Dynamically populated
            refresh_button=True,  # Allow the dropdown to be refreshed
        ),
        DictInput(
            name="dataset_metadata",
            display_name="Dataset Metadata",
            info="Dictionary storing metadata for the datasets",
            advanced=True,  # This is the advanced field we populate dynamically
        ),
    ]

    # Outputs: A list of Data objects
    outputs = [Output(name="data_list", display_name="Data List", method="get_dataset_data_list")]

    def fetch_and_process_datasets(self, client) -> list[Data]:
        """Fetch and process the selected dataset, and return a list of Data objects."""
        space_id = getattr(self, "space_id", None)
        selected_dataset_name = getattr(self, "dataset_name", None)
        self.log(f"selected_dataset_name {selected_dataset_name}")
        dataset_metadata = getattr(self, "dataset_metadata", None)
        dataset_info = dataset_metadata.get(selected_dataset_name)
        self.log(f"dataset_info {dataset_info}")
        if not selected_dataset_name:
            logger.warning("No dataset selected. Please select a dataset from the dropdown.")
            return []

        try:
            dataset_id = dataset_info.get("dataset_id")
            self.log(f"dataset_id {dataset_id}")
            # Fetch the specific dataset by ID
            dataset = client.get_dataset(space_id=space_id, dataset_id=dataset_id)
            if dataset.empty:
                self.log(f"No data found for dataset: {selected_dataset_name}")
                return []
            self.log(f"dataset {dataset}")
            # Process the dataset row by row
            new_data = []
            for _, row in dataset.iterrows():
                # Check if the input and output messages exist in the row
                input_messages = row.get("attributes.llm.input_messages", None)
                output_messages = row.get("attributes.llm.output_messages", None)

                if input_messages and output_messages:
                    # Parse the messages if they exist and are valid JSON
                    try:
                        input_messages = (
                            json.loads(input_messages) if isinstance(input_messages, str) else input_messages
                        )
                        output_messages = (
                            json.loads(output_messages) if isinstance(output_messages, str) else output_messages
                        )
                    except (json.JSONDecodeError, TypeError):
                        logger.exception("Error parsing JSON for row %s", row.name)
                        input_messages = []
                        output_messages = []

                    # Process the messages
                    input_message, output_message = self.process_messages(input_messages, output_messages)
                else:
                    # Fallback to attributes.input.value and attributes.output.value if messages don't exist
                    input_message = row.get("attributes.input.value", None)
                    output_message = row.get("attributes.output.value", None)

                new_data.append({"input": input_message, "completion": output_message})

            # Create new DataFrame with the mapped values
            new_df = pd.DataFrame(new_data)

            # Create a list of Data objects, one for each row
            data_objects = [
                Data(
                    data={"input": row["input"], "completion": row["completion"]},
                    dataset_name=selected_dataset_name,
                    document_type="Arize dataset",
                    description="",
                )
                for _, row in new_df.iterrows()
            ]
            length = len(data_objects)
            message = f"Created {length} Data objects for dataset: {data_objects}"
            logger.info(message)
            return data_objects

        except (httpx.RequestError, ValueError):
            logger.exception("Error fetching or processing datasets")
        else:
            return []

    def process_messages(self, input_messages, output_messages):
        """Extracts 'user' and 'assistant' messages from the input and output messages.

        Returns the extracted user input and assistant output.
        """
        # Extract 'user' message from input messages
        user_input = next((msg["message.content"] for msg in input_messages if msg["message.role"] == "user"), None)

        # Extract "assistant" message from output messages
        assistant_output = next(
            (msg["message.content"] for msg in output_messages if msg["message.role"] == "assistant"), None
        )

        # If no messages found, return fallback from 'attributes.input.value' and 'attributes.output.value'
        if not user_input:
            user_input = None
        if not assistant_output:
            assistant_output = None

        return user_input, assistant_output

    def get_dataset_data_list(self) -> list[Data]:
        """Return the list of Data objects created from the dataset."""
        client = self.get_client()
        return self.fetch_and_process_datasets(client)

    def fetch_datasets(self, client) -> pd.DataFrame:
        """Fetch datasets from the client and return a DataFrame with dataset_id and dataset_name."""
        space_id = getattr(self, "space_id", None)
        try:
            datasets = client.list_datasets(space_id)
            if datasets.empty:
                logger.warning("No datasets found.")
                return pd.DataFrame(columns=["dataset_id", "dataset_name"])

        except (httpx.RequestError, ValueError):
            logger.exception("Error fetching datasets")
            return pd.DataFrame(columns=["dataset_id", "dataset_name"])

        return datasets

    def update_build_config(self, build_config, field_value, field_name=None):
        """Update the build configuration and store datasets in DictInput when the dropdown is updated."""
        if field_name == "dataset_name":
            log_message = f"Fetching datasets and storing them in DictInput {field_value}"
            logger.info(log_message)
            # Fetch datasets
            client = self.get_client()  # Assuming you have a method to initialize the client
            datasets_df = self.fetch_datasets(client)

            if not datasets_df.empty:
                # Convert the DataFrame to a dictionary for dropdown and metadata storage
                datasets_dict = datasets_df.set_index("dataset_name").to_dict("index")

                # Store metadata for each dataset in DictInput
                build_config["dataset_metadata"]["value"] = datasets_dict
                # Populate the dropdown with dataset names
                build_config["dataset_name"]["options"] = datasets_df["dataset_name"].tolist()
            else:
                # If no datasets, clear the dropdown and DictInput
                build_config["dataset_name"]["options"] = []
                build_config["dataset_metadata"]["value"] = {}
                logger.warning("No datasets found, dropdown options and metadata cleared.")

        return build_config

    def get_client(self):
        """Initialize and return an instance of ArizeDatasetsClient."""
        try:
            developer_key = getattr(self, "developer_key", None)
            api_key = getattr(self, "developer_key", None)
            client = ArizeDatasetsClient(developer_key=developer_key, api_key=api_key)
            logger.info("Successfully initialized ArizeDatasetsClient.")
        except Exception:
            logger.exception("Failed to initialize ArizeDatasetsClient")
            raise
        else:
            return client
