import os
from typing import List, Optional

import yaml
from pydantic import BaseSettings, Field, root_validator


class Settings(BaseSettings):
    chains: Optional[List[str]] = Field(...)
    agents: Optional[List[str]] = Field(...)
    prompts: Optional[List[str]] = Field(...)
    llms: Optional[List[str]] = Field(...)
    tools: Optional[List[str]] = Field(...)
    memories: Optional[List[str]] = Field(...)
    dev: bool = Field(...)

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
