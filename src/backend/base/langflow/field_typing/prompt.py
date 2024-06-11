from langchain_core.load import load
from langchain_core.messages import HumanMessage
from langchain_core.prompts import BaseChatPromptTemplate, ChatPromptTemplate, PromptTemplate

from langflow.base.prompts.utils import dict_values_to_string
from langflow.schema.message import Message
from langflow.schema.record import Record


class Prompt(Record):
    def load_lc_prompt(self):
        if "prompt" not in self:
            raise ValueError("Prompt is required.")
        return load(self.prompt)

    @classmethod
    def from_lc_prompt(
        cls,
        prompt: BaseChatPromptTemplate,
    ):
        prompt_json = prompt.to_json()
        return cls(prompt=prompt_json)

    def format_text(self):
        prompt_template = PromptTemplate.from_template(self.template)
        variables_with_str_values = dict_values_to_string(self.variables)
        formatted_prompt = prompt_template.format(**variables_with_str_values)
        self.text = formatted_prompt
        return formatted_prompt

    @classmethod
    async def from_template_and_variables(cls, template: str, variables: dict):
        instance = cls(template=template, variables=variables)
        contents = [{"type": "text", "text": instance.format_text()}]
        # Get all Message instances from the kwargs
        for value in variables.values():
            if isinstance(value, Message):
                content_dicts = await value.get_file_content_dicts()
                contents.extend(content_dicts)
        prompt_template = ChatPromptTemplate.from_messages([HumanMessage(content=contents)])
        instance.prompt = prompt_template.to_json()
        return instance
