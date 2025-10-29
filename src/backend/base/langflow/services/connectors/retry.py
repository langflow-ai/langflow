"""Retry logic and error handling for connector operations."""

import asyncio
import random
from collections.abc import Callable
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import Any, TypeVar

from lfx.log import logger

T = TypeVar("T")


class ErrorCategory(Enum):
    """Categories of errors for appropriate handling."""

    # Recoverable errors - should retry
    TRANSIENT = "transient"  # Network issues, timeouts
    RATE_LIMIT = "rate_limit"  # API rate limiting
    SERVER_ERROR = "server_error"  # 5xx errors

    # Non-recoverable errors - should not retry
    AUTH_ERROR = "auth_error"  # 401, 403 - needs re-authentication
    NOT_FOUND = "not_found"  # 404 - resource doesn't exist
    VALIDATION_ERROR = "validation_error"  # 400 - bad request
    PERMISSION_ERROR = "permission_error"  # Access denied

    # Special handling
    QUOTA_EXCEEDED = "quota_exceeded"  # Need to wait or upgrade
    MAINTENANCE = "maintenance"  # Provider under maintenance


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
    ):
        """Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay between retries
            exponential_base: Base for exponential backoff
            jitter: Whether to add random jitter to delays
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given attempt number.

        Args:
            attempt: The attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = min(self.initial_delay * (self.exponential_base**attempt), self.max_delay)

        if self.jitter:
            # Add jitter up to 25% of the delay
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)  # Ensure non-negative


def categorize_error(error: Exception) -> ErrorCategory:
    """Categorize an error to determine if it's retryable.

    Args:
        error: The exception to categorize

    Returns:
        ErrorCategory enum value
    """
    error_msg = str(error).lower()
    error_type = type(error).__name__.lower()

    # Check for specific error patterns
    if "rate limit" in error_msg or "429" in error_msg:
        return ErrorCategory.RATE_LIMIT

    if "unauthorized" in error_msg or "401" in error_msg:
        return ErrorCategory.AUTH_ERROR

    if "forbidden" in error_msg or "403" in error_msg:
        return ErrorCategory.PERMISSION_ERROR

    if "not found" in error_msg or "404" in error_msg:
        return ErrorCategory.NOT_FOUND

    if "bad request" in error_msg or "400" in error_msg or "validation" in error_msg:
        return ErrorCategory.VALIDATION_ERROR

    if "quota" in error_msg or "limit exceeded" in error_msg:
        return ErrorCategory.QUOTA_EXCEEDED

    if "maintenance" in error_msg or "unavailable" in error_msg:
        return ErrorCategory.MAINTENANCE

    if any(code in error_msg for code in ["500", "502", "503", "504"]):
        return ErrorCategory.SERVER_ERROR

    # Network and connection errors
    if any(pattern in error_type for pattern in ["timeout", "connection", "network", "oserror", "ioerror"]):
        return ErrorCategory.TRANSIENT

    # Default to transient for unknown errors
    return ErrorCategory.TRANSIENT


def is_retryable(error_category: ErrorCategory) -> bool:
    """Determine if an error category is retryable.

    Args:
        error_category: The error category

    Returns:
        True if the error should be retried
    """
    retryable_categories = {
        ErrorCategory.TRANSIENT,
        ErrorCategory.RATE_LIMIT,
        ErrorCategory.SERVER_ERROR,
        ErrorCategory.MAINTENANCE,
    }
    return error_category in retryable_categories


def with_exponential_backoff(
    config: RetryConfig | None = None,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for adding exponential backoff retry logic to async functions.

    Args:
        config: Retry configuration
        retryable_exceptions: Tuple of exception types to retry

    Returns:
        Decorated function with retry logic
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    error_category = categorize_error(e)

                    if not is_retryable(error_category):
                        logger.error(f"Non-retryable error in {func.__name__}: {error_category.value} - {e}")
                        raise

                    if attempt == config.max_retries:
                        logger.error(f"Max retries ({config.max_retries}) exceeded for {func.__name__}: {e}")
                        raise

                    delay = config.get_delay(attempt)
                    logger.warning(
                        f"Retryable error in {func.__name__} (attempt {attempt + 1}/{config.max_retries + 1}): "
                        f"{error_category.value} - {e}. Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            if last_exception:
                raise last_exception

            # Should never reach here
            msg = f"Unexpected retry logic state in {func.__name__}"
            raise RuntimeError(msg)

        return wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker pattern implementation for preventing cascading failures."""

    class State(Enum):
        """Circuit breaker states."""

        CLOSED = "closed"  # Normal operation
        OPEN = "open"  # Failing, reject all calls
        HALF_OPEN = "half_open"  # Testing if service recovered

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception_types: tuple[type[Exception], ...] = (Exception,),
    ):
        """Initialize circuit breaker.

        Args:
            name: Name for this circuit breaker (for logging)
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception_types: Exceptions that trigger the breaker
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception_types = expected_exception_types

        self.state = self.State.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None
        self.success_count = 0

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to apply circuit breaker to a function."""

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            if not await self.can_execute():
                msg = f"Circuit breaker {self.name} is OPEN"
                raise RuntimeError(msg)

            try:
                result = await func(*args, **kwargs)
                self.on_success()
                return result
            except self.expected_exception_types:
                self.on_failure()
                raise

        return wrapper

    async def can_execute(self) -> bool:
        """Check if the circuit breaker allows execution.

        Returns:
            True if execution is allowed
        """
        if self.state == self.State.CLOSED:
            return True

        if self.state == self.State.OPEN:
            if self._should_attempt_reset():
                self.state = self.State.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} entering HALF_OPEN state")
                return True
            return False

        # HALF_OPEN state
        return True

    def on_success(self):
        """Handle successful execution."""
        if self.state == self.State.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 1:  # Could require multiple successes
                self.state = self.State.CLOSED
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} CLOSED (recovered)")
        elif self.state == self.State.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)

        if self.state == self.State.HALF_OPEN:
            self.state = self.State.OPEN
            self.success_count = 0
            logger.warning(f"Circuit breaker {self.name} OPEN (recovery failed)")
        elif self.failure_count >= self.failure_threshold:
            self.state = self.State.OPEN
            logger.warning(
                f"Circuit breaker {self.name} OPEN (failures: {self.failure_count}/{self.failure_threshold})"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset.

        Returns:
            True if recovery should be attempted
        """
        if not self.last_failure_time:
            return True

        time_since_failure = datetime.now(timezone.utc) - self.last_failure_time
        return time_since_failure.total_seconds() >= self.recovery_timeout

    def reset(self):
        """Manually reset the circuit breaker."""
        self.state = self.State.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        logger.info(f"Circuit breaker {self.name} manually reset")


class CircuitBreakerManager:
    """Manages circuit breakers for different services/providers."""

    def __init__(self):
        """Initialize the circuit breaker manager."""
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker.

        Args:
            name: Name for the circuit breaker
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting recovery

        Returns:
            Circuit breaker instance
        """
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    def reset(self, name: str):
        """Reset a specific circuit breaker.

        Args:
            name: Name of the circuit breaker to reset
        """
        if name in self._breakers:
            self._breakers[name].reset()

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def get_status(self) -> dict[str, str]:
        """Get status of all circuit breakers.

        Returns:
            Dictionary mapping breaker names to their states
        """
        return {name: breaker.state.value for name, breaker in self._breakers.items()}


# Global circuit breaker manager
_circuit_breaker_manager = CircuitBreakerManager()


def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """Get the global circuit breaker manager.

    Returns:
        CircuitBreakerManager instance
    """
    return _circuit_breaker_manager
