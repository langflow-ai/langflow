import re


def validate_prompt(prompt: str):
    """Validate prompt."""
    if extract_input_variables_from_prompt(prompt):
        return prompt

    return fix_prompt(prompt)


def fix_prompt(prompt: str):
    """Fix prompt."""
    return prompt + " {input}"


def extract_input_variables_from_prompt(prompt: str) -> list[str]:
    """Extract input variables from prompt."""
    return re.findall(r"{(.*?)}", prompt)
