import json
import os
import re
import urllib
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Any

import requests
from langchain_core.tools import StructuredTool, Tool
from pydantic import BaseModel, Field, create_model

from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.io import (
    DictInput,
    DropdownInput,
    HandleInput,
    IntInput,
    MultilineInput,
    SecretStrInput,
    StrInput,
    TableInput,
)
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
        MultilineInput(
            name="tool_description",
            display_name="Tool Description",
            info="The tool description to be passed to the model.",
            required=True,
        ),
        DropdownInput(
            name="query_mode",
            display_name="Query Mode",
            info="Runs CQL command or REST API.",
            options=["REST API", "CQL"],
            value="REST API",
            required=True,
            real_time_refresh=True,
        ),
        StrInput(
            name="keyspace",
            display_name="Keyspace",
            value="default_keyspace",
            info="The keyspace name within Astra DB where the data is stored.",
            required=False,
            advanced=True,
        ),
        StrInput(
            name="table_name",
            display_name="Table Name",
            info="The name of the table within Astra DB where the data is stored. "
            "Leave it empty if you want to use a CQL command.",
        ),
        MultilineInput(
            name="cql_command",
            display_name="CQL Command",
            info="CQL command to be executed. Use :<arg_name> to reference the arguments.",
            show=False,
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
                    "name": "datatype",
                    "display_name": "Data Type",
                    "type": "str",
                    "edit_mode": EditMode.INLINE,
                    "description": ("Indicate the data type of the field."),
                    "options": ["string", "number", "boolean", "timestamp", "vector"],
                    "default": "string",
                },
                {
                    "name": "operator",
                    "display_name": "Operator",
                    "type": "str",
                    "description": "Set the operator for the field. "
                    "https://docs.datastax.com/en/astra-db-serverless/api-reference/documents.html#operators",
                    "default": "$eq",
                    "options": ["$gt", "$gte", "$lt", "$lte", "$eq", "$ne", "$in", "$nin"],
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
            name="cql_replaces",
            display_name="CQL Replace Params",
            is_list=True,
            info="Replacements to be applied to the CQL command before execution. (attention to whitespaces)",
            required=False,
            value={" WHERE AND ": " WHERE ", " WHERE OR ": " WHERE ", ", WHERE ": " WHERE "},
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
        HandleInput(name="embedding", display_name="Embedding Model", input_types=["Embeddings"], show=False),
    ]

    async def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update build configuration based on field name and value."""
        if field_name == "query_mode":
            is_cql = field_value == "CQL"
            build_config["cql_command"]["show"] = is_cql
            build_config["embedding"]["show"] = is_cql
            build_config["table_name"]["show"] = not is_cql
            build_config["keyspace"]["show"] = not is_cql
            build_config["projection_fields"]["show"] = not is_cql
            build_config["partition_keys"]["show"] = not is_cql
            build_config["clustering_keys"]["show"] = not is_cql
            build_config["static_filters"]["show"] = not is_cql
        return build_config

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
        headers = {
            "Accept": "application/json",
            "X-Cassandra-Token": f"{self.token}",
            "User-Agent": "langflow-astra-tool-cql",
        }
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

    def astra_cql(self, args):
        headers = {
            "Accept": "application/json",
            "X-Cassandra-Token": f"{self.token}",
            "User-Agent": "langflow-astra-cql-tool",
        }
        astra_url = f"{self.api_endpoint}/api/rest/v2/cql"
        cql = self.cql_command

        # replace all texts starting with : with the value of the argument
        for arg in args:
            if arg == "limit":
                cql = cql.replace(f":{arg}", f"{self.number_of_results!s}")
                continue

            param = next((p for p in self.tools_params if p["name"] == arg), None)
            if param is None:
                continue
            if param["datatype"] == "string" or param["datatype"] == "timestamp":
                cql = cql.replace(f":{arg}", f"'{args[arg]!s}'")
            else:
                cql = cql.replace(f":{arg}", f"{args[arg]!s}")

        # remove all the lines that has some parameter not assigned
        cql_cleaned = ""
        for line in cql.split("\n"):
            if not any(f":{param['name']}" in line for param in self.tools_params):
                cql_cleaned += line + "\n"

        # remove all linebreaks before cleanup
        cql_cleaned = cql_cleaned.replace("\n", " ")

        # remove all multiple spaces
        cql_cleaned = re.sub(r"\s+", " ", cql_cleaned)

        # removes parts of the command that are not needed or get wrong after optional parameters are removed
        for dirty in self.cql_replaces:
            cql_cleaned = cql_cleaned.replace(dirty, self.cql_replaces[dirty])

        logger.debug(f"CQL Command: {cql_cleaned}")

        res = requests.request("POST", url=astra_url, headers=headers, timeout=10, data=cql_cleaned)

        if int(res.status_code) >= HTTPStatus.BAD_REQUEST:
            msg = f"Error on Astra DB CQL Tool {self.tool_name} request: {res.text}"
            logger.error(msg)
            raise ValueError(msg)

        try:
            res_data = res.json()
            return res_data["data"]
        except ValueError as e:
            msg = f"Error on Astra DB CQL Tool {self.tool_name} request: {res.text}"
            logger.error(msg)
            raise ValueError(msg) from e

    def create_args_schema(self) -> dict[str, BaseModel]:
        schema_args: dict[str, tuple[Any, Field]] = {}
        # Map string datatypes to Python types
        type_mapping = {
            "string": str,
            "number": float,
            "boolean": bool,
            "integer": int,
            "timestamp": datetime,
            "list": list,
            "dict": dict,
            "vector": str,  # Vector parameters are passed as strings to the model
        }

        if self.static_filters is None:
            self.static_filters = {}

        if self.tools_params is None:
            self.tools_params = []

        for param in self.tools_params:
            logger.info(f"Param: {param}")
            try:
                logger.info(f"Schema args: {schema_args} {param}")
                datatype = param["datatype"]
                python_type = type_mapping.get(datatype, str)
                if python_type is None:
                    error_msg = f"Unsupported datatype: {datatype}"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
                logger.info(f"Python type: {python_type}")

                field_name = param["field_name"] if param["field_name"] else param["name"]

                if field_name not in self.static_filters:
                    if param["mandatory"]:
                        schema_args[param["name"]] = (python_type, Field(description=param["description"]))
                    else:
                        schema_args[param["name"]] = (
                            python_type | None,
                            Field(description=param["description"], default=None),
                        )
            except Exception as e:
                error_msg = f"Error processing parameter {param}: {e!s}"
                logger.error(error_msg)
                raise ValueError(error_msg) from e

        model = create_model("ToolInput", **schema_args, __base__=BaseModel)
        return {"ToolInput": model}

    def build_tool(self) -> Tool:
        """Builds a Astra DB CQL Table tool.

        Args:
            name (str, optional): The name of the tool.

        Returns:
            Tool: The built AstraDB tool.
        """
        schema_dict = self.create_args_schema()
        logger.info(f"Schema dict: {schema_dict}")
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
        args["limit"] = self.number_of_results or 10

        # Build the vector search argument with the embedding model
        vector_search_param = next((p for p in self.tools_params if p["datatype"] == "vector"), None)
        if vector_search_param is not None and args.get(vector_search_param["name"]) is not None:
            if self.embedding is None:
                msg = "Embedding model is not set. Please set the embedding model."
                logger.error(msg)
                raise ValueError(msg)
            embedding_query = self.embedding.embed_query(args[vector_search_param["name"]])
            args[vector_search_param["name"]] = embedding_query

        results = None
        if self.cql_command:
            logger.debug(f"Running CQL Command {args}")
            results = self.astra_cql(args)
        else:
            logger.debug(f"Running REST Command {args}")
            results = self.astra_rest(args)
        data: list[Data] = []

        if isinstance(results, list):
            data = [Data(data=doc) for doc in results]
        else:
            self.status = results
            return []

        self.status = data
        return data
