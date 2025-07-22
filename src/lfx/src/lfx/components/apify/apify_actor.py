import json
import string
from typing import Any, cast

from apify_client import ApifyClient
from langchain_community.document_loaders.apify_dataset import ApifyDatasetLoader
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, field_serializer

from lfx.custom.custom_component.component import Component
from lfx.field_typing import Tool
from lfx.inputs.inputs import BoolInput
from lfx.io import MultilineInput, Output, SecretStrInput, StrInput
from lfx.schema.data import Data

MAX_DESCRIPTION_LEN = 250


class ApifyActorsComponent(Component):
    display_name = "Apify Actors"
    description = (
        "Use Apify Actors to extract data from hundreds of places fast. "
        "This component can be used in a flow to retrieve data or as a tool with an agent."
    )
    documentation: str = "http://docs.langflow.org/integrations-apify"
    icon = "Apify"
    name = "ApifyActors"

    inputs = [
        SecretStrInput(
            name="apify_token",
            display_name="Apify Token",
            info="The API token for the Apify account.",
            required=True,
            password=True,
        ),
        StrInput(
            name="actor_id",
            display_name="Actor",
            info=(
                "Actor name from Apify store to run. For example 'apify/website-content-crawler' "
                "to use the Website Content Crawler Actor."
            ),
            value="apify/website-content-crawler",
            required=True,
        ),
        # multiline input is more pleasant to use than the nested dict input
        MultilineInput(
            name="run_input",
            display_name="Run input",
            info=(
                'The JSON input for the Actor run. For example for the "apify/website-content-crawler" Actor: '
                '{"startUrls":[{"url":"https://docs.apify.com/academy/web-scraping-for-beginners"}],"maxCrawlDepth":0}'
            ),
            value='{"startUrls":[{"url":"https://docs.apify.com/academy/web-scraping-for-beginners"}],"maxCrawlDepth":0}',
            required=True,
        ),
        MultilineInput(
            name="dataset_fields",
            display_name="Output fields",
            info=(
                "Fields to extract from the dataset, split by commas. "
                "Other fields will be ignored. Dots in nested structures will be replaced by underscores. "
                "Sample input: 'text, metadata.title'. "
                "Sample output: {'text': 'page content here', 'metadata_title': 'page title here'}. "
                "For example, for the 'apify/website-content-crawler' Actor, you can extract the 'markdown' field, "
                "which is the content of the website in markdown format."
            ),
        ),
        BoolInput(
            name="flatten_dataset",
            display_name="Flatten output",
            info=(
                "The output dataset will be converted from a nested format to a flat structure. "
                "Dots in nested structure will be replaced by underscores. "
                "This is useful for further processing of the Data object. "
                "For example, {'a': {'b': 1}} will be flattened to {'a_b': 1}."
            ),
        ),
    ]

    outputs = [
        Output(display_name="Output", name="output", type_=list[Data], method="run_model"),
        Output(display_name="Tool", name="tool", type_=Tool, method="build_tool"),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._apify_client: ApifyClient | None = None

    def run_model(self) -> list[Data]:
        """Run the Actor and return node output."""
        input_ = json.loads(self.run_input)
        fields = ApifyActorsComponent.parse_dataset_fields(self.dataset_fields) if self.dataset_fields else None
        res = self._run_actor(self.actor_id, input_, fields=fields)
        if self.flatten_dataset:
            res = [ApifyActorsComponent.flatten(item) for item in res]
        data = [Data(data=item) for item in res]

        self.status = data
        return data

    def build_tool(self) -> Tool:
        """Build a tool for an agent that runs the Apify Actor."""
        actor_id = self.actor_id

        build = self._get_actor_latest_build(actor_id)
        readme = build.get("readme", "")[:250] + "..."
        if not (input_schema_str := build.get("inputSchema")):
            msg = "Input schema not found"
            raise ValueError(msg)
        input_schema = json.loads(input_schema_str)
        properties, required = ApifyActorsComponent.get_actor_input_schema_from_build(input_schema)
        properties = {"run_input": properties}

        # works from input schema
        info_ = [
            (
                "JSON encoded as a string with input schema (STRICTLY FOLLOW JSON FORMAT AND SCHEMA):\n\n"
                f"{json.dumps(properties, separators=(',', ':'))}"
            )
        ]
        if required:
            info_.append("\n\nRequired fields:\n" + "\n".join(required))

        info = "".join(info_)

        input_model_cls = ApifyActorsComponent.create_input_model_class(info)
        tool_cls = ApifyActorsComponent.create_tool_class(self, readme, input_model_cls, actor_id)

        return cast("Tool", tool_cls())

    @staticmethod
    def create_tool_class(
        parent: "ApifyActorsComponent", readme: str, input_model: type[BaseModel], actor_id: str
    ) -> type[BaseTool]:
        """Create a tool class that runs an Apify Actor."""

        class ApifyActorRun(BaseTool):
            """Tool that runs Apify Actors."""

            name: str = f"apify_actor_{ApifyActorsComponent.actor_id_to_tool_name(actor_id)}"
            description: str = (
                "Run an Apify Actor with the given input. "
                "Here is a part of the currently loaded Actor README:\n\n"
                f"{readme}\n\n"
            )

            args_schema: type[BaseModel] = input_model

            @field_serializer("args_schema")
            def serialize_args_schema(self, args_schema):
                return args_schema.schema()

            def _run(self, run_input: str | dict) -> str:
                """Use the Apify Actor."""
                input_dict = json.loads(run_input) if isinstance(run_input, str) else run_input

                # retrieve if nested, just in case
                input_dict = input_dict.get("run_input", input_dict)

                res = parent._run_actor(actor_id, input_dict)
                return "\n\n".join([ApifyActorsComponent.dict_to_json_str(item) for item in res])

        return ApifyActorRun

    @staticmethod
    def create_input_model_class(description: str) -> type[BaseModel]:
        """Create a Pydantic model class for the Actor input."""

        class ActorInput(BaseModel):
            """Input for the Apify Actor tool."""

            run_input: str = Field(..., description=description)

        return ActorInput

    def _get_apify_client(self) -> ApifyClient:
        """Get the Apify client.

        Is created if not exists or token changes.
        """
        if not self.apify_token:
            msg = "API token is required."
            raise ValueError(msg)
        # when token changes, create a new client
        if self._apify_client is None or self._apify_client.token != self.apify_token:
            self._apify_client = ApifyClient(self.apify_token)
            if httpx_client := self._apify_client.http_client.httpx_client:
                httpx_client.headers["user-agent"] += "; Origin/langflow"
        return self._apify_client

    def _get_actor_latest_build(self, actor_id: str) -> dict:
        """Get the latest build of an Actor from the default build tag."""
        client = self._get_apify_client()
        actor = client.actor(actor_id=actor_id)
        if not (actor_info := actor.get()):
            msg = f"Actor {actor_id} not found."
            raise ValueError(msg)

        default_build_tag = actor_info.get("defaultRunOptions", {}).get("build")
        latest_build_id = actor_info.get("taggedBuilds", {}).get(default_build_tag, {}).get("buildId")

        if (build := client.build(latest_build_id).get()) is None:
            msg = f"Build {latest_build_id} not found."
            raise ValueError(msg)

        return build

    @staticmethod
    def get_actor_input_schema_from_build(input_schema: dict) -> tuple[dict, list[str]]:
        """Get the input schema from the Actor build.

        Trim the description to 250 characters.
        """
        properties = input_schema.get("properties", {})
        required = input_schema.get("required", [])

        properties_out: dict = {}
        for item, meta in properties.items():
            properties_out[item] = {}
            if desc := meta.get("description"):
                properties_out[item]["description"] = (
                    desc[:MAX_DESCRIPTION_LEN] + "..." if len(desc) > MAX_DESCRIPTION_LEN else desc
                )
            for key_name in ("type", "default", "prefill", "enum"):
                if value := meta.get(key_name):
                    properties_out[item][key_name] = value

        return properties_out, required

    def _get_run_dataset_id(self, run_id: str) -> str:
        """Get the dataset id from the run id."""
        client = self._get_apify_client()
        run = client.run(run_id=run_id)
        if (dataset := run.dataset().get()) is None:
            msg = "Dataset not found"
            raise ValueError(msg)
        if (did := dataset.get("id")) is None:
            msg = "Dataset id not found"
            raise ValueError(msg)
        return did

    @staticmethod
    def dict_to_json_str(d: dict) -> str:
        """Convert a dictionary to a JSON string."""
        return json.dumps(d, separators=(",", ":"), default=lambda _: "<n/a>")

    @staticmethod
    def actor_id_to_tool_name(actor_id: str) -> str:
        """Turn actor_id into a valid tool name.

        Tool name must only contain letters, numbers, underscores, dashes,
            and cannot contain spaces.
        """
        valid_chars = string.ascii_letters + string.digits + "_-"
        return "".join(char if char in valid_chars else "_" for char in actor_id)

    def _run_actor(self, actor_id: str, run_input: dict, fields: list[str] | None = None) -> list[dict]:
        """Run an Apify Actor and return the output dataset.

        Args:
            actor_id: Actor name from Apify store to run.
            run_input: JSON input for the Actor.
            fields: List of fields to extract from the dataset. Other fields will be ignored.
        """
        client = self._get_apify_client()
        if (details := client.actor(actor_id=actor_id).call(run_input=run_input, wait_secs=1)) is None:
            msg = "Actor run details not found"
            raise ValueError(msg)
        if (run_id := details.get("id")) is None:
            msg = "Run id not found"
            raise ValueError(msg)

        if (run_client := client.run(run_id)) is None:
            msg = "Run client not found"
            raise ValueError(msg)

        # stream logs
        with run_client.log().stream() as response:
            if response:
                for line in response.iter_lines():
                    self.log(line)
        run_client.wait_for_finish()

        dataset_id = self._get_run_dataset_id(run_id)

        loader = ApifyDatasetLoader(
            dataset_id=dataset_id,
            dataset_mapping_function=lambda item: item
            if not fields
            else {k.replace(".", "_"): ApifyActorsComponent.get_nested_value(item, k) for k in fields},
        )
        return loader.load()

    @staticmethod
    def get_nested_value(data: dict[str, Any], key: str) -> Any:
        """Get a nested value from a dictionary."""
        keys = key.split(".")
        value = data
        for k in keys:
            if not isinstance(value, dict) or k not in value:
                return None
            value = value[k]
        return value

    @staticmethod
    def parse_dataset_fields(dataset_fields: str) -> list[str]:
        """Convert a string of comma-separated fields into a list of fields."""
        dataset_fields = dataset_fields.replace("'", "").replace('"', "").replace("`", "")
        return [field.strip() for field in dataset_fields.split(",")]

    @staticmethod
    def flatten(d: dict) -> dict:
        """Flatten a nested dictionary."""

        def items():
            for key, value in d.items():
                if isinstance(value, dict):
                    for subkey, subvalue in ApifyActorsComponent.flatten(value).items():
                        yield key + "_" + subkey, subvalue
                else:
                    yield key, value

        return dict(items())
