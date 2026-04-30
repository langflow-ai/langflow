from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolRetryMiddleware

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, handle_model_input_update
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS

# IBM WatsonX-specific behavior is implemented as a middleware (see ibm_granite_middleware.py).
from lfx.components.langchain_utilities.ibm_granite_handler import (
    get_enhanced_system_prompt,
    is_granite_model,
    is_watsonx_model,
)
from lfx.components.langchain_utilities.ibm_granite_middleware import build_watsonx_middleware
from lfx.inputs.inputs import (
    DataInput,
    DropdownInput,
    MessageTextInput,
    ModelInput,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data


class ToolCallingAgentComponent(LCToolsAgentComponent):
    display_name: str = "Tool Calling Agent"
    description: str = "An agent designed to utilize various tools seamlessly within workflows."
    icon = "LangChain"
    name = "ToolCallingAgent"

    inputs = [
        *LCToolsAgentComponent.get_base_inputs(),
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
        MessageTextInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt to guide the agent's behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
        ),
        DataInput(
            name="chat_history",
            display_name="Chat Memory",
            is_list=True,
            advanced=True,
            info="This input stores the chat history, allowing the agent to remember previous conversations.",
        ),
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
        return handle_model_input_update(
            self,
            dict(build_config),
            field_value,
            field_name,
            cache_key_prefix="language_model_options_tool_calling",
            get_options_func=lambda user_id=None: get_language_model_options(user_id=user_id, tool_calling=True),
        )

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        """Build the agent graph using `langchain.agents.create_agent`.

        Returns a `CompiledStateGraph` (LangGraph). The legacy
        `langchain_classic.create_tool_calling_agent` path is removed; WatsonX-specific
        behavior is now applied via middleware so it composes with the rest of the system.
        """
        self.validate_tool_names()

        llm = self._get_llm()
        tools = self.tools or []
        effective_system_prompt = (self.system_prompt or "").strip()

        # WatsonX models still need their tool-usage hints injected directly into the system prompt
        # because some providers behave better when the prompt itself describes how to call tools.
        if is_granite_model(llm) and tools:
            effective_system_prompt = get_enhanced_system_prompt(effective_system_prompt, tools)
            self._effective_system_prompt = effective_system_prompt

        # Eagerly verify tool-calling support to preserve the legacy build-time error contract.
        # `create_agent` itself is lazy — without this check, a model that does not support
        # tool calling would only fail at run-time, surprising users who expect the error
        # at flow build-time.
        try:
            llm.bind_tools(tools)
        except NotImplementedError as e:
            message = f"{self.display_name} does not support tool calling. Please try using a compatible model."
            raise NotImplementedError(message) from e

        middleware = []
        if is_watsonx_model(llm) and tools:
            middleware.append(build_watsonx_middleware(llm=llm, tools=tools))

        max_iterations = getattr(self, "max_iterations", None)
        if max_iterations:
            middleware.append(ModelCallLimitMiddleware(run_limit=int(max_iterations)))

        if getattr(self, "handle_parsing_errors", False):
            # ToolRetryMiddleware retries tool failures with exponential backoff. This is the
            # closest equivalent to AgentExecutor's `handle_parsing_errors=True` (best-effort
            # mapping; semantics are not 1:1 — see CZL/PLAN_create_agent_migration.md §5.1).
            middleware.append(ToolRetryMiddleware(max_retries=2))

        return create_agent(
            model=llm,
            tools=tools,
            system_prompt=effective_system_prompt or None,
            middleware=middleware,
        )
