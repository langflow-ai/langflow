from typing import Any, List, Optional, cast

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.prompts.chat import HumanMessagePromptTemplate, SystemMessagePromptTemplate

from langflow.base.agents.agent import LCAgentComponent
from langflow.base.agents.utils import AGENTS, AgentSpec, get_agents_list
from langflow.field_typing import BaseLanguageModel, Text, Tool
from langflow.schema.dotdict import dotdict
from langflow.schema.schema import Record


class AgentComponent(LCAgentComponent):
    display_name = "Agent"
    description = "Run any LangChain agent using a simplified interface."
    field_order = [
        "agent_name",
        "llm",
        "tools",
        "prompt",
        "tool_template",
        "handle_parsing_errors",
        "memory",
        "input_value",
    ]

    def build_config(self):
        return {
            "agent_name": {
                "display_name": "Agent",
                "info": "The agent to use.",
                "refresh_button": True,
                "real_time_refresh": True,
                "options": get_agents_list(),
            },
            "llm": {"display_name": "LLM"},
            "tools": {"display_name": "Tools"},
            "user_prompt": {
                "display_name": "Prompt",
                "multiline": True,
                "info": "This prompt must contain 'tools' and 'agent_scratchpad' keys.",
            },
            "system_message": {
                "display_name": "System Message",
                "info": "System message to be passed to the LLM.",
                "advanced": True,
            },
            "tool_template": {
                "display_name": "Tool Template",
                "info": "Template for rendering tools in the prompt. Tools have 'name' and 'description' keys.",
                "advanced": True,
            },
            "handle_parsing_errors": {
                "display_name": "Handle Parsing Errors",
                "info": "If True, the agent will handle parsing errors. If False, the agent will raise an error.",
                "advanced": True,
            },
            "message_history": {
                "display_name": "Message History",
                "info": "Message history to pass to the agent.",
            },
            "input_value": {
                "display_name": "Input",
                "info": "Input text to pass to the agent.",
            },
            "langchain_hub_api_key": {
                "display_name": "LangChain Hub API Key",
                "info": "API key to use for LangChain Hub. If provided, prompts will be fetched from LangChain Hub.",
                "advanced": True,
            },
        }

    def get_system_and_user_message_from_prompt(self, prompt: Any):
        """
        Extracts the system message and user prompt from a given prompt object.

        Args:
            prompt (Any): The prompt object from which to extract the system message and user prompt.

        Returns:
            Tuple[Optional[str], Optional[str]]: A tuple containing the system message and user prompt.
                If the prompt object does not have any messages, both values will be None.
        """
        if hasattr(prompt, "messages"):
            system_message = None
            user_prompt = None
            for message in prompt.messages:
                if isinstance(message, SystemMessagePromptTemplate):
                    s_prompt = message.prompt
                    if isinstance(s_prompt, list):
                        s_template = " ".join([cast(str, s.template) for s in s_prompt if hasattr(s, "template")])
                    elif hasattr(s_prompt, "template"):
                        s_template = s_prompt.template
                    system_message = s_template
                elif isinstance(message, HumanMessagePromptTemplate):
                    h_prompt = message.prompt
                    if isinstance(h_prompt, list):
                        h_template = " ".join([cast(str, h.template) for h in h_prompt if hasattr(h, "template")])
                    elif hasattr(h_prompt, "template"):
                        h_template = h_prompt.template
                    user_prompt = h_template
            return system_message, user_prompt
        return None, None

    def update_build_config(self, build_config: dotdict, field_value: Any, field_name: Text | None = None):
        """
        Updates the build configuration based on the provided field value and field name.

        Args:
            build_config (dotdict): The build configuration to be updated.
            field_value (Any): The value of the field being updated.
            field_name (Text | None, optional): The name of the field being updated. Defaults to None.

        Returns:
            dotdict: The updated build configuration.
        """
        if field_name == "agent":
            build_config["agent"]["options"] = get_agents_list()
            if field_value in AGENTS:
                # if langchain_hub_api_key is provided, fetch the prompt from LangChain Hub
                if build_config["langchain_hub_api_key"]["value"] and AGENTS[field_value].hub_repo:
                    from langchain import hub

                    hub_repo: str | None = AGENTS[field_value].hub_repo
                    if hub_repo:
                        hub_api_key: str = build_config["langchain_hub_api_key"]["value"]
                        prompt = hub.pull(hub_repo, api_key=hub_api_key)
                        system_message, user_prompt = self.get_system_and_user_message_from_prompt(prompt)
                        if system_message:
                            build_config["system_message"]["value"] = system_message
                        if user_prompt:
                            build_config["user_prompt"]["value"] = user_prompt

                if AGENTS[field_value].prompt:
                    build_config["user_prompt"]["value"] = AGENTS[field_value].prompt
                else:
                    build_config["user_prompt"]["value"] = "{input}"
            fields = AGENTS[field_value].fields
            for field in ["llm", "tools", "prompt", "tools_renderer"]:
                if field not in fields:
                    build_config[field]["show"] = False
        return build_config

    async def build(
        self,
        agent_name: str,
        input_value: str,
        llm: BaseLanguageModel,
        tools: List[Tool],
        system_message: str = "You are a helpful assistant. Help the user answer any questions.",
        user_prompt: str = "{input}",
        message_history: Optional[List[Record]] = None,
        tool_template: str = "{name}: {description}",
        handle_parsing_errors: bool = True,
    ) -> Text:
        agent_spec: Optional[AgentSpec] = AGENTS.get(agent_name)
        if agent_spec is None:
            raise ValueError(f"{agent_name} not found.")

        def render_tool_description(tools):
            return "\n".join(
                [tool_template.format(name=tool.name, description=tool.description, args=tool.args) for tool in tools]
            )

        messages = [
            ("system", system_message),
            (
                "placeholder",
                "{chat_history}",
            ),
            ("human", user_prompt),
            ("placeholder", "{agent_scratchpad}"),
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        agent_func = agent_spec.func
        agent = agent_func(llm, tools, prompt, render_tool_description, True)
        result = await self.run_agent(
            agent=agent,
            inputs=input_value,
            tools=tools,
            message_history=message_history,
            handle_parsing_errors=handle_parsing_errors,
        )
        self.status = result
        return result
