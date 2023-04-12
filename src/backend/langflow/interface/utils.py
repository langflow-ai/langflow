import json
import os

import yaml


def load_file_into_dict(file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_extension = os.path.splitext(file_path)[1].lower()

    if file_extension == ".json":
        with open(file_path, "r") as json_file:
            data = json.load(json_file)
    elif file_extension in [".yaml", ".yml"]:
        with open(file_path, "r") as yaml_file:
            data = yaml.safe_load(yaml_file)
    else:
        raise ValueError("Unsupported file type. Please provide a JSON or YAML file.")

    return data
