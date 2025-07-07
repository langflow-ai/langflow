import os
from datetime import datetime, timezone
from typing import Any

from astrapy import Collection, DataAPIClient, Database
from astrapy.admin import parse_api_endpoint
from langchain.pydantic_v1 import BaseModel, Field, create_model
from langchain_core.tools import StructuredTool, Tool

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.io import BoolInput, DictInput, HandleInput, IntInput, SecretStrInput, StrInput, TableInput
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.table import EditMode


class AstraDBToolComponent(LCToolComponent):
    display_name: str = "Astra DB Tool"
    description: str = "Tool to run hybrid vector and metadata search on DataStax Astra DB Collection"
    documentation: str = "https://docs.langflow.org/components-bundle-components"
    icon: str = "AstraDB"

    inputs = [
        StrInput(
            name="tool_name",
            display_name="Tool Name",
            info="The name of the tool to be passed to the LLM.",
            required=True,
        ),
        StrInput(
            name="tool_description",
            display_name="Tool Description",
            info="Describe the tool to LLM. Add any information that can help the LLM to use the tool.",
            required=True,
        ),
        StrInput(
            name="keyspace",
            display_name="Keyspace Name",
            info="The name of the keyspace within Astra where the collection is stored.",
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
            info="Attributes to be returned by the tool separated by comma.",
            required=True,
            value="*",
            advanced=True,
        ),
        TableInput(
            name="tools_params_v2",
            display_name="Tools Parameters",
            info="Define the structure for the tool parameters. Describe the parameters "
            "in a way the LLM can understand how to use them.",
            required=False,
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Specify the name of the output field/parameter for the model.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "attribute_name",
                    "display_name": "Attribute Name",
                    "type": "str",
                    "description": "Specify the attribute name to be filtered on the collection. "
                    "Leave empty if the attribute name is the same as the name of the field.",
                    "default": "",
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
                    "name": "is_timestamp",
                    "display_name": "Is Timestamp",
                    "type": "boolean",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate if the field is a timestamp."),
                    "options": ["True", "False"],
                    "default": "False",
                },
                {
                    "name": "operator",
                    "display_name": "Operator",
                    "type": "str",
                    "description": "Set the operator for the field. "
                    "https://docs.datastax.com/en/astra-db-serverless/api-reference/documents.html#operators",
                    "default": "$eq",
                    "options": ["$gt", "$gte", "$lt", "$lte", "$eq", "$ne", "$in", "$nin", "$exists", "$all", "$size"],
                    "edit_mode": EditMode.INLINE,
                },
            ],
            value=[],
        ),
        DictInput(
            name="tool_params",
            info="DEPRECATED: Attributes to filter and description to the model. "
            "Add ! for mandatory (e.g: !customerId)",
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
        BoolInput(
            name="use_vectorize",
            display_name="Use Astra DB Vectorize",
            info="When this parameter is activated, Astra DB Vectorize method will be used to generate the embeddings.",
            advanced=False,
            value=False,
        ),
        HandleInput(name="embedding", display_name="Embedding Model", input_types=["Embeddings"]),
        StrInput(
            name="semantic_search_instruction",
            display_name="Semantic Search Instruction",
            info="The instruction to use for the semantic search.",
            required=True,
            value="Search query to find relevant documents.",
            advanced=True,
        ),
    ]

    _cached_client: DataAPIClient | None = None
    _cached_db: Database | None = None
    _cached_collection: Collection | None = None

    def _build_collection(self):
        if self._cached_collection:
            return self._cached_collection

        try:
            environment = parse_api_endpoint(self.api_endpoint).environment
            cached_client = DataAPIClient(self.token, environment=environment)
            cached_db = cached_client.get_database(self.api_endpoint, keyspace=self.keyspace)
            self._cached_collection = cached_db.get_collection(self.collection_name)
        except Exception as e:
            msg = f"Error building collection: {e}"
            raise ValueError(msg) from e
        else:
            return self._cached_collection

    def create_args_schema(self) -> dict[str, BaseModel]:
        """DEPRECATED: This method is deprecated. Please use create_args_schema_v2 instead.

        It is keep only for backward compatibility.
        """
        logger.warning("This is the old way to define the tool parameters. Please use the new way.")
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

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def create_args_schema_v2(self) -> dict[str, BaseModel]:
        """Create the tool input schema using the new tool parameters configuration."""
        args: dict[str, tuple[Any, Field] | list[str]] = {}

        for tool_param in self.tools_params_v2:
            if tool_param["mandatory"]:
                args[tool_param["name"]] = (str, Field(description=tool_param["description"]))
            else:
                args[tool_param["name"]] = (str | None, Field(description=tool_param["description"], default=None))

        if self.use_search_query:
            args["search_query"] = (
                str,
                Field(description=self.semantic_search_instruction),
            )

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def build_tool(self) -> Tool:
        """Builds an Astra DB Collection tool.

        Returns:
            Tool: The built Astra DB tool.
        """
        schema_dict = self.create_args_schema() if len(self.tool_params.keys()) > 0 else self.create_args_schema_v2()

        tool = StructuredTool.from_function(
            name=self.tool_name,
            args_schema=schema_dict["ToolInput"],
            description=self.tool_description,
            func=self.run_model,
            return_direct=False,
        )
        self.status = "Astra DB Tool created"

        return tool

    def projection_args(self, input_str: str) -> dict | None:
        """Build the projection arguments for the AstraDB query."""
        elements = input_str.split(",")
        result = {}

        if elements == ["*"]:
            return None

        # Force the projection to exclude the $vector field as it is not required by the tool
        result["$vector"] = False

        # Fields with ! as prefix should be removed from the projection
        for element in elements:
            if element.startswith("!"):
                result[element[1:]] = False
            else:
                result[element] = True

        return result

    def parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse a timestamp string into Astra DB REST API format.

        Args:
            timestamp_str (str): Input timestamp string

        Returns:
            datetime: Datetime object

        Raises:
            ValueError: If the timestamp cannot be parsed
        """
        # Common datetime formats to try
        formats = [
            "%Y-%m-%d",  # 2024-03-21
            "%Y-%m-%dT%H:%M:%S",  # 2024-03-21T15:30:00
            "%Y-%m-%dT%H:%M:%S%z",  # 2024-03-21T15:30:00+0000
            "%Y-%m-%d %H:%M:%S",  # 2024-03-21 15:30:00
            "%d/%m/%Y",  # 21/03/2024
            "%Y/%m/%d",  # 2024/03/21
        ]

        for fmt in formats:
            try:
                # Parse the date string
                date_obj = datetime.strptime(timestamp_str, fmt).astimezone()

                # If the parsed date has no timezone info, assume UTC
                if date_obj.tzinfo is None:
                    date_obj = date_obj.replace(tzinfo=timezone.utc)

                # Convert to UTC and format
                return date_obj.astimezone(timezone.utc)

            except ValueError:
                continue

        msg = f"Could not parse date: {timestamp_str}"
        logger.error(msg)
        raise ValueError(msg)

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
                field_name = filter_setting["attribute_name"] if filter_setting["attribute_name"] else key
                filter_key = field_name if not filter_setting["metadata"] else f"metadata.{field_name}"
                if filter_setting["operator"] == "$exists":
                    filters[filter_key] = {**filters.get(filter_key, {}), filter_setting["operator"]: True}
                elif filter_setting["operator"] in ["$in", "$nin", "$all"]:
                    filters[filter_key] = {
                        **filters.get(filter_key, {}),
                        filter_setting["operator"]: value.split(",") if isinstance(value, str) else value,
                    }
                elif filter_setting["is_timestamp"] == True:  # noqa: E712
                    try:
                        filters[filter_key] = {
                            **filters.get(filter_key, {}),
                            filter_setting["operator"]: self.parse_timestamp(value),
                        }
                    except ValueError as e:
                        msg = f"Error parsing timestamp: {e} - Use the prompt to specify the date in the correct format"
                        logger.error(msg)
                        raise ValueError(msg) from e
                else:
                    filters[filter_key] = {**filters.get(filter_key, {}), filter_setting["operator"]: value}
        return filters

    def run_model(self, **args) -> Data | list[Data]:
        """Run the query to get the data from the AstraDB collection."""
        collection = self._build_collection()
        sort = {}

        # Build filters using the new method
        filters = self.build_filter(args, self.tools_params_v2)

        # Build the vector search on
        if self.use_search_query and args["search_query"] is not None and args["search_query"] != "":
            if self.use_vectorize:
                sort["$vectorize"] = args["search_query"]
            else:
                if self.embedding is None:
                    msg = "Embedding model is not set. Please set the embedding model or use Astra DB Vectorize."
                    logger.error(msg)
                    raise ValueError(msg)
                embedding_query = self.embedding.embed_query(args["search_query"])
                sort["$vector"] = embedding_query
            del args["search_query"]

        find_options = {
            "filter": filters,
            "limit": self.number_of_results,
            "sort": sort,
        }

        projection = self.projection_args(self.projection_attributes)
        if projection and len(projection) > 0:
            find_options["projection"] = projection

        try:
            results = collection.find(**find_options)
        except Exception as e:
            msg = f"Error on Astra DB Tool {self.tool_name} request: {e}"
            logger.error(msg)
            raise ValueError(msg) from e

        logger.info(f"Tool {self.tool_name} executed`")

        data: list[Data] = [Data(data=doc) for doc in results]
        self.status = data
        return data
