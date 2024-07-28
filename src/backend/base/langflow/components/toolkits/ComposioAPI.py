from typing import Union


from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, MultilineInput, MessageTextInput
from langflow.schema import Data
from langchain_core.tools import StructuredTool

from composio_langchain import ComposioToolSet
import typing as t


class ComposioAPIComponent(LCToolComponent):
    display_name: str = "Composio Tools"
    description: str = "Use Composio to run actions or tools with you agent"
    name = "ComposioAPI"
    icon = "Composio"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        MessageTextInput(name="entity_id", display_name="Entity ID", value="default"),
        SecretStrInput(name="api_key", display_name="Composio API Key", required=True),
        MultilineInput(
            name="app_names",
            display_name="App to use",
            required=True,
        ),
        MultilineInput(
            name="action_names",
            display_name="Action to use",
            required=False,
        ),
    ]

    def run_model(self) -> Union[Data, list[Data]]:
        wrapper = self._build_wrapper()
        results = wrapper.results(query=self.input_value, **(self.search_params or {}))
        list_results = results.get("organic_results", [])
        data = [Data(data=result, text=result["snippet"]) for result in list_results]
        self.status = data
        return data

    def build_tool(self) -> t.Sequence[StructuredTool]:
        composio_toolset = self._build_wrapper()
        # apps = self.app_names.split("\n")
        # action_names = self.action_names.split("\n")
        apps = ["github"]
        action_names = self.action_names.split("\n")
        if len(action_names) > 0:
            composio_tools = composio_toolset.get_actions(actions=action_names, entity_id=self.entity_id)
        else:
            composio_tools = composio_toolset.get_tools(apps=apps, entity_id=self.entity_id)

        return composio_tools[0]

    def _build_wrapper(self):
        return ComposioToolSet(api_key=self.api_key)
