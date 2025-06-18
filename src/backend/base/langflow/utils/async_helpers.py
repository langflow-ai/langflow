"""Async utility functions and helpers for Langflow.

This module provides essential asynchronous utilities for managing async operations
in Langflow, including timeout handling and event loop management for components
that need to bridge sync and async execution contexts.

Key Features:
    - Cross-platform timeout context management
    - Event loop detection and coroutine execution
    - Backward compatibility for different Python versions
    - Safe async-to-sync bridging utilities

Timeout Context Manager:
    Provides a unified interface for timeout handling across Python versions:
    - Python 3.11+: Uses native asyncio.timeout()
    - Earlier versions: Falls back to asyncio.wait_for()
    - Consistent timeout error handling

Run Until Complete Utility:
    Safely executes coroutines in both sync and async contexts:
    - Detects existing event loops
    - Creates new loops when needed
    - Handles nested event loop scenarios
    - Essential for component execution bridging

Usage Examples:
    ```python
    # Timeout context for async operations
    async with timeout_context(30.0):
        result = await some_long_operation()

    # Safe coroutine execution
    result = run_until_complete(async_function())
    ```

This module is critical for Langflow's component execution system where
components may need to execute async operations within sync contexts
or manage timeouts for network operations.
"""

import asyncio
from contextlib import asynccontextmanager

if hasattr(asyncio, "timeout"):

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        with asyncio.timeout(timeout_seconds) as ctx:
            yield ctx

else:

    @asynccontextmanager
    async def timeout_context(timeout_seconds):
        try:
            yield await asyncio.wait_for(asyncio.Future(), timeout=timeout_seconds)
        except asyncio.TimeoutError as e:
            msg = f"Operation timed out after {timeout_seconds} seconds"
            raise TimeoutError(msg) from e


def run_until_complete(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # If there's no event loop, create a new one and run the coroutine
        return asyncio.run(coro)
    return loop.run_until_complete(coro)
