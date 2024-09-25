from astrapy import DataAPIClient, Collection, Database
from langflow.schema import Data
from typing import Union, Dict
from langflow.base.langchain_utilities.model import LCToolComponent
from pydantic import BaseModel, Field
from langchain.pydantic_v1 import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool
from langflow.io import (
    DictInput,
    SecretStrInput,
    StrInput,
    IntInput
)
from typing import Optional


class AstraToolComponent(LCToolComponent):
    display_name: str = "Astra DB Tool"
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
            name="projection",
            display_name="Projection fields",
            info="Attributes to return separated by comma.",
            required=True,
            value="*",
            advanced=True
        ),
        DictInput(name="tool_params",
                  info="Attributes to filter and description to the model. Mandatory arguments should start with an exclamation mark (e.g: !customerId)",
                  display_name="Tool params", is_list=True),
        DictInput(name="static_filters",
                  info="Attributes to filter and correspoding value",
                  display_name="Static filters", is_list=True),
        IntInput(name="limit", display_name="Limit", value=5, advanced=True)

    ]

    _cached_client: DataAPIClient | None = None
    _cached_db: Database | None = None
    _cached_collection: Collection | None = None

    def _build_collection(self):

        if self._cached_collection:
            return self._cached_collection

        _cached_client = DataAPIClient(self.token)
        _cached_db = _cached_client.get_database(
            self.api_endpoint,  namespace=self.namespace)
        self._cached_collection = _cached_db.get_collection(
            self.collection_name)
        return self._cached_collection

    def create_args_schema(self) -> Dict[str, BaseModel]:
        args = {}

        for key in self.tool_params.keys():
            if key.startswith('!'):  # Mandatory
                args[key[1:]] = (str, Field(
                    description=self.tool_params[key]))
            else:  # Optional
                args[key] = (Optional[str], Field(
                    description=self.tool_params[key], default=None))

        model = create_model('ToolInput', **args,  __base__=BaseModel)
        return {'ToolInput': model}

    def build_tool(self) -> StructuredTool:
        """
        Builds an Astra DB Collection tool.

        Args:

        Returns:
            Tool: The built Astra DB tool.
        """

        schema_dict = self.create_args_schema()
        tool = StructuredTool.from_function(
            name=self.tool_name,
            args_schema=schema_dict['ToolInput'],
            description=self.tool_description,
            func=self.run_model,
            return_direct=False
        )
        self.status = "Astra DB Tool created"

        return tool

    def projection_args(self, input_str: str) -> dict:
        elements = input_str.split(',')
        result = {}

        for element in elements:
            if element.startswith('!'):
                result[element[1:]] = False
            else:
                result[element] = True

        return result

    def run_model(self, **args) -> Union[Data, list[Data]]:
        collection = self._build_collection()
        results = collection.find(({**args, **self.static_filters} or {}),
                                  projection=self.projection_args(
                                      self.projection),
                                  limit=self.limit)
        data = [{"text": repr(doc)} for doc in results]
        self.status = data
        return data
