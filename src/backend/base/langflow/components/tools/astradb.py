import os
from typing import Any

from astrapy import Collection, DataAPIClient, Database
from langchain.pydantic_v1 import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool, Tool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.io import BoolInput, DictInput, HandleInput, IntInput, SecretStrInput, StrInput, TableInput
from langflow.schema import Data
from langflow.schema.table import EditMode


class AstraDBToolComponent(LCToolComponent):
    display_name: str = "Astra DB Tool"
    description: str = "Create a tool to get transactional data from DataStax Astra DB Collection"
    documentation: str = "https://docs.langflow.org/Components/components-tools#astra-db-tool"
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
            name="keyspace",
            display_name="Keyspace Name",
            info="The name of the keyspace within Astra where the collection is be stored.",
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
        SecretStrInput(
            name="api_endpoint",
            display_name="Database" if os.getenv("ASTRA_ENHANCED", "false").lower() == "true" else "API Endpoint",
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
        TableInput(
            name="tools_params_v2",
            display_name="Tools Params",
            info="Define the structure for the tool parameters.",
            required=False,
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the output field.",
                    "default": "description of field",
                    "edit_mode": EditMode.POPOVER,
                },
                {
                    "name": "metadata",
                    "display_name": "Is Metadata",
                    "type": "boolean",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate if the field is included in the metadata field."),
                    "options": ["True", "False"],
                    "default": "False",
                },
                {
                    "name": "mandatory",
                    "display_name": "Is Mandatory",
                    "type": "boolean",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate if the field is mandatory."),
                    "options": ["True", "False"],
                    "default": "False",
                },
                {
                    "name": "operator",
                    "display_name": "Operator",
                    "type": "str",
                    "description": "Set the operator for the field. https://docs.datastax.com/en/astra-db-serverless/api-reference/documents.html#operators",
                    "default": "$eq",
                    "options": ["$gt", "$gte", "$lt", "$lte", "$eq", "$ne", "$in", "$nin", "$exists", "$all", "$size"],
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[],
        ),
        DictInput(
            name="tool_params",
            info="DEPRECATED: Attributes to filter and description to the model. Add ! for mandatory (e.g: !customerId)",
            display_name="Tool params",
            is_list=True,
            advanced=True,
        ),
        DictInput(
            name="static_filters",
            info="Attributes to filter and correspoding value",
            display_name="Static filters",
            advanced=True,
            is_list=True,
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=5,
        ),
        BoolInput(
            name="use_search_query",
            display_name="Semantic Search",
            info="When this parameter is activated, the search query parameter will be used to search the collection.",
            advanced=False,
            value=False,
        ),
        HandleInput(name="embedding", display_name="Embedding", input_types=["Embeddings"]),
        BoolInput(
            name="use_vectorize",
            display_name="Use Vectorize",
            info="When this parameter is activated, Astra Vectorize method will be used to generate the embeddings.",
            advanced=False,
            value=False,
        ),
    ]

    _cached_client: DataAPIClient | None = None
    _cached_db: Database | None = None
    _cached_collection: Collection | None = None

    def _build_collection(self):
        if self._cached_collection:
            return self._cached_collection

        cached_client = DataAPIClient(self.token)
        cached_db = cached_client.get_database(self.api_endpoint, keyspace=self.keyspace)
        self._cached_collection = cached_db.get_collection(self.collection_name)
        return self._cached_collection

    def create_args_schema(self) -> dict[str, BaseModel]:
        print("tools_params")
        self.log.warning("This is the old way to define the tool parameters. Please use the new way.")
        args: dict[str, tuple[Any, Field] | list[str]] = {}

        for key in self.tool_params:
            if key.startswith("!"):  # Mandatory
                args[key[1:]] = (str, Field(description=self.tool_params[key]))
            else:  # Optional
                args[key] = (str | None, Field(description=self.tool_params[key], default=None))

        if self.use_search_query:
            args["search_query"] = (
                str | None,
                Field(description="Search query to find relevant documents.", default=None),
            )
        print("args schema")
        print(args)

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def create_args_schema_v2(self) -> dict[str, BaseModel]:
        print("tools_params_v2")
        print(self.tools_params_v2)
        args: dict[str, tuple[Any, Field] | list[str]] = {}

        for tool_param in self.tools_params_v2:
            print(tool_param)
            if tool_param["mandatory"]:
                args[tool_param["name"]] = (str, Field(description=tool_param["description"]))
            else:
                args[tool_param["name"]] = (str | None, Field(description=tool_param["description"], default=None))

        if self.use_search_query:
            args["search_query"] = (
                str | None,
                Field(description="Search query to find relevant documents.", default=None),
            )
        print("args schema")
        print(args)

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def build_tool(self) -> Tool:
        """Builds an Astra DB Collection tool.

        Returns:
            Tool: The built Astra DB tool.
        """
        schema_dict = self.create_args_schema_v2() if self.tools_params_v2 is not None else self.create_args_schema()

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

        if elements == ["*"]:
            return None

        result["$vector"] = False

        for element in elements:
            if element.startswith("!"):
                result[element[1:]] = False
            else:
                result[element] = True

        return result

    def build_filter(self, args: dict, filter_settings: list) -> dict:
        """Build filter dictionary for AstraDB query.

        Args:
            args: Dictionary of arguments from the tool
            filter_settings: List of filter settings from tools_params_v2

        Returns:
            Dictionary containing the filter conditions
        """
        filters = {**self.static_filters}

        for key, value in args.items():
            # Skip search_query as it's handled separately
            if key == "search_query":
                continue

            filter_setting = next((x for x in filter_settings if x["name"] == key), None)
            if filter_setting and value is not None:
                filter_key = key if not filter_setting["metadata"] else f"metadata.{key}"
                if filter_setting["operator"] == "$exists":
                    filters[filter_key] = {filter_setting["operator"]: True}
                elif filter_setting["operator"] in ["$in", "$nin", "$all"]:
                    filters[filter_key] = {filter_setting["operator"]: [value]}
                else:
                    filters[filter_key] = {filter_setting["operator"]: value}

        print("filters")
        print(filters)
        return filters

    def run_model(self, **args) -> Data | list[Data]:
        collection = self._build_collection()
        sort = {}

        # Build filters using the new method
        filters = self.build_filter(args, self.tools_params_v2)

        if self.use_search_query:
            if self.use_vectorize:
                sort["$vectorize"] = args["search_query"]
                del args["search_query"]
            else:
                filters["search_query"] = args["search_query"]

        find_options = {
            "filter": filters,
            "limit": self.number_of_results,
            "sort": sort,
        }

        projection = self.projection_args(self.projection_attributes)
        if projection and len(projection) > 0:
            find_options["projection"] = projection

        results = collection.find(**find_options)

        data: list[Data] = [Data(data=doc) for doc in results]
        self.status = data
        return data
