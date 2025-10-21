"""
Runtime Converter Factory.

This module provides a factory pattern for creating and managing runtime converters
with plugin architecture support for dynamic loading.
"""

from typing import Dict, Type, Optional, List, Any, Union
import logging
import importlib
from pathlib import Path
import inspect

from .base_converter import RuntimeConverter, RuntimeType, ConversionMode
from .registry import runtime_registry
from .langflow_converter import LangflowConverter
from .temporal_converter import TemporalConverter
from .kafka_converter import KafkaConverter

logger = logging.getLogger(__name__)


class ConverterFactory:
    """
    Factory for creating runtime converters with plugin support.

    The factory supports:
    - Built-in converter instantiation
    - Dynamic plugin loading
    - Runtime converter registration
    - Fallback mechanisms
    """

    def __init__(self):
        """Initialize the converter factory."""
        self.logger = logging.getLogger(__name__)
        self._built_in_converters = self._register_built_in_converters()
        self._plugin_paths: List[str] = []
        self._loaded_plugins: Dict[str, Type[RuntimeConverter]] = {}

    def create_converter(self, runtime_type: Union[str, RuntimeType],
                        **kwargs) -> Optional[RuntimeConverter]:
        """
        Create a runtime converter instance.

        Args:
            runtime_type: Runtime type (string or enum)
            **kwargs: Additional arguments for converter initialization

        Returns:
            RuntimeConverter instance or None if not found
        """
        # Normalize runtime type
        if isinstance(runtime_type, str):
            try:
                runtime_enum = RuntimeType(runtime_type.lower())
            except ValueError:
                self.logger.error(f"Unknown runtime type: {runtime_type}")
                return None
        else:
            runtime_enum = runtime_type

        # Try built-in converters first
        converter_class = self._built_in_converters.get(runtime_enum)
        if converter_class:
            try:
                return converter_class(**kwargs)
            except Exception as e:
                self.logger.error(f"Failed to create built-in converter for {runtime_enum.value}: {e}")

        # Try loaded plugins
        plugin_class = self._loaded_plugins.get(runtime_enum.value)
        if plugin_class:
            try:
                return plugin_class(runtime_enum, **kwargs)
            except Exception as e:
                self.logger.error(f"Failed to create plugin converter for {runtime_enum.value}: {e}")

        # Try to load from registry
        converter = runtime_registry.get_converter(runtime_enum.value)
        if converter:
            return converter

        self.logger.warning(f"No converter found for runtime: {runtime_enum.value}")
        return None

    def register_converter_class(self, runtime_type: Union[str, RuntimeType],
                                converter_class: Type[RuntimeConverter]) -> None:
        """
        Register a converter class for a runtime.

        Args:
            runtime_type: Runtime type
            converter_class: Converter class to register
        """
        # Normalize runtime type
        if isinstance(runtime_type, str):
            try:
                runtime_enum = RuntimeType(runtime_type.lower())
            except ValueError:
                self.logger.error(f"Unknown runtime type: {runtime_type}")
                return
        else:
            runtime_enum = runtime_type

        # Validate converter class
        if not issubclass(converter_class, RuntimeConverter):
            raise ValueError(f"Converter class must inherit from RuntimeConverter")

        # Register with registry
        runtime_registry.register_converter_class(runtime_enum, converter_class)

        # Store in built-in converters
        self._built_in_converters[runtime_enum] = converter_class

        self.logger.info(f"Registered converter class for runtime: {runtime_enum.value}")

    def load_plugins_from_path(self, plugin_path: str) -> int:
        """
        Load converter plugins from a directory path.

        Args:
            plugin_path: Path to scan for plugin modules

        Returns:
            Number of plugins loaded
        """
        loaded_count = 0
        plugin_dir = Path(plugin_path)

        if not plugin_dir.exists() or not plugin_dir.is_dir():
            self.logger.warning(f"Plugin path does not exist or is not a directory: {plugin_path}")
            return 0

        # Add to plugin paths
        if plugin_path not in self._plugin_paths:
            self._plugin_paths.append(plugin_path)

        # Scan for Python files
        for python_file in plugin_dir.glob("*.py"):
            if python_file.name.startswith("_"):
                continue  # Skip private modules

            try:
                loaded_count += self._load_plugin_file(python_file)
            except Exception as e:
                self.logger.error(f"Failed to load plugin from {python_file}: {e}")

        self.logger.info(f"Loaded {loaded_count} plugins from {plugin_path}")
        return loaded_count

    def load_plugin_module(self, module_name: str) -> int:
        """
        Load converter plugins from a specific module.

        Args:
            module_name: Full module name to import

        Returns:
            Number of plugins loaded
        """
        try:
            module = importlib.import_module(module_name)
            return self._scan_module_for_converters(module)
        except ImportError as e:
            self.logger.error(f"Failed to import plugin module {module_name}: {e}")
            return 0
        except Exception as e:
            self.logger.error(f"Error loading plugin module {module_name}: {e}")
            return 0

    def get_available_runtimes(self) -> List[str]:
        """
        Get list of all available runtime types.

        Returns:
            List of runtime names
        """
        runtimes = set()

        # Add built-in runtimes
        runtimes.update(rt.value for rt in self._built_in_converters.keys())

        # Add plugin runtimes
        runtimes.update(self._loaded_plugins.keys())

        # Add registry runtimes
        runtimes.update(runtime_registry.list_available_runtimes())

        return sorted(list(runtimes))

    def get_converter_info(self, runtime_type: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a specific converter.

        Args:
            runtime_type: Runtime type name

        Returns:
            Converter information dictionary or None
        """
        converter = self.create_converter(runtime_type)
        if not converter:
            return None

        try:
            info = converter.get_runtime_info()
            info["source"] = self._get_converter_source(runtime_type)
            info["conversion_modes"] = [mode.value for mode in converter.get_supported_conversion_modes()]
            return info
        except Exception as e:
            self.logger.error(f"Failed to get converter info for {runtime_type}: {e}")
            return None

    def validate_converter_compatibility(self, runtime_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if a converter can handle a specific specification.

        Args:
            runtime_type: Runtime type name
            spec: Genesis specification

        Returns:
            Validation result
        """
        converter = self.create_converter(runtime_type)
        if not converter:
            return {
                "compatible": False,
                "error": f"Converter not found for runtime: {runtime_type}"
            }

        try:
            validation_errors = converter.validate_specification(spec)
            return {
                "compatible": len(validation_errors) == 0,
                "errors": validation_errors,
                "runtime_info": converter.get_runtime_info()
            }
        except Exception as e:
            return {
                "compatible": False,
                "error": f"Validation failed: {str(e)}"
            }

    def convert_with_fallback(self, spec: Dict[str, Any], preferred_runtime: str,
                             fallback_runtimes: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Convert specification with fallback runtime support.

        Args:
            spec: Genesis specification
            preferred_runtime: Preferred runtime type
            fallback_runtimes: List of fallback runtimes to try

        Returns:
            Conversion result with metadata
        """
        fallback_runtimes = fallback_runtimes or ["langflow"]
        runtimes_to_try = [preferred_runtime] + [rt for rt in fallback_runtimes if rt != preferred_runtime]

        for runtime in runtimes_to_try:
            try:
                converter = self.create_converter(runtime)
                if not converter:
                    continue

                # Validate compatibility
                validation_errors = converter.validate_specification(spec)
                if validation_errors:
                    self.logger.warning(f"Runtime {runtime} validation failed: {validation_errors}")
                    continue

                # Attempt conversion
                result = converter.convert_to_runtime(spec)
                return {
                    "success": True,
                    "runtime_used": runtime,
                    "result": result,
                    "fallback_used": runtime != preferred_runtime
                }

            except Exception as e:
                self.logger.warning(f"Conversion failed for runtime {runtime}: {e}")
                continue

        return {
            "success": False,
            "error": f"All runtimes failed: {runtimes_to_try}",
            "attempted_runtimes": runtimes_to_try
        }

    def _register_built_in_converters(self) -> Dict[RuntimeType, Type[RuntimeConverter]]:
        """Register built-in converter classes."""
        converters = {
            RuntimeType.LANGFLOW: LangflowConverter,
            RuntimeType.TEMPORAL: TemporalConverter,
            RuntimeType.KAFKA: KafkaConverter
        }

        # Register with registry
        for runtime_type, converter_class in converters.items():
            runtime_registry.register_converter_class(runtime_type, converter_class)

        self.logger.info(f"Registered {len(converters)} built-in converters")
        return converters

    def _load_plugin_file(self, plugin_file: Path) -> int:
        """Load converters from a plugin file."""
        loaded_count = 0

        try:
            # Create module name from file path
            module_name = f"runtime_converter_plugin_{plugin_file.stem}"

            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)
            if not spec or not spec.loader:
                return 0

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Scan for converter classes
            loaded_count = self._scan_module_for_converters(module)

        except Exception as e:
            self.logger.error(f"Failed to load plugin file {plugin_file}: {e}")

        return loaded_count

    def _scan_module_for_converters(self, module) -> int:
        """Scan a module for RuntimeConverter classes."""
        loaded_count = 0

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, RuntimeConverter) and
                obj is not RuntimeConverter and
                hasattr(obj, 'runtime_type')):

                try:
                    # Get runtime type from class
                    if hasattr(obj, '_runtime_type'):
                        runtime_type = obj._runtime_type
                    elif hasattr(obj, 'RUNTIME_TYPE'):
                        runtime_type = obj.RUNTIME_TYPE
                    else:
                        # Try to instantiate to get runtime type
                        instance = obj()
                        runtime_type = instance.runtime_type.value

                    # Store plugin
                    self._loaded_plugins[runtime_type] = obj
                    loaded_count += 1

                    self.logger.info(f"Loaded plugin converter: {name} for runtime {runtime_type}")

                except Exception as e:
                    self.logger.warning(f"Failed to load converter class {name}: {e}")

        return loaded_count

    def _get_converter_source(self, runtime_type: str) -> str:
        """Determine the source of a converter (built-in, plugin, or registry)."""
        try:
            runtime_enum = RuntimeType(runtime_type.lower())
            if runtime_enum in self._built_in_converters:
                return "built-in"
        except ValueError:
            pass

        if runtime_type in self._loaded_plugins:
            return "plugin"

        return "registry"

    def auto_discover_plugins(self) -> int:
        """
        Automatically discover and load plugins from common locations.

        Returns:
            Total number of plugins loaded
        """
        total_loaded = 0

        # Common plugin directories
        plugin_dirs = [
            "langflow/services/runtime/plugins",
            "~/.langflow/plugins/runtime",
            "/etc/langflow/plugins/runtime"
        ]

        for plugin_dir in plugin_dirs:
            expanded_path = Path(plugin_dir).expanduser()
            if expanded_path.exists():
                total_loaded += self.load_plugins_from_path(str(expanded_path))

        self.logger.info(f"Auto-discovery loaded {total_loaded} plugins")
        return total_loaded

    def reload_plugins(self) -> int:
        """
        Reload all plugins from registered paths.

        Returns:
            Total number of plugins reloaded
        """
        # Clear loaded plugins
        self._loaded_plugins.clear()

        # Reload from all plugin paths
        total_reloaded = 0
        for plugin_path in self._plugin_paths:
            total_reloaded += self.load_plugins_from_path(plugin_path)

        self.logger.info(f"Reloaded {total_reloaded} plugins")
        return total_reloaded

    def get_plugin_info(self) -> Dict[str, Any]:
        """
        Get information about loaded plugins.

        Returns:
            Plugin information dictionary
        """
        return {
            "plugin_paths": self._plugin_paths,
            "loaded_plugins": {
                runtime: plugin_class.__name__
                for runtime, plugin_class in self._loaded_plugins.items()
            },
            "built_in_converters": {
                runtime.value: converter_class.__name__
                for runtime, converter_class in self._built_in_converters.items()
            },
            "total_plugins": len(self._loaded_plugins),
            "total_built_in": len(self._built_in_converters)
        }


# Global factory instance
converter_factory = ConverterFactory()