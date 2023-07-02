from pathlib import Path
from langflow.schema import Component, ComponentList

import yaml
from pydantic import BaseSettings, root_validator


class Settings(BaseSettings):
    chains: ComponentList = ComponentList(components=[])
    agents: ComponentList = ComponentList(components=[])
    prompts: ComponentList = ComponentList(components=[])
    llms: ComponentList = ComponentList(components=[])
    tools: ComponentList = ComponentList(components=[])
    memories: ComponentList = ComponentList(components=[])
    embeddings: ComponentList = ComponentList(components=[])
    vectorstores: ComponentList = ComponentList(components=[])
    documentloaders: ComponentList = ComponentList(components=[])
    wrappers: ComponentList = ComponentList(components=[])
    toolkits: ComponentList = ComponentList(components=[])
    textsplitters: ComponentList = ComponentList(components=[])
    utilities: ComponentList = ComponentList(components=[])
    dev: bool = False
    database_url: str = "sqlite:///./langflow.db"
    cache: str = "InMemoryCache"
    remove_api_keys: bool = False

    class Config:
        validate_assignment = True
        extra = "ignore"
        env_prefix = "LANGFLOW_"

    @root_validator(allow_reuse=True)
    def validate_lists(cls, values):
        for key, value in values.items():
            if key != "dev" and not value:
                values[key] = []
        return values

    def update_from_yaml(self, file_path: str, dev: bool = False):
        new_settings = load_settings_from_yaml(file_path)
        self.chains = new_settings.chains
        self.agents = new_settings.agents
        self.prompts = new_settings.prompts
        self.llms = new_settings.llms
        self.tools = new_settings.tools
        self.memories = new_settings.memories
        self.wrappers = new_settings.wrappers
        self.toolkits = new_settings.toolkits
        self.textsplitters = new_settings.textsplitters
        self.utilities = new_settings.utilities
        self.dev = dev

    def update_settings(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


def save_settings_to_yaml(settings: Settings, file_path: str):
    with open(file_path, "w") as f:
        settings_dict = settings.dict()
        yaml.dump(settings_dict, f)


def load_settings_from_yaml(config_folder: str) -> Settings:
    settings_dict = {}

    # Load the main config.yaml file if present
    config_file = Path(config_folder) / "config.yaml"
    if config_file.exists():
        with open(config_file, "r") as f:
            settings_dict = yaml.safe_load(f) or {}

    # Load component-specific config files
    component_files = []
    for key, value in settings_dict.items():
        if isinstance(value, str):
            component_file = Path(config_folder) / value
            if component_file.exists():
                component_files.append(component_file)

    for component_file in component_files:
        component_type = component_file.stem  # Get component type from file name

        with open(component_file, "r") as f:
            component_data = yaml.safe_load(f)
            components = [Component(**component) for component in component_data]
            settings_dict[component_type] = ComponentList(components=components)

    # Convert the component lists in the settings dictionary to ComponentList objects
    for key, value in settings_dict.items():
        if isinstance(value, list):
            settings_dict[key] = ComponentList(components=value)

    return Settings(**settings_dict)


settings = load_settings_from_yaml("./config/config.yaml")
