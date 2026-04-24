from langchain_classic.agents import create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, handle_model_input_update
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS

# IBM Granite-specific logic is in a separate file
from lfx.components.langchain_utilities.ibm_granite_handler import (
    create_granite_agent,
    get_enhanced_system_prompt,
    is_granite_model,
)
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
        messages = []

        # Use local variable to avoid mutating component state on repeated calls
        effective_system_prompt = self.system_prompt or ""

        llm = self._get_llm()

        # Enhance prompt for IBM Granite models (they need explicit tool usage instructions)
        if is_granite_model(llm) and self.tools:
            effective_system_prompt = get_enhanced_system_prompt(effective_system_prompt, self.tools)
            # Store enhanced prompt for use in agent.py without mutating original
            self._effective_system_prompt = effective_system_prompt

        # Only include system message if system_prompt is provided and not empty
        if effective_system_prompt.strip():
            messages.append(("system", "{system_prompt}"))

        messages.extend(
            [
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        prompt = ChatPromptTemplate.from_messages(messages)
        self.validate_tool_names()

        try:
            # Use IBM Granite-specific agent if detected
            # Other WatsonX models (Llama, Mistral, etc.) use default behavior
            if is_granite_model(llm) and self.tools:
                return create_granite_agent(llm, self.tools, prompt)

            # Default behavior for other models (including non-Granite WatsonX models)
            return create_tool_calling_agent(llm, self.tools or [], prompt)
        except NotImplementedError as e:
            message = f"{self.display_name} does not support tool calling. Please try using a compatible model."
            raise NotImplementedError(message) from e
