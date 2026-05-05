"""Modern OpenAPI agent built on `langchain.agents.create_agent`.

Replaces the legacy `OpenAPIAgentComponent` (`openapi.py`) which depended on
`langchain_classic.AgentExecutor` and `langchain_community.create_openapi_agent`.
"""

from pathlib import Path

import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware
from langchain_community.agent_toolkits.openapi.prompt import OPENAPI_PREFIX
from langchain_community.agent_toolkits.openapi.toolkit import OpenAPIToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain_core.runnables import Runnable

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, handle_model_input_update
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.inputs.inputs import BoolInput, DropdownInput, FileInput, ModelInput, SecretStrInput, StrInput


class OpenAPISpecAgentComponent(LCAgentComponent):
    # display_name matches the legacy OpenAPIAgentComponent so users see the
    # same label in the sidebar and in flows after the swap. Internal `name`
    # is different to avoid a collision in the components dict.
    display_name = "OpenAPI Agent"
    description = "Agent to interact with OpenAPI API (LangGraph create_agent)."
    name = "OpenAPISpecAgent"
    icon = "LangChain"
    documentation: str = "https://python.langchain.com/docs/integrations/toolkits/openapi/"

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
            info="Overrides global provider settings. Leave blank to use your pre-configured API Key.",
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
        return get_llm(
            model=self.model,
            user_id=self.user_id,
            api_key=getattr(self, "api_key", None),
            watsonx_url=getattr(self, "base_url_ibm_watsonx", None),
            watsonx_project_id=getattr(self, "project_id", None),
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        return handle_model_input_update(
            self,
            dict(build_config),
            field_value,
            field_name,
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=lambda user_id=None: get_language_model_options(user_id=user_id, tool_calling=True),
        )

    def build_agent(self) -> Runnable:
        llm = self._get_llm()
        path = Path(self.path)
        if path.suffix in {".yaml", ".yml"}:
            with path.open(encoding="utf-8") as file:
                yaml_dict = yaml.safe_load(file)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(str(path))
        requests_wrapper = TextRequestsWrapper()
        toolkit = OpenAPIToolkit.from_llm(
            llm=llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            allow_dangerous_requests=self.allow_dangerous_requests,
        )
        tools = list(toolkit.get_tools())

        middleware = []
        max_iterations = getattr(self, "max_iterations", None)
        if max_iterations:
            middleware.append(ModelCallLimitMiddleware(run_limit=int(max_iterations)))
        if getattr(self, "handle_parsing_errors", False):
            middleware.append(ToolRetryMiddleware(max_retries=2))

        return create_agent(
            model=llm,
            tools=tools,
            system_prompt=OPENAPI_PREFIX,
            middleware=middleware or None,
        )
