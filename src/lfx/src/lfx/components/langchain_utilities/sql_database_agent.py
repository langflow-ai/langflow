"""Modern SQL agent built on `langchain.agents.create_agent`.

Replaces the legacy `SQLAgentComponent` (`sql.py`) which depended on
`langchain_classic.AgentExecutor` and `langchain_community.create_sql_agent`.

The toolkit (`SQLDatabaseToolkit`) and the prompt prefix (`SQL_PREFIX`) are
preserved; only the agent factory changes.
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.agent_toolkits.sql.prompt import SQL_PREFIX
from langchain_community.utilities import SQLDatabase
from langchain_core.runnables import Runnable

from lfx.base.agents.agent import LCAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, handle_model_input_update
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.inputs.inputs import DropdownInput, HandleInput, MessageTextInput, ModelInput
from lfx.io import Output, SecretStrInput, StrInput

# Default top_k mirrors langchain_classic.create_sql_agent's default.
_DEFAULT_TOP_K = 10


class SQLDatabaseAgentComponent(LCAgentComponent):
    # display_name matches the legacy SQLAgentComponent so users see the same
    # label in the sidebar and in flows after the swap. Internal `name` is
    # different to avoid a collision in the components dict.
    display_name = "SQLAgent"
    description = "Construct an SQL agent from an LLM and tools (LangGraph create_agent)."
    name = "SQLDatabaseAgent"
    icon = "LangChain"
    documentation: str = "https://python.langchain.com/docs/integrations/toolkits/sql_database/"

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
        MessageTextInput(name="database_uri", display_name="Database URI", required=True),
        HandleInput(
            name="extra_tools",
            display_name="Extra Tools",
            input_types=["Tool"],
            is_list=True,
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="Response", name="response", method="message_response"),
        Output(display_name="Agent", name="agent", method="build_agent", tool_mode=False),
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

    def _build_system_prompt(self, db: SQLDatabase) -> str:
        return SQL_PREFIX.format(dialect=db.dialect, top_k=_DEFAULT_TOP_K)

    def build_agent(self) -> Runnable:
        llm = self._get_llm()
        db = SQLDatabase.from_uri(self.database_uri)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools = list(toolkit.get_tools()) + list(self.extra_tools or [])

        middleware = []
        max_iterations = getattr(self, "max_iterations", None)
        if max_iterations:
            middleware.append(ModelCallLimitMiddleware(run_limit=int(max_iterations)))
        if getattr(self, "handle_parsing_errors", False):
            middleware.append(ToolRetryMiddleware(max_retries=2))

        return create_agent(
            model=llm,
            tools=tools,
            system_prompt=self._build_system_prompt(db),
            middleware=middleware or None,
        )
