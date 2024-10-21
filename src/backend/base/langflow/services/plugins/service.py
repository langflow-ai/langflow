from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from loguru import logger

from langflow.services.base import Service
from langflow.services.plugins.base import BasePlugin, CallbackPlugin


class PluginService(Service):
    name = "plugin_service"

    def __init__(self) -> None:
        self.plugins: dict[str, BasePlugin] = {}
        self.plugin_dir = Path(__file__).parent
        self.plugins_base_module = "langflow.services.plugins"
        self.load_plugins()

    def load_plugins(self) -> None:
        base_files = ["base.py", "service.py", "factory.py", "__init__.py"]
        for module in self.plugin_dir.iterdir():
            if module.suffix == ".py" and module.name not in base_files:
                plugin_name = module.stem
                module_path = f"{self.plugins_base_module}.{plugin_name}"
                try:
                    mod = importlib.import_module(module_path)
                    for attr_name in dir(mod):
                        attr = getattr(mod, attr_name)
                        if (
                            inspect.isclass(attr)
                            and issubclass(attr, BasePlugin)
                            and attr not in {CallbackPlugin, BasePlugin}
                        ):
                            self.register_plugin(plugin_name, attr())
                except Exception:  # noqa: BLE001
                    logger.exception(f"Error loading plugin {plugin_name}")

    def register_plugin(self, plugin_name, plugin_instance) -> None:
        self.plugins[plugin_name] = plugin_instance
        plugin_instance.initialize()

    def get_plugin(self, plugin_name) -> BasePlugin | None:
        return self.plugins.get(plugin_name)

    def get(self, plugin_name):
        if plugin := self.get_plugin(plugin_name):
            return plugin.get()
        return None

    async def teardown(self) -> None:
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
