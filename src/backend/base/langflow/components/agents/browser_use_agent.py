from browser_use import Agent

from langflow.custom import Component
from langflow.io import HandleInput, MessageTextInput, Output
from langflow.schema import Message


class BrowserUseAgentComponent(Component):
    display_name: str = "Browser Use Agent"
    description: str = "An agent designed to utilize various tools seamlessly within workflows."
    icon = "square-mouse-pointer"

    inputs = [
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
            info="Language model that the agent utilizes to perform tasks effectively.",
        ),
        MessageTextInput(
            name="user_prompt",
            display_name="User Prompt",
            info="The prompt that the agent will use to perform tasks effectively.",
        ),
    ]

    outputs = [
        Output(display_name="result", name="result", method="run_browser_use_agent"),
    ]

    async def run_browser_use_agent(self) -> Message:
        agent = Agent(
            task=self.user_prompt,
            llm=self.llm,
        )
        result = await agent.run()
        print(result)
        return Message(text=str(result))
