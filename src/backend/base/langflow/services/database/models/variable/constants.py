from enum import Enum


# VARIABLE_TYPES = ["Generic", "Credential", "Prompt"]
class VariableCategories(str, Enum):
    GENERIC = "Generic"
    CREDENTIAL = "Credential"
    PROMPT = "Prompt"


IS_READABLE_MAP = {
    VariableCategories.GENERIC: True,
    VariableCategories.CREDENTIAL: False,
    VariableCategories.PROMPT: True,
}
