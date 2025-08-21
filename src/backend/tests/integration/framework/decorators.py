"""Decorators for integration testing."""

import asyncio
import contextlib
import functools
import os
import time
from collections.abc import Callable

import pytest


def requires_api_key(api_keys: str | list[str] | None = None, env_var: str | None = None) -> Callable:
    """Skip test if required API keys are not available.

    Args:
        api_keys: API key environment variable names to check
        env_var: Single environment variable name (deprecated, use api_keys)

    Example:
        @requires_api_key("OPENAI_API_KEY")
        async def test_openai_component(self):
            ...

        @requires_api_key(["OPENAI_API_KEY", "ANTHROPIC_API_KEY"])
        async def test_multi_llm_component(self):
            ...
    """
    if env_var is not None:
        # Backward compatibility
        api_keys = env_var

    if isinstance(api_keys, str):
        api_keys = [api_keys]

    def decorator(func: Callable) -> Callable:
        # Check if any of the API keys are available
        available_keys = [key for key in api_keys if os.getenv(key)]

        if not available_keys:
            missing_keys = ", ".join(api_keys)
            return pytest.mark.skip(f"API key(s) required: {missing_keys}")(func)

        return pytest.mark.api_key_required(func)

    return decorator


def skip_if_no_env(*env_vars: str, reason: str | None = None) -> Callable:
    """Skip test if environment variables are not set.

    Args:
        *env_vars: Environment variable names to check
        reason: Custom skip reason

    Example:
        @skip_if_no_env("ASTRA_DB_API_ENDPOINT", "ASTRA_DB_APPLICATION_TOKEN")
        async def test_astra_component(self):
            ...
    """

    def decorator(func: Callable) -> Callable:
        missing_vars = [var for var in env_vars if not os.getenv(var)]

        if missing_vars:
            missing_str = ", ".join(missing_vars)
            skip_reason = reason or f"Environment variables required: {missing_str}"
            return pytest.mark.skip(skip_reason)(func)

        return func

    return decorator


def auto_cleanup(*cleanup_funcs: Callable) -> Callable:
    """Automatically run cleanup functions after test completion.

    Args:
        *cleanup_funcs: Functions to call for cleanup

    Example:
        @auto_cleanup(lambda: cleanup_temp_files())
        async def test_file_operations(self):
            # Test code that creates temp files
            ...
            # cleanup_temp_files() will be called automatically
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                finally:
                    for cleanup_func in cleanup_funcs:
                        try:
                            if asyncio.iscoroutinefunction(cleanup_func):
                                await cleanup_func()
                            else:
                                cleanup_func()
                        except Exception:
                            pass

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            finally:
                for cleanup_func in cleanup_funcs:
                    with contextlib.suppress(Exception):
                        cleanup_func()

        return sync_wrapper

    return decorator


def leak_detection(enable_task_tracking: bool = True, thread_name_filter: str = r"^(?!asyncio_\d+$).*") -> Callable:
    """Enable memory leak detection for the test.

    Args:
        enable_task_tracking: Enable asyncio task creation tracking
        thread_name_filter: Regex filter for thread names to monitor

    Example:
        @leak_detection()
        async def test_component_memory_usage(self):
            # Test will fail if it leaks memory
            ...
    """

    def decorator(func: Callable) -> Callable:
        # For now, just return the function without leak detection
        # TODO: Fix pyleak integration
        return func

    return decorator


def timeout(seconds: float) -> Callable:
    """Set timeout for test execution.

    Args:
        seconds: Timeout in seconds

    Example:
        @timeout(30.0)
        async def test_slow_operation(self):
            ...
    """
    return pytest.mark.timeout(seconds)


def benchmark(name: str | None = None) -> Callable:
    """Mark test as a benchmark test.

    Args:
        name: Custom benchmark name

    Example:
        @benchmark("component_loading")
        async def test_component_loading_performance(self):
            ...
    """

    def decorator(func: Callable) -> Callable:
        benchmark_name = name or func.__name__
        return pytest.mark.benchmark(benchmark_name)(func)

    return decorator


def parametrize_components(*component_classes) -> Callable:
    """Parametrize test to run with multiple component classes.

    Args:
        *component_classes: Component classes to test

    Example:
        @parametrize_components(ChatInput, TextInput, FileInput)
        async def test_input_components(self, component_class):
            result = await self.run_component_class(component_class)
            assert result is not None
    """
    return pytest.mark.parametrize("component_class", component_classes)


def retry(max_attempts: int = 3, delay: float = 1.0) -> Callable:
    """Retry test on failure.

    Args:
        max_attempts: Maximum retry attempts
        delay: Delay between attempts in seconds

    Example:
        @retry(max_attempts=3, delay=2.0)
        async def test_flaky_external_api(self):
            # Test that might fail due to external factors
            ...
    """

    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exception = None
                for attempt in range(max_attempts):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_attempts - 1:
                            await asyncio.sleep(delay)
                        continue
                raise last_exception

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay)
                    continue
            raise last_exception

        return sync_wrapper

    return decorator


def skip_in_ci(reason: str = "Test skipped in CI environment") -> Callable:
    """Skip test when running in CI environment.

    Args:
        reason: Skip reason

    Example:
        @skip_in_ci("Test requires local services")
        async def test_local_service_integration(self):
            ...
    """
    is_ci = any(os.getenv(var) for var in ["CI", "GITHUB_ACTIONS", "TRAVIS", "JENKINS_URL"])

    def decorator(func: Callable) -> Callable:
        if is_ci:
            return pytest.mark.skip(reason)(func)
        return func

    return decorator


def requires_docker(reason: str = "Test requires Docker") -> Callable:
    """Skip test if Docker is not available.

    Args:
        reason: Skip reason

    Example:
        @requires_docker()
        async def test_containerized_service(self):
            ...
    """

    def decorator(func: Callable) -> Callable:
        try:
            import docker

            client = docker.from_env()
            client.ping()
            return func
        except Exception:
            return pytest.mark.skip(reason)(func)

    return decorator
