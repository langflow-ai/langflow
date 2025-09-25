import base64
import contextlib
import hashlib
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import UploadFile
from platformdirs import user_cache_dir

# Try to import logger, fallback to standard logging if lfx not available
try:
    from lfx.log.logger import logger
except ImportError:
    import logging

    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from langflow.api.v1.schemas import BuildStatus

CACHE: dict[str, Any] = {}

CACHE_DIR = user_cache_dir("langflow", "langflow")

PREFIX = "langflow_cache"


# Define CACHE_MISS for compatibility
class CacheMiss:
    def __repr__(self):
        return "<CACHE_MISS>"


CACHE_MISS = CacheMiss()


def create_cache_folder(func):
    def wrapper(*args, **kwargs):
        # Get the destination folder
        cache_path = Path(CACHE_DIR) / PREFIX

        # Create the destination folder if it doesn't exist
        cache_path.mkdir(parents=True, exist_ok=True)

        return func(*args, **kwargs)

    return wrapper


@create_cache_folder
def clear_old_cache_files(max_cache_size: int = 3) -> None:
    cache_dir = Path(tempfile.gettempdir()) / PREFIX
    cache_files = list(cache_dir.glob("*.dill"))

    if len(cache_files) > max_cache_size:
        cache_files_sorted_by_mtime = sorted(cache_files, key=lambda x: x.stat().st_mtime, reverse=True)

        for cache_file in cache_files_sorted_by_mtime[max_cache_size:]:
            with contextlib.suppress(OSError):
                cache_file.unlink()


def filter_json(json_data):
    filtered_data = json_data.copy()

    # Remove 'viewport' and 'chatHistory' keys
    if "viewport" in filtered_data:
        del filtered_data["viewport"]
    if "chatHistory" in filtered_data:
        del filtered_data["chatHistory"]

    # Filter nodes
    if "nodes" in filtered_data:
        for node in filtered_data["nodes"]:
            if "position" in node:
                del node["position"]
            if "positionAbsolute" in node:
                del node["positionAbsolute"]
            if "selected" in node:
                del node["selected"]
            if "dragging" in node:
                del node["dragging"]

    return filtered_data


@create_cache_folder
def save_binary_file(content: str, file_name: str, accepted_types: list[str]) -> str:
    """Save a binary file to the specified folder.

    Args:
        content: The content of the file as a bytes object.
        file_name: The name of the file, including its extension.
        accepted_types: A list of accepted file types.

    Returns:
        The path to the saved file.
    """
    if not any(file_name.endswith(suffix) for suffix in accepted_types):
        msg = f"File {file_name} is not accepted"
        raise ValueError(msg)

    # Get the destination folder
    cache_path = Path(CACHE_DIR) / PREFIX
    if not content:
        msg = "Please, reload the file in the loader."
        raise ValueError(msg)
    data = content.split(",")[1]
    decoded_bytes = base64.b64decode(data)

    # Create the full file path
    file_path = cache_path / file_name

    # Save the binary content to the file
    file_path.write_bytes(decoded_bytes)

    return str(file_path)


@create_cache_folder
def save_uploaded_file(file: UploadFile, folder_name):
    """Save an uploaded file to the specified folder with a hash of its content as the file name.

    Args:
        file: The uploaded file object.
        folder_name: The name of the folder to save the file in.

    Returns:
        The path to the saved file.
    """
    cache_path = Path(CACHE_DIR)
    folder_path = cache_path / folder_name
    filename = file.filename
    file_extension = Path(filename).suffix if isinstance(filename, str | Path) else ""
    file_object = file.file

    # Create the folder if it doesn't exist
    if not folder_path.exists():
        folder_path.mkdir()

    # Create a hash of the file content
    sha256_hash = hashlib.sha256()
    # Reset the file cursor to the beginning of the file
    file_object.seek(0)
    # Iterate over the uploaded file in small chunks to conserve memory
    while chunk := file_object.read(8192):  # Read 8KB at a time (adjust as needed)
        sha256_hash.update(chunk)

    # Use the hex digest of the hash as the file name
    hex_dig = sha256_hash.hexdigest()
    file_name = f"{hex_dig}{file_extension}"

    # Reset the file cursor to the beginning of the file
    file_object.seek(0)

    # Save the file with the hash as its name
    file_path = folder_path / file_name

    with file_path.open("wb") as new_file:
        while chunk := file_object.read(8192):
            new_file.write(chunk)

    return file_path


def update_build_status(cache_service, flow_id: str, status: "BuildStatus") -> None:
    cached_flow = cache_service[flow_id]
    if cached_flow is None:
        msg = f"Flow {flow_id} not found in cache"
        raise ValueError(msg)
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow
    cached_flow["status"] = status
    cache_service[flow_id] = cached_flow


def setup_rich_pickle_support() -> bool:
    """Setup pickle support for Rich library objects.

    This function adds custom __getstate__ and __setstate__ methods to Rich library's
    ConsoleThreadLocals and Console classes to enable serialization for Redis caching.

    Returns:
        bool: True if setup was successful, False otherwise
    """
    try:
        from rich.console import Console, ConsoleThreadLocals

        # Check if already setup
        if hasattr(ConsoleThreadLocals, "_langflow_pickle_enabled"):
            logger.debug("Rich pickle support already enabled")
            return True

        # ConsoleThreadLocals pickle methods
        def _console_thread_locals_getstate(self) -> dict[str, Any]:
            """Serialize ConsoleThreadLocals for caching."""
            return {
                "theme_stack": self.theme_stack,
                "buffer": self.buffer.copy() if self.buffer else [],
                "buffer_index": self.buffer_index,
            }

        def _console_thread_locals_setstate(self, state: dict[str, Any]) -> None:
            """Restore ConsoleThreadLocals from cached state."""
            self.theme_stack = state["theme_stack"]
            self.buffer = state["buffer"]
            self.buffer_index = state["buffer_index"]

        # Console pickle methods
        def _console_getstate(self) -> dict[str, Any]:
            """Serialize Console for caching."""
            state = self.__dict__.copy()
            # Remove unpickleable locks
            state.pop("_lock", None)
            state.pop("_record_buffer_lock", None)
            return state

        def _console_setstate(self, state: dict[str, Any]) -> None:
            """Restore Console from cached state."""
            self.__dict__.update(state)
            # Recreate locks
            self._lock = threading.RLock()
            self._record_buffer_lock = threading.RLock()

        # Apply the methods
        ConsoleThreadLocals.__getstate__ = _console_thread_locals_getstate
        ConsoleThreadLocals.__setstate__ = _console_thread_locals_setstate
        Console.__getstate__ = _console_getstate
        Console.__setstate__ = _console_setstate

        # Mark as setup
        ConsoleThreadLocals._langflow_pickle_enabled = True
        Console._langflow_pickle_enabled = True

    except ImportError:
        logger.debug("Rich library not available, pickle support not enabled")
        return False
    except (AttributeError, TypeError) as e:
        logger.warning("Failed to setup Rich pickle support: %s", e)
        return False
    else:
        logger.info("Rich pickle support enabled for cache serialization")
        return True


def validate_rich_pickle_support() -> bool:
    """Validate that Rich objects can be pickled successfully.

    Returns:
        bool: True if validation passes, False otherwise
    """
    try:
        import pickle

        from rich.console import Console

        # Test basic serialization
        console = Console()
        test_data = {"console": console, "metadata": {"validator": "langflow_cache", "test_type": "rich_pickle"}}

        # Serialize and deserialize
        pickled = pickle.dumps(test_data)
        restored = pickle.loads(pickled)

        # Verify functionality
        restored_console = restored["console"]
        with restored_console.capture() as capture:
            restored_console.print("validation_test")

        validation_passed = "validation_test" in capture.get()
        if validation_passed:
            logger.debug("Rich pickle validation successful")
        else:
            logger.warning("Rich pickle validation failed - console not functional")
    except (ImportError, AttributeError, TypeError) as e:
        logger.warning("Rich pickle validation failed: %s", e)
        return False
    else:
        return validation_passed


def is_rich_pickle_enabled() -> bool:
    """Check if Rich pickle support is currently enabled.

    Returns:
        bool: True if Rich pickle support is enabled, False otherwise
    """
    try:
        from rich.console import ConsoleThreadLocals

        return hasattr(ConsoleThreadLocals, "_langflow_pickle_enabled")
    except ImportError:
        return False
