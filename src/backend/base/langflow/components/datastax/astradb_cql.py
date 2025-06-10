import json
import urllib
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import requests
from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, Field, create_model

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.io import DictInput, IntInput, SecretStrInput, StrInput, TableInput
from langflow.logging import logger
from langflow.schema.data import Data
from langflow.schema.table import EditMode


class AstraDBCQLToolComponent(LCToolComponent):
    display_name: str = "Astra DB CQL"
    description: str = "Create a tool to get transactional data from DataStax Astra DB CQL Table"
    documentation: str = "https://docs.langflow.org/Components/components-tools#astra-db-cql-tool"
    icon: str = "AstraDB"

    inputs = [
        StrInput(name="tool_name", display_name="Tool Name", info="The name of the tool.", required=True),
        StrInput(
            name="tool_description",
            display_name="Tool Description",
            info="The tool description to be passed to the model.",
            required=True,
        ),
        StrInput(
            name="keyspace",
            display_name="Keyspace",
            value="default_keyspace",
            info="The keyspace name within Astra DB where the data is stored.",
            required=True,
            advanced=True,
        ),
        StrInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table within Astra DB where the data is stored.",
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
            name="projection_fields",
            display_name="Projection fields",
            info="Attributes to return separated by comma.",
            required=True,
            value="*",
            advanced=True,
        ),
        TableInput(
            name="tools_params",
            display_name="Tools Parameters",
            info="Define the structure for the tool parameters. Describe the parameters "
            "in a way the LLM can understand how to use them. Add the parameters "
            "respecting the table schema (Partition Keys, Clustering Keys and Indexed Fields).",
            required=False,
            table_schema=[
                {
                    "name": "name",
                    "display_name": "Name",
                    "type": "str",
                    "description": "Name of the field/parameter to be used by the model.",
                    "default": "field",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "field_name",
                    "display_name": "Field Name",
                    "type": "str",
                    "description": "Specify the column name to be filtered on the table. "
                    "Leave empty if the attribute name is the same as the name of the field.",
                    "default": "",
                    "edit_mode": EditMode.INLINE,
                },
                {
                    "name": "description",
                    "display_name": "Description",
                    "type": "str",
                    "description": "Describe the purpose of the parameter.",
                    "default": "description of tool parameter",
                    "edit_mode": EditMode.POPOVER,
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
            name="partition_keys",
            display_name="DEPRECATED: Partition Keys",
            is_list=True,
            info="Field name and description to the model",
            required=False,
            advanced=True,
        ),
        DictInput(
            name="clustering_keys",
            display_name="DEPRECATED: Clustering Keys",
            is_list=True,
            info="Field name and description to the model",
            required=False,
            advanced=True,
        ),
        DictInput(
            name="static_filters",
            display_name="Static Filters",
            is_list=True,
            advanced=True,
            info="Field name and value. When filled, it will not be generated by the LLM.",
        ),
        IntInput(
            name="number_of_results",
            display_name="Number of Results",
            info="Number of results to return.",
            advanced=True,
            value=5,
        ),
    ]

    def parse_timestamp(self, timestamp_str: str) -> str:
        """Parse a timestamp string into Astra DB REST API format.

        Args:
            timestamp_str (str): Input timestamp string

        Returns:
            str: Formatted timestamp string in YYYY-MM-DDTHH:MI:SS.000Z format

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
                utc_date = date_obj.astimezone(timezone.utc)
                return utc_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except ValueError:
                continue

        msg = f"Could not parse date: {timestamp_str}"
        logger.error(msg)
        raise ValueError(msg)

    def astra_rest(self, args):
        headers = {"Accept": "application/json", "X-Cassandra-Token": f"{self.token}"}
        astra_url = f"{self.api_endpoint}/api/rest/v2/keyspaces/{self.keyspace}/{self.table_name}/"
        where = {}

        for param in self.tools_params:
            field_name = param["field_name"] if param["field_name"] else param["name"]
            field_value = None

            if field_name in self.static_filters:
                field_value = self.static_filters[field_name]
            elif param["name"] in args:
                field_value = args[param["name"]]

            if field_value is None:
                continue

            if param["is_timestamp"] == True:  # noqa: E712
                try:
                    field_value = self.parse_timestamp(field_value)
                except ValueError as e:
                    msg = f"Error parsing timestamp: {e} - Use the prompt to specify the date in the correct format"
                    logger.error(msg)
                    raise ValueError(msg) from e

            if param["operator"] == "$exists":
                where[field_name] = {**where.get(field_name, {}), param["operator"]: True}
            elif param["operator"] in ["$in", "$nin", "$all"]:
                where[field_name] = {
                    **where.get(field_name, {}),
                    param["operator"]: field_value.split(",") if isinstance(field_value, str) else field_value,
                }
            else:
                where[field_name] = {**where.get(field_name, {}), param["operator"]: field_value}

        url = f"{astra_url}?page-size={self.number_of_results}"
        url += f"&where={json.dumps(where)}"

        if self.projection_fields != "*":
            url += f"&fields={urllib.parse.quote(self.projection_fields.replace(' ', ''))}"

        res = requests.request("GET", url=url, headers=headers, timeout=10)

        if int(res.status_code) >= HTTPStatus.BAD_REQUEST:
            msg = f"Error on Astra DB CQL Tool {self.tool_name} request: {res.text}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            res_data = res.json()
            return res_data["data"]
        except ValueError:
            return res.status_code

    def create_args_schema(self) -> dict[str, BaseModel]:
        args: dict[str, tuple[Any, Field]] = {}

        for param in self.tools_params:
            field_name = param["field_name"] if param["field_name"] else param["name"]
            if field_name not in self.static_filters:
                if param["mandatory"]:
                    args[param["name"]] = (str, Field(description=param["description"]))
                else:
                    args[param["name"]] = (str | None, Field(description=param["description"], default=None))

        model = create_model("ToolInput", **args, __base__=BaseModel)
        return {"ToolInput": model}

    def build_tool(self) -> Tool:
        """Builds a Astra DB CQL Table tool.

        Args:
            name (str, optional): The name of the tool.

        Returns:
            Tool: The built AstraDB tool.
        """
        schema_dict = self.create_args_schema()
        return StructuredTool.from_function(
            name=self.tool_name,
            args_schema=schema_dict["ToolInput"],
            description=self.tool_description,
            func=self.run_model,
            return_direct=False,
        )

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
        results = self.astra_rest(args)
        data: list[Data] = []

        if isinstance(results, list):
            data = [Data(data=doc) for doc in results]
        else:
            self.status = results
            return []

        self.status = data
        return data
