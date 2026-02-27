from langchain.agents import create_xml_agent
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, PromptTemplate

from lfx.base.agents.agent import LCToolsAgentComponent
from lfx.base.models.unified_models import get_language_model_options, get_llm, update_model_options_in_build_config
from lfx.base.models.watsonx_constants import IBM_WATSONX_URLS
from lfx.inputs.inputs import (
    DataInput,
    DropdownInput,
    ModelInput,
    MultilineInput,
    SecretStrInput,
    StrInput,
)
from lfx.schema.data import Data


class XMLAgentComponent(LCToolsAgentComponent):
    display_name: str = "XML Agent"
    description: str = "Agent that uses tools formatting instructions as xml to the Language Model."
    icon = "LangChain"
    beta = True
    name = "XMLAgent"
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
        DataInput(name="chat_history", display_name="Chat History", is_list=True, advanced=True),
        MultilineInput(
            name="system_prompt",
            display_name="System Prompt",
            info="System prompt for the agent.",
            value="""You are a helpful assistant. Help the user answer any questions.

You have access to the following tools:

{tools}

In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>

For example, if you have a tool called 'search' that could run a google search, in order to search for the weather in SF you would respond:

<tool>search</tool><tool_input>weather in SF</tool_input>

<observation>64 degrees</observation>

When you are done, respond with a final answer between <final_answer></final_answer>. For example:

<final_answer>The weather in SF is 64 degrees</final_answer>

Begin!

Question: {input}

{agent_scratchpad}
            """,  # noqa: E501
        ),
        MultilineInput(
            name="user_prompt", display_name="Prompt", info="This prompt must contain 'input' key.", value="{input}"
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

        # Show/hide watsonx fields based on selected model
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

    def get_chat_history_data(self) -> list[Data] | None:
        return self.chat_history

    def create_agent_runnable(self):
        if "input" not in self.user_prompt:
            msg = "Prompt must contain 'input' key."
            raise ValueError(msg)
        llm = self._get_llm()
        messages = [
            ("system", self.system_prompt),
            ("placeholder", "{chat_history}"),
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=self.user_prompt)),
            ("ai", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        return create_xml_agent(llm, self.tools, prompt)
