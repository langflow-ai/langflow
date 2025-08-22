import hashlib
import sys
import tempfile
import types
import weakref
from pathlib import Path

from loguru import logger


class DebugHelper:
    """Debug helper class for managing debug files and module creation/cleanup."""

    def __init__(self, code, class_name, debug_file_base_dir: str | None = None):
        """Initialize debug helper."""
        self._debug_file_base_dir = debug_file_base_dir or self._setup_debug_file_base_dir()
        self.code = code
        self.class_name = class_name
        self.debug_filepath = self._create_debug_file(code, class_name)
        self.debug_module_name = self._create_debug_module(self.debug_filepath)

    @staticmethod
    def is_debug_mode() -> bool:
        """Check if in debug mode."""
        # skip debug in initialization stage
        try:
            from langflow.interface.components import component_cache

            has_initialized = component_cache.all_types_dict is not None
        except (ImportError, AttributeError):
            has_initialized = False

        return sys.gettrace() is not None and has_initialized

    def _setup_debug_file_base_dir(self) -> Path:
        """Setup debug code base directory."""
        debug_file_base_dir = Path(tempfile.gettempdir()) / "langflow_debug"
        Path(debug_file_base_dir).mkdir(exist_ok=True)
        return debug_file_base_dir

    def _create_debug_file(self, code: str, class_name: str) -> str:
        """Create debug source code file."""
        code_hash = hashlib.md5(code.encode()).hexdigest()[:8]  # noqa: S324
        debug_filename = f"component_{class_name}_{code_hash}.py"
        debug_filepath = Path(self._debug_file_base_dir) / debug_filename

        if not Path(debug_filepath).exists():
            with Path(debug_filepath).open("w", encoding="utf-8") as f:
                f.write(code)

        return str(debug_filepath)

    def _create_debug_module(self, debug_filepath: str) -> str:
        """Create debug module."""
        file_name = Path(debug_filepath).stem
        mod = types.ModuleType(file_name)
        mod.__file__ = debug_filepath
        sys.modules[file_name] = mod
        return file_name

    def _cleanup_debug_resources(self, debug_filepath: str, debug_module_name: str):
        """Cleanup debug resources."""
        try:
            if debug_filepath and Path(debug_filepath).exists():
                Path(debug_filepath).unlink()
                logger.debug(f"Auto cleanup debug file: {debug_filepath}")

            if debug_module_name and debug_module_name in sys.modules:
                del sys.modules[debug_module_name]
                logger.debug(f"Auto cleanup debug module: {debug_module_name}")

        except (OSError, KeyError) as e:
            logger.debug(f"Error cleaning up debug resources: {e}")

    def register_debug_cleanup(self, target_class):
        weakref.finalize(target_class, self._cleanup_debug_resources, self.debug_filepath, self.debug_module_name)
