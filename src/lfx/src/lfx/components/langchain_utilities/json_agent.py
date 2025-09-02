from pathlib import Path

import yaml
from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits import create_json_agent
from langchain_community.agent_toolkits.json.toolkit import JsonToolkit
from langchain_community.tools.json.tool import JsonSpec

from lfx.base.agents.agent import LCAgentComponent
from lfx.inputs.inputs import FileInput, HandleInput


class JsonAgentComponent(LCAgentComponent):
    display_name = "JsonAgent"
    description = "Construct a json agent from an LLM and tools."
    name = "JsonAgent"
    legacy: bool = True

    inputs = [
        *LCAgentComponent.get_base_inputs(),
        HandleInput(
            name="llm",
            display_name="Language Model",
            input_types=["LanguageModel"],
            required=True,
        ),
        FileInput(
            name="path",
            display_name="File Path",
            file_types=["json", "yaml", "yml"],
            required=True,
        ),
    ]

    def build_agent(self) -> AgentExecutor:
        path = Path(self.path)
        if path.suffix in {"yaml", "yml"}:
            with path.open(encoding="utf-8") as file:
                yaml_dict = yaml.safe_load(file)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(path)
        toolkit = JsonToolkit(spec=spec)

        return create_json_agent(llm=self.llm, toolkit=toolkit, **self.get_agent_kwargs())
