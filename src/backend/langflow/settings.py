import os
from typing import List

import yaml
from pydantic import BaseSettings, Field, root_validator


class Settings(BaseSettings):
    chains: List[str] = Field(default=[])
    agents: List[str] = Field(default=[])
    prompts: List[str] = Field(default=[])
    llms: List[str] = Field(default=[])
    tools: List[str] = Field(default=[])
    memories: List[str] = Field(default=[])
    dev: bool = Field(default=False)

    class Config:
        validate_assignment = True

    @root_validator
    def validate_lists(cls, values):
        for key, value in values.items():
            if key != "dev" and not value:
                values[key] = []
        return values


def save_settings_to_yaml(settings: Settings, file_path: str):
    with open(file_path, "w") as f:
        settings_dict = settings.dict()
        yaml.dump(settings_dict, f)


def load_settings_from_yaml(file_path: str) -> Settings:
    # Check if a string is a valid path or a file name
    if "/" not in file_path:
        # Get current path
        current_path = os.path.dirname(os.path.abspath(__file__))

        file_path = os.path.join(current_path, file_path)

    with open(file_path, "r") as f:
        settings_dict = yaml.safe_load(f)
        a = Settings.parse_obj(settings_dict)

    return a


settings = load_settings_from_yaml("config.yaml")
