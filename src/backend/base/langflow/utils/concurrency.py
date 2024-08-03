import re
import threading
from contextlib import contextmanager
from pathlib import Path
from filelock import FileLock

from platformdirs import user_cache_dir


class KeyedMemoryLockManager:
    """
    A manager for acquiring and releasing memory locks based on a key
    """

    def __init__(self):
        self.locks = {}
        self.global_lock = threading.Lock()

    def _get_lock(self, key: str):
        with self.global_lock:
            if key not in self.locks:
                self.locks[key] = threading.Lock()
            return self.locks[key]

    @contextmanager
    def lock(self, key: str):
        lock = self._get_lock(key)
        lock.acquire()
        try:
            yield
        finally:
            lock.release()


class KeyedWorkerLockManager:
    """
    A manager for acquiring locks between workers based on a key
    """

    def __init__(self):
        self.locks_dir = Path(user_cache_dir("langflow"), ensure_exists=True) / "worker_locks"

    def _validate_key(self, key: str) -> bool:
        """
        Validate that the string only contains alphanumeric characters and underscores.

        Parameters:
        s (str): The string to validate.

        Returns:
        bool: True if the string is valid, False otherwise.
        """
        pattern = re.compile(r"^\w+$")
        return bool(pattern.match(key))

    @contextmanager
    def lock(self, key: str):
        if not self._validate_key(key):
            raise ValueError(f"Invalid key: {key}")

        lock = FileLock(self.locks_dir / key)
        with lock:
            yield
