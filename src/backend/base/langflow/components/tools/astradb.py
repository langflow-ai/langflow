from typing import Any

from astrapy import Collection, DataAPIClient, Database
from langchain.pydantic_v1 import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.io import DictInput, IntInput, SecretStrInput, StrInput
from langflow.schema import Data


class AstraDBToolComponent(LCToolComponent):
    display_name: str = "Astra DB"
    description: str = "Create a tool to get data from DataStax Astra DB Collection"
    documentation: str = "https://astra.datastax.com"
    icon: str = "AstraDB"

    inputs = [
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            info="The name of the tool.",
            required=True,
        ),
        StrInput(
            name="tool_description",
            display_name="Tool Description",
            info="The description of the tool.",
            required=True,
        ),
        StrInput(
            name="namespace",
            display_name="Namespace Name",
            info="The name of the namespace within Astra where the collection is be stored.",
            value="default_keyspace",
            advanced=True,
        ),
        StrInput(
            name="collection_name",
            display_name="Collection Name",
            info="The name of the collection within Astra DB where the vectors will be stored.",
            required=True,
        ),
        SecretStrInput(
            name="token",
            display_name="Astra DB Application Token",
            info="Authentication token for accessing Astra DB.",
            value="ASTRA_DB_APPLICATION_TOKEN",
            required=True,
        ),
        StrInput(
            name="api_endpoint",
            display_name="API Endpoint",
            info="API endpoint URL for the Astra DB service.",
            value="ASTRA_DB_API_ENDPOINT",
            required=True,
        ),
        StrInput(
            name="projection_attributes",
            display_name="Projection Attributes",
            info="Attributes to return separated by comma.",
            required=True,
            value="*",
            advanced=True,
        ),
        DictInput(
            name="tool_params",
            info="Attributes to filter and description to the model. Add ! for mandatory (e.g: !customerId)",
            display_name="Tool params",
            is_list=True,
        ),
        DictInput(
            name="static_filters",
            info="Attributes to filter and correspoding value",
            display_name="Static filters",
            is_list=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=5,
        ),
    ]

    _cached_client: DataAPIClient | None = None
    _cached_db: Database | None = None
    _cached_collection: Collection | None = None

    def _build_collection(self):
        if self._cached_collection:
            return self._cached_collection

        _cached_client = DataAPIClient(self.token)
        _cached_db = _cached_client.get_database(self.api_endpoint, namespace=self.namespace)
        self._cached_collection = _cached_db.get_collection(self.collection_name)
        return self._cached_collection

    def create_args_schema(self) -> dict[str, BaseModel]:
        args: dict[str, tuple[Any, Field] | list[str]] = {}

        for key in self.tool_params:
            if key.startswith("!"):  # Mandatory
                args[key[1:]] = (str, Field(description=self.tool_params[key]))
            else:  # Optional
                args[key] = (str | None, Field(description=self.tool_params[key], default=None))

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def build_tool(self) -> StructuredTool:
        """Builds an Astra DB Collection tool.

        Returns:
            Tool: The built Astra DB tool.
        """
        schema_dict = self.create_args_schema()

        tool = StructuredTool.from_function(
            name=self.tool_name,
            args_schema=schema_dict["ToolInput"],
            description=self.tool_description,
            func=self.run_model,
            return_direct=False,
        )
        self.status = "Astra DB Tool created"

        return tool

    def projection_args(self, input_str: str) -> dict:
        elements = input_str.split(",")
        result = {}

        for element in elements:
            if element.startswith("!"):
                result[element[1:]] = False
            else:
                result[element] = True

        return result

    def run_model(self, **args) -> Data | list[Data]:
        collection = self._build_collection()
        results = collection.find(
            ({**args, **self.static_filters}),
            projection=self.projection_args(self.projection_attributes),
            limit=self.number_of_results,
        )

        data: list[Data] = [Data(data=doc) for doc in results]
        self.status = data
        return data
