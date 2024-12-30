import asyncio
import contextvars
import logging
from weakref import WeakKeyDictionary


class AsyncRLock:
    """An asyncio-based reentrant lock implementation.

    This lock can be acquired multiple times by the same task without blocking.
    The lock must be released as many times as it was acquired.

    Attributes:
        _lock (asyncio.Lock): The underlying asyncio Lock
        _owner (contextvars.ContextVar): The task that currently owns the lock
        _count (int): Number of times the lock has been acquired by the current owner
        _debug (bool): Whether to enable debug logging
        _pending_tasks (WeakKeyDictionary): Tasks waiting to acquire the lock
    """

    def __init__(self, *, debug: bool = False):
        self._lock = asyncio.Lock()
        self._owner = contextvars.ContextVar("lock_owner", default=None)
        self._count = 0
        self._debug = debug
        self._pending_tasks: WeakKeyDictionary = WeakKeyDictionary()
        self._logger = logging.getLogger(__name__)
        if debug:
            self._logger.setLevel(logging.DEBUG)

    @property
    def locked(self) -> bool:
        """Check if the lock is currently held by any task."""
        return self._lock.locked()

    def get_owner(self) -> asyncio.Task | None:
        """Get the task that currently owns the lock."""
        return self._owner.get()

    async def acquire(self) -> bool:
        """Acquire the lock.

        If the lock is already held by the current task, increment the counter.
        Otherwise, wait for the lock to be released.

        Returns:
            bool: True if the lock was acquired, False if it timed out

        Raises:
            RuntimeError: If there's an attempt to acquire the lock from a non-Task context
        """
        current_task = asyncio.current_task()
        if current_task is None:
            msg = "Cannot acquire lock from non-Task context"
            raise RuntimeError(msg)

        if self._debug:
            self._logger.debug(
                "Task %s attempting to acquire lock. Current owner: %s, Count: %d",
                current_task.get_name(),
                self.get_owner(),
                self._count,
            )

        if self._owner.get() == current_task:
            # The lock is already held by this task
            self._count += 1
            if self._debug:
                self._logger.debug(
                    "Task %s reacquired lock. New count: %d",
                    current_task.get_name(),
                    self._count,
                )
            return True

        # Track that this task is waiting for the lock
        self._pending_tasks[current_task] = True
        try:
            # Wait for the lock to become available
            await self._lock.acquire()
            self._owner.set(current_task)
            self._count = 1
            if self._debug:
                self._logger.debug(
                    "Task %s acquired lock. Count: %d",
                    current_task.get_name(),
                    self._count,
                )
            return True
        finally:
            # Remove the task from pending regardless of success/failure
            self._pending_tasks.pop(current_task, None)

    def release(self) -> None:
        """Release the lock.

        The lock can only be released by the task that holds it.
        The lock must be released as many times as it was acquired.

        Raises:
            RuntimeError: If the current task doesn't own the lock or if called from a non-Task context
        """
        current_task = asyncio.current_task()
        if current_task is None:
            msg = "Cannot release lock from non-Task context"
            raise RuntimeError(msg)

        if self._owner.get() != current_task:
            msg = f"Cannot release lock owned by {self.get_owner()} " f"from task {current_task.get_name()}"
            raise RuntimeError(msg)

        self._count -= 1
        if self._debug:
            self._logger.debug(
                "Task %s releasing lock. New count: %d",
                current_task.get_name(),
                self._count,
            )

        if self._count == 0:
            self._owner.set(None)
            self._lock.release()
        elif self._count < 0:
            # This should never happen if used correctly
            self._count = 0
            self._owner.set(None)
            self._lock.release()
            msg = "Lock released more times than acquired"
            raise RuntimeError(msg)

    def get_waiters_count(self) -> int:
        """Get the number of tasks waiting to acquire this lock."""
        return len(self._pending_tasks)

    async def __aenter__(self) -> "AsyncRLock":
        """Async context manager entry."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        """Async context manager exit."""
        self.release()

    def __repr__(self) -> str:
        """Return a string representation of the lock state."""
        return (
            f"<{self.__class__.__name__} locked={self.locked} "
            f"owner={self.get_owner()} count={self._count} "
            f"waiters={self.get_waiters_count()}>"
        )
