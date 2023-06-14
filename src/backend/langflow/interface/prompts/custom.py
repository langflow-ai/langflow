from typing import Dict, List, Optional, Type

from langchain.prompts import PromptTemplate
from pydantic import root_validator

from langflow.interface.utils import extract_input_variables_from_prompt

# Steps to create a BaseCustomPrompt:
# 1. Create a prompt template that endes with:
#    Current conversation:
#     {history}
#    Human: {input}
#    {ai_prefix}:
# 2. Create a class that inherits from BaseCustomPrompt
# 3. Add the following class attributes:
#    template: str = ""
#    description: Optional[str]
#    ai_prefix: Optional[str] = "{ai_prefix}"
# 3.1. The ai_prefix should be a value in input_variables
# SeriesCharacterPrompt is a working example
# If used in a LLMChain, with a Memory module, it will work as expected
# We should consider creating ConversationalChains that expose custom parameters
# That way it will be easier to create custom prompts


class BaseCustomPrompt(PromptTemplate):
    template: str = ""
    description: Optional[str]
    ai_prefix: Optional[str]

    @root_validator(pre=False)
    def build_template(cls, values):
        format_dict = {}
        ai_prefix_format_dict = {}
        for key in values.get("input_variables", []):
            new_value = values.get(key, f"{{{key}}}")
            format_dict[key] = new_value
            if key in values["ai_prefix"]:
                ai_prefix_format_dict[key] = new_value

        values["ai_prefix"] = values["ai_prefix"].format(**ai_prefix_format_dict)
        values["template"] = values["template"].format(**format_dict)

        values["template"] = values["template"]
        values["input_variables"] = extract_input_variables_from_prompt(
            values["template"]
        )
        return values


class SeriesCharacterPrompt(BaseCustomPrompt):
    # Add a very descriptive description for the prompt generator
    description: Optional[
        str
    ] = "A prompt that asks the AI to act like a character from a series."
    character: str
    series: str
    template: str = """I want you to act like {character} from {series}.
I want you to respond and answer like {character}. do not write any explanations. only answer like {character}.
You must know all of the knowledge of {character}.

Current conversation:
{history}
Human: {input}
{character}:"""

    ai_prefix: str = "{character}"
    input_variables: List[str] = ["character", "series"]


CUSTOM_PROMPTS: Dict[str, Type[BaseCustomPrompt]] = {
    "SeriesCharacterPrompt": SeriesCharacterPrompt
}
