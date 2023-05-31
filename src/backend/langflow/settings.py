import os
from typing import List

import yaml
from pydantic import BaseSettings, root_validator


class Settings(BaseSettings):
    chains: List[str] = []
    agents: List[str] = []
    prompts: List[str] = []
    llms: List[str] = []
    tools: List[str] = []
    memories: List[str] = []
    embeddings: List[str] = []
    vectorstores: List[str] = []
    documentloaders: List[str] = []
    wrappers: List[str] = []
    toolkits: List[str] = []
    textsplitters: List[str] = []
    utilities: List[str] = []
    dev: bool = False

    class Config:
        validate_assignment = True
        extra = "ignore"

    @root_validator(allow_reuse=True)
    def validate_lists(cls, values):
        for key, value in values.items():
            if key != "dev" and not value:
                values[key] = []
        return values

    def update_from_yaml(self, file_path: str, dev: bool = False):
        new_settings = load_settings_from_yaml(file_path)
        self.chains = new_settings.chains or []
        self.agents = new_settings.agents or []
        self.prompts = new_settings.prompts or []
        self.llms = new_settings.llms or []
        self.tools = new_settings.tools or []
        self.memories = new_settings.memories or []
        self.wrappers = new_settings.wrappers or []
        self.toolkits = new_settings.toolkits or []
        self.textsplitters = new_settings.textsplitters or []
        self.utilities = new_settings.utilities or []
        self.dev = dev


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

    return Settings(**settings_dict)


settings = load_settings_from_yaml("config.yaml")
