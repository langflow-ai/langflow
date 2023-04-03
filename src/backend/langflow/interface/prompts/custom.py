from typing import List, Optional

from langchain.prompts import PromptTemplate
from pydantic import root_validator

from langflow.graph.utils import extract_input_variables_from_prompt
from langflow.template.base import Template, TemplateField
from langflow.template.nodes import PromptTemplateNode

CHARACTER_PROMPT = """I want you to act like {character} from {series}.
I want you to respond and answer like {character}. do not write any explanations. only answer like {character}.
You must know all of the knowledge of {character}."""


class BaseCustomPrompt(PromptTemplate):
    template: str = ""
    description: Optional[str]
    human_text: str = "\n {input}"

    @root_validator(pre=False)
    def build_template(cls, values):
        format_dict = {}
        for key in values.get("input_variables", []):
            new_value = values[key]
            format_dict[key] = new_value

        values["template"] = values["template"].format(**format_dict)

        values["template"] = values["template"] + values["human_text"]
        values["input_variables"] = extract_input_variables_from_prompt(
            values["template"]
        )
        return values

    def build_frontend_node(self) -> PromptTemplateNode:
        return PromptTemplateNode(
            template=Template(
                type_name="test",
                fields=[
                    TemplateField(name=field, field_type="str", required=True)
                    for field in self.input_variables
                ],
            ),
            description=self.description or "",
        )


class SeriesCharacterPrompt(BaseCustomPrompt):
    # Add a very descriptive description for the prompt generator
    description: Optional[
        str
    ] = "A prompt that asks the AI to act like a character from a series."
    character: str
    series: str
    human_text: str = "\n {input}"
    template: str = CHARACTER_PROMPT

    input_variables: List[str] = ["character", "series"]


if __name__ == "__main__":
    prompt = SeriesCharacterPrompt(character="Walter White", series="Breaking Bad")
    user_input = "I am the one who knocks"
    full_prompt = prompt.format(input=user_input)
    print(full_prompt)
