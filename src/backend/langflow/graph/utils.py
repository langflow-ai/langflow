import base64
import csv
import io
import json
import re
from typing import Any

import yaml


def load_file(file_name, file_content, accepted_types) -> Any:
    """Load a file from a string."""
    # Check if the file is accepted
    if not any(file_name.endswith(suffix) for suffix in accepted_types):
        raise ValueError(f"File {file_name} is not accepted")
    # Get the suffix
    suffix = file_name.split(".")[-1]
    # file_content == 'data:application/x-yaml;base64,b3BlbmFwaTogIjMuMC4wIg...'
    data = file_content.split(",")[1]
    decoded_bytes = base64.b64decode(data)

    # Convert the bytes object to a string
    decoded_string = decoded_bytes.decode("utf-8")
    if suffix == "json":
        # Return the json content
        return json.loads(decoded_string)
    elif suffix in ["yaml", "yml"]:
        # Return the yaml content
        loaded_yaml = yaml.load(decoded_string, Loader=yaml.FullLoader)
        try:
            from langchain.agents.agent_toolkits.openapi.spec import reduce_openapi_spec  # type: ignore

            return reduce_openapi_spec(loaded_yaml)
        except ImportError:
            return loaded_yaml

    elif suffix == "csv":
        # Load the csv content
        csv_reader = csv.DictReader(io.StringIO(decoded_string))
        return list(csv_reader)
    else:
        raise ValueError(f"File {file_name} is not accepted")


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
