from typing import List

from langflow.custom import Component
from langflow.inputs import StrInput, SecretStrInput, DefaultPromptField
from langflow.io import Output

from langchain_core.prompts import ChatPromptTemplate

import re


class LangChainHubPromptComponent(Component):
    display_name: str = "LangChain Hub Prompt Component"
    description: str = "Prompt Component that uses LangChain Hub prompts"
    beta = True
    icon = "prompts"
    trace_type = "prompt"
    name = "LangChain Hub Prompt"

    inputs = [
        SecretStrInput(
            name="langchain_api_key",
            display_name="Your LangChain API Key",
            info="The LangChain API Key to use.",
        ),
        StrInput(
            name="langchain_hub_prompt",
            display_name="LangChain Hub Prompt",
            info="The LangChain Hub prompt to use.",
            value="efriis/my-first-prompt",
            refresh_button=True,
        ),
    ]

    outputs = [
        Output(display_name="Build Chat Prompt", name="template", method="build_chat_prompt"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name == "langchain_hub_prompt":
            template = self._fetch_langchain_hub_template()

            # Extract the messages from the prompt data
            prompt_template = []
            for message_data in template.messages:
                prompt_template.append(message_data.prompt)

            # Regular expression to find all instances of {<string>}
            pattern = r"\{(.*?)\}"

            # Get all the custom fields
            custom_fields: List[str] = []
            full_template = ""
            for message in prompt_template:
                # Find all matches
                matches = re.findall(pattern, message.template)
                custom_fields = custom_fields + matches

                # Create a string version of the full template
                full_template = full_template + "\n" + message.template

            # Easter egg: Show template in info popup
            build_config["langchain_hub_prompt"]["info"] = full_template

            # Now create inputs for each
            for custom_field in custom_fields:
                new_parameter = DefaultPromptField(
                    name=custom_field,
                    display_name=custom_field,
                    ihfo="Fill in the value for {" + custom_field + "}",
                ).to_dict()

                build_config[custom_field] = new_parameter

        return build_config

    def build_chat_prompt(
        self,
    ) -> ChatPromptTemplate:

        # Get the parameters that 
        template = self._fetch_langchain_hub_template() # TODO: doing this twice
        prompt_value = template.invoke(self._attributes)

        # Now build the ChatPromptTemplate back
        prompt_messages = prompt_value.to_messages()
        prompt_template = ChatPromptTemplate.from_messages(prompt_messages)

        self.status = prompt_value.to_string()

        return prompt_template

    def _fetch_langchain_hub_template(self):
        import langchain.hub

        # Pull the prompt from LangChain Hub
        prompt_data = langchain.hub.pull(self.langchain_hub_prompt, api_key=self.langchain_api_key)

        return prompt_data
