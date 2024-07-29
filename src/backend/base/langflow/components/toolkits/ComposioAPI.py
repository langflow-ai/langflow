from typing import Union
from langflow.base.langchain_utilities.model import LCToolComponent
from langflow.inputs import SecretStrInput, MessageTextInput, DropdownInput, StrInput
from langflow.schema import Data
from langchain_core.tools import StructuredTool
from composio_langchain import ComposioToolSet, App, Action
import typing as t


class ComposioAPIComponent(LCToolComponent):
    display_name: str = "Composio Tools"
    description: str = "Use Composio toolset to run actions with your agent"
    name = "ComposioAPI"
    icon = "Composio"
    documentation: str = "https://docs.composio.dev"

    inputs = [
        MessageTextInput(name="entity_id", display_name="Entity ID", value="default", advanced=True),
        SecretStrInput(
            name="api_key",
            display_name="Composio API Key",
            required=True,
            refresh_button=True,
            info="Refer to https://docs.composio.dev/introduction/foundations/howtos/get_api_key",
        ),
        DropdownInput(
            name="app_names",
            display_name="App Name",
            options=[app_name for app_name in App.__annotations__],
            value="",
            info="The app name to use",
            refresh_button=True,
        ),
        DropdownInput(
            name="action_names",
            display_name="Action to use",
            required=False,
            options=[""],
            value="",
            info="The action name to use",
        ),
        StrInput(
            name="auth_status_config",
            display_name="Auth status",
            value="",
            refresh_button=True,
            info="Open link or enter api key. Then refresh button",
        ),
    ]

    def check_for_authorization(self, app):
        toolset = self._build_wrapper()
        entity = toolset.client.get_entity(id=self.entity_id)
        try:
            entity.get_connection(app=app)
            return app + " CONNECTED"
        except Exception:
            return self.handle_authorization_failure(toolset, entity, app)

    def handle_authorization_failure(self, toolset, entity, app):
        try:
            auth_schemes = toolset.client.apps.get(app).auth_schemes
            if auth_schemes[0].auth_mode == "API_KEY":
                return self.process_api_key_auth(entity, app)
            else:
                return self.initiate_default_connection(entity, app)
        except Exception as e:
            print(e)
            return "Error"

    def process_api_key_auth(self, entity, app):
        auth_status_config = self.auth_status_config
        is_url = "http" in auth_status_config or "https" in auth_status_config
        is_different_app = "CONNECTED" in auth_status_config and app not in auth_status_config
        is_api_key_message = "API Key" in auth_status_config

        if is_different_app or is_url or is_api_key_message:
            return "Enter API Key"
        else:
            if not is_api_key_message:
                entity.initiate_connection(
                    app_name=app,
                    auth_mode="API_KEY",
                    auth_config={"api_key": self.auth_status_config},
                    use_composio_auth=False,
                    force_new_integration=True,
                )
                return app + " CONNECTED"
            else:
                return "Enter API Key"

    def initiate_default_connection(self, entity, app):
        connection = entity.initiate_connection(app_name=app, use_composio_auth=True, force_new_integration=True)
        return connection.redirectUrl

    def get_connected_app_names(self):
        toolset = self._build_wrapper()
        connections = toolset.client.get_entity(id=self.entity_id).get_connections()
        return list(set(connection.appUniqueId for connection in connections))

    def update_app_names(self, build_config: dict):
        connected_app_names = self.get_connected_app_names()

        app_names = [
            app_name + "_CONNECTED" for app_name in App.__annotations__ if app_name.lower() in connected_app_names
        ]
        non_connected_app_names = [
            app_name for app_name in App.__annotations__ if app_name.lower() not in connected_app_names
        ]
        build_config["app_names"]["options"] = app_names + non_connected_app_names
        build_config["app_names"]["value"] = app_names[0]
        return build_config

    def get_app_name(self):
        app_name = self.app_names
        return app_name.replace("_CONNECTED", "").replace("_connected", "")

    def update_build_config(self, build_config: dict, field_value: t.Any, field_name: str | None = None):
        if field_name == "api_key":
            build_config = self.update_app_names(build_config)

        if field_name == "app_names" or field_name == "auth_status_config" or field_name == "api_key":
            build_config["auth_status_config"]["value"] = self.check_for_authorization(self.get_app_name())
            all_action_names = [action_name for action_name in Action.__annotations__]
            app_action_names = []
            for action_name in all_action_names:
                if action_name.lower().startswith(self.get_app_name().lower() + "_"):
                    app_action_names.append(action_name)
            build_config["action_names"]["options"] = app_action_names
        return build_config

    def run_model(self) -> Union[Data, list[Data]]:
        wrapper = self._build_wrapper()
        results = wrapper.results(query=self.input_value, **(self.search_params or {}))
        list_results = results.get("organic_results", [])
        data = [Data(data=result, text=result["snippet"]) for result in list_results]
        self.status = data
        return data

    def build_tool(self) -> t.Sequence[StructuredTool]:
        composio_toolset = self._build_wrapper()
        composio_tools = composio_toolset.get_actions(actions=[self.action_names], entity_id=self.entity_id)
        return composio_tools[0]

    def _build_wrapper(self):
        return ComposioToolSet(api_key=self.api_key)
