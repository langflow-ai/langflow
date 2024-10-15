import re

from langchain_core.prompts import HumanMessagePromptTemplate

from langflow.custom import Component
from langflow.inputs import DefaultPromptField, SecretStrInput, StrInput
from langflow.io import Output
from langflow.schema.message import Message


class LangChainHubPromptComponent(Component):
    display_name: str = "LangChain Hub"
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
            required=True,
        ),
        StrInput(
            name="langchain_hub_prompt",
            display_name="LangChain Hub Prompt",
            info="The LangChain Hub prompt to use, i.e., 'efriis/my-first-prompt'",
            refresh_button=True,
            required=True,
        ),
    ]

    outputs = [
        Output(display_name="Build Prompt", name="prompt", method="build_prompt"),
    ]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        # If the field is not langchain_hub_prompt or the value is empty, return the build config as is
        if field_name != "langchain_hub_prompt" or not field_value:
            return build_config

        # Fetch the template
        template = self._fetch_langchain_hub_template()

        # Get the template's messages
        if hasattr(template, "messages"):
            template_messages = template.messages
        else:
            template_messages = [HumanMessagePromptTemplate(prompt=template)]

        # Extract the messages from the prompt data
        prompt_template = [message_data.prompt for message_data in template_messages]

        # Regular expression to find all instances of {<string>}
        pattern = r"\{(.*?)\}"

        # Get all the custom fields
        custom_fields: list[str] = []
        full_template = ""
        for message in prompt_template:
            # Find all matches
            matches = re.findall(pattern, message.template)
            custom_fields += matches

            # Create a string version of the full template
            full_template = full_template + "\n" + message.template

        # No need to reprocess if we have them already
        if all("param_" + custom_field in build_config for custom_field in custom_fields):
            return build_config

        # Easter egg: Show template in info popup
        build_config["langchain_hub_prompt"]["info"] = full_template

        # Remove old parameter inputs if any
        for key in build_config.copy():
            if key.startswith("param_"):
                del build_config[key]

        # Now create inputs for each
        for custom_field in custom_fields:
            new_parameter = DefaultPromptField(
                name=f"param_{custom_field}",
                display_name=custom_field,
                info="Fill in the value for {" + custom_field + "}",
            ).to_dict()

            # Add the new parameter to the build config
            build_config[f"param_{custom_field}"] = new_parameter

        return build_config

    async def build_prompt(
        self,
    ) -> Message:
        # Fetch the template
        template = self._fetch_langchain_hub_template()

        # Get the parameters from the attributes
        original_params = {k.removeprefix("param_"): v for k, v in self._attributes.items()}
        prompt_value = template.invoke(original_params)

        original_params["template"] = prompt_value.to_string()

        # Now pass the filtered attributes to the function
        prompt = await Message.from_template_and_variables(**original_params)

        self.status = prompt.text

        return prompt

    def _fetch_langchain_hub_template(self):
        import langchain.hub

        # Check if the api key is provided
        if not self.langchain_api_key:
            msg = "Please provide a LangChain API Key"

            raise ValueError(msg)

        # Pull the prompt from LangChain Hub
        return langchain.hub.pull(self.langchain_hub_prompt, api_key=self.langchain_api_key)
