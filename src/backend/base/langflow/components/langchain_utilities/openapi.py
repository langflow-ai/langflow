from pathlib import Path

import yaml
from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits import create_openapi_agent
from langchain_community.agent_toolkits.openapi.toolkit import OpenAPIToolkit
from langchain_community.tools.json.tool import JsonSpec
from langchain_community.utilities.requests import TextRequestsWrapper

from langflow.base.agents.agent import LCAgentComponent
from langflow.inputs import BoolInput, FileInput, HandleInput


class OpenAPIAgentComponent(LCAgentComponent):
    display_name = "OpenAPI Agent"
    description = "Agent to interact with OpenAPI API."
    name = "OpenAPIAgent"
    icon = "LangChain"
    inputs = [
        *LCAgentComponent._base_inputs,
        HandleInput(name="llm", display_name="Language Model", input_types=["LanguageModel"], required=True),
        FileInput(name="path", display_name="File Path", file_types=["json", "yaml", "yml"], required=True),
        BoolInput(name="allow_dangerous_requests", display_name="Allow Dangerous Requests", value=False, required=True),
    ]

    def build_agent(self) -> AgentExecutor:
        path = Path(self.path)
        if path.suffix in {"yaml", "yml"}:
            with path.open(encoding="utf-8") as file:
                yaml_dict = yaml.safe_load(file)
            spec = JsonSpec(dict_=yaml_dict)
        else:
            spec = JsonSpec.from_file(path)
        requests_wrapper = TextRequestsWrapper()
        toolkit = OpenAPIToolkit.from_llm(
            llm=self.llm,
            json_spec=spec,
            requests_wrapper=requests_wrapper,
            allow_dangerous_requests=self.allow_dangerous_requests,
        )

        agent_args = self.get_agent_kwargs()

        # This is bit weird - generally other create_*_agent functions have max_iterations in the
        # `agent_executor_kwargs`, but openai has this parameter passed directly.
        agent_args["max_iterations"] = agent_args["agent_executor_kwargs"]["max_iterations"]
        del agent_args["agent_executor_kwargs"]["max_iterations"]
        return create_openapi_agent(llm=self.llm, toolkit=toolkit, **agent_args)
