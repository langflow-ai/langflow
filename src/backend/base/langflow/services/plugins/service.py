import importlib
import inspect
import os
from typing import TYPE_CHECKING, Union

from loguru import logger

from langflow.services.base import Service
from langflow.services.plugins.base import BasePlugin, CallbackPlugin

if TYPE_CHECKING:
    from langflow.services.settings.service import SettingsService


class PluginService(Service):
    name = "plugin_service"

    def __init__(self, settings_service: "SettingsService"):
        self.plugins: dict[str, BasePlugin] = {}
        # plugin_dir = settings_service.settings.PLUGIN_DIR
        self.plugin_dir = os.path.dirname(__file__)
        self.plugins_base_module = "langflow.services.plugins"
        self.load_plugins()

    def load_plugins(self):
        base_files = ["base.py", "service.py", "factory.py", "__init__.py"]
        for module in os.listdir(self.plugin_dir):
            if module.endswith(".py") and module not in base_files:
                plugin_name = module[:-3]
                module_path = f"{self.plugins_base_module}.{plugin_name}"
                try:
                    mod = importlib.import_module(module_path)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, BasePlugin)
                            and attr not in [CallbackPlugin, BasePlugin]
                        ):
                            self.register_plugin(plugin_name, attr())
                except Exception as exc:
                    logger.error(f"Error loading plugin {plugin_name}: {exc}")

    def register_plugin(self, plugin_name, plugin_instance):
        self.plugins[plugin_name] = plugin_instance
        plugin_instance.initialize()

    def get_plugin(self, plugin_name) -> Union[BasePlugin, None]:
        return self.plugins.get(plugin_name)

    def get(self, plugin_name):
        if plugin := self.get_plugin(plugin_name):
            return plugin.get()
        return None

    async def teardown(self):
        for plugin in self.plugins.values():
            plugin.teardown()

    def get_callbacks(self, _id=None):
        callbacks = []
        for plugin in self.plugins.values():
            if isinstance(plugin, CallbackPlugin):
                callback = plugin.get_callback(_id=_id)
                if callback:
                    callbacks.append(callback)
        return callbacks
