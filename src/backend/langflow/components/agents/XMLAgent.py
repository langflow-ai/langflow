from typing import List

from langchain.agents import AgentExecutor, create_xml_agent
from langchain_core.prompts import PromptTemplate

from langflow import CustomComponent
from langflow.field_typing import BaseLLM, BaseMemory, Text, Tool


class XMLAgentComponent(CustomComponent):
    display_name = "XMLAgent"
    description = "Construct an XML agent from an LLM and tools."

    def build_config(self):
        return {
            "llm": {"display_name": "LLM"},
            "tools": {"display_name": "Tools"},
            "prompt": {
                "display_name": "Prompt",
                "multiline": True,
                "info": "This prompt must contain 'tools' and 'agent_scratchpad' keys.",
                "value": """You are a helpful assistant. Help the user answer any questions.

            You have access to the following tools:

            {tools}

            In order to use a tool, you can use <tool></tool> and <tool_input></tool_input> tags. You will then get back a response in the form <observation></observation>
            For example, if you have a tool called 'search' that could run a google search, in order to search for the weather in SF you would respond:

            <tool>search</tool><tool_input>weather in SF</tool_input>
            <observation>64 degrees</observation>

            When you are done, respond with a final answer between <final_answer></final_answer>. For example:

            <final_answer>The weather in SF is 64 degrees</final_answer>

            Begin!

            Previous Conversation:
            {chat_history}

            Question: {input}
            {agent_scratchpad}""",
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
            "memory": {
                "display_name": "Memory",
                "info": "Memory to use for the agent.",
            },
        }

    def build(
        self,
        inputs: str,
        llm: BaseLLM,
        tools: List[Tool],
        prompt: str,
        memory: BaseMemory = None,
        tool_template: str = "{name}: {description}",
        handle_parsing_errors: bool = True,
    ) -> Text:
        if "input" not in prompt:
            raise ValueError("Prompt must contain 'input' key.")

        def render_tool_description(tools):
            return "\n".join([tool_template.format(name=tool.name, description=tool.description) for tool in tools])

        prompt_template = PromptTemplate.from_template(prompt)
        input_variables = prompt_template.input_variables
        agent = create_xml_agent(llm, tools, prompt_template, tools_renderer=render_tool_description)
        runnable = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=tools, verbose=True, memory=memory, handle_parsing_errors=handle_parsing_errors
        )
        input_dict = {"input": inputs}
        for var in input_variables:
            if var not in ["agent_scratchpad", "input"]:
                input_dict[var] = ""
        result = runnable.invoke(input_dict)
        self.status = result
        return result
