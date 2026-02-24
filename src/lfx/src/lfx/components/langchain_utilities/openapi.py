from pathlib import Path

import yaml
from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits import create_openapi_agent
from langchain_community.agent_toolkits.openapi.toolkit import OpenAPIToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.inputs.inputs import BoolInput, DropdownInput, FileInput, ModelInput, SecretStrInput, StrInput


class OpenAPIAgentComponent(LCAgentComponent):
    display_name = "OpenAPI Agent"
    description = "Agent to interact with OpenAPI API."
    name = "OpenAPIAgent"
    icon = "LangChain"
    inputs = [
        *LCAgentComponent.get_base_inputs(),
        ModelInput(
            name="model",
            display_name="Language Model",
            info="Select your model provider or connect a Language Model component.",
            real_time_refresh=True,
            required=True,
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="Model Provider API key",
            real_time_refresh=True,
            advanced=True,
        ),
        DropdownInput(
            name="base_url_ibm_watsonx",
            display_name="watsonx API Endpoint",
            info="The base URL of the API (IBM watsonx.ai only)",
            options=IBM_WATSONX_URLS,
            value=IBM_WATSONX_URLS[0],
            show=False,
            real_time_refresh=True,
        ),
        StrInput(
            name="project_id",
            display_name="watsonx Project ID",
            info="The project ID associated with the foundation model (IBM watsonx.ai only)",
            show=False,
            required=False,
        ),
        FileInput(name="path", display_name="File Path", file_types=["json", "yaml", "yml"], required=True),
        BoolInput(name="allow_dangerous_requests", display_name="Allow Dangerous Requests", value=False, required=True),
    ]

    def _get_llm(self):
        """Resolve the language model from dropdown selection or connected component."""
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=getattr(self, "api_key", None),
            watsonx_url=getattr(self, "base_url_ibm_watsonx", None),
            watsonx_project_id=getattr(self, "project_id", None),
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Dynamically update build config with user-filtered model options (tool-calling capable models)."""

        def get_tool_calling_model_options(user_id=None):
            return get_language_model_options(user_id=user_id, tool_calling=True)

        build_config = update_model_options_in_build_config(
            component=self,
            build_config=dict(build_config),
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=get_tool_calling_model_options,
            field_name=field_name,
            field_value=field_value,
        )
        current_model_value = field_value if field_name == "model" else build_config.get("model", {}).get("value")
        if isinstance(current_model_value, list) and len(current_model_value) > 0:
            selected_model = current_model_value[0]
            provider = selected_model.get("provider", "")
            is_watsonx = provider == "IBM WatsonX"
            if "base_url_ibm_watsonx" in build_config:
                build_config["base_url_ibm_watsonx"]["show"] = is_watsonx
                build_config["base_url_ibm_watsonx"]["required"] = is_watsonx
            if "project_id" in build_config:
                build_config["project_id"]["show"] = is_watsonx
                build_config["project_id"]["required"] = is_watsonx
        return build_config

    def build_agent(self) -> AgentExecutor:
        llm = self._get_llm()
        path = Path(self.path)
        if path.suffix in {"yaml", "yml"}:
            with path.open(encoding="utf-8") as file:
                yaml_dict = yaml.safe_load(file)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(path)
        requests_wrapper = TextRequestsWrapper()
        toolkit = OpenAPIToolkit.from_llm(
            llm=llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            allow_dangerous_requests=self.allow_dangerous_requests,
        )

        agent_args = self.get_agent_kwargs()

        # This is bit weird - generally other create_*_agent functions have max_iterations in the
        # `agent_executor_kwargs`, but openai has this parameter passed directly.
        agent_args["max_iterations"] = agent_args["agent_executor_kwargs"]["max_iterations"]
        del agent_args["agent_executor_kwargs"]["max_iterations"]
        return create_openapi_agent(llm=llm, toolkit=toolkit, **agent_args)
