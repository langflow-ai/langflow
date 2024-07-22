from langchain.agents import create_xml_agent
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate, HumanMessagePromptTemplate

from langflow.base.agents.agent import LCToolsAgentComponent
from langflow.inputs import MultilineInput
from langflow.inputs.inputs import HandleInput


class XMLAgentComponent(LCToolsAgentComponent):
    display_name: str = "XML Agent"
    description: str = "Agent that uses tools formatting instructions as xml to the Language Model."
    icon = "LangChain"
    beta = True
    name = "XMLAgent"

    inputs = LCToolsAgentComponent._base_inputs + [
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        MultilineInput(
            name="user_prompt",
            display_name="Prompt",
            value="""
You are a helpful assistant. Help the user answer any questions.

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
            """,
        ),
    ]

    def create_agent_runnable(self):
        messages = [
            HumanMessagePromptTemplate(prompt=PromptTemplate(input_variables=["input"], template=self.user_prompt))
        ]
        prompt = ChatPromptTemplate.from_messages(messages)
        return create_xml_agent(self.llm, self.tools, prompt)
