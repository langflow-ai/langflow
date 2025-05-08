import asyncio
import gc
import logging
import sys
import threading

import pytest


@pytest.mark.asyncio
async def test_mcp_component():
    """Test MCP component with default event loop policy for subprocess support."""
    logging.debug("Starting MCP component integration test")
    from langflow.components.tools.mcp_component import MCPToolsComponent

    # Store the original policy
    original_policy = asyncio.get_event_loop_policy()
    logging.debug("Original event loop policy: %s", original_policy.__class__.__name__)

    # Check if we're using uvloop
    using_uvloop = False
    if (
        "uvloop" in sys.modules
        and hasattr(original_policy, "__class__")
        and "uvloop" in original_policy.__class__.__module__
    ):
        using_uvloop = True
        logging.debug("Detected uvloop is being used")
    else:
        logging.debug("uvloop is not being used")

    # Track child processes for cleanup
    child_processes = []
    old_loop = None

    try:
        # Only switch if using uvloop
        if using_uvloop:
            logging.debug("Switching from uvloop to default event loop policy")
            # Switch to default policy that supports subprocesses
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

            # We also need a new event loop under the new policy
            old_loop = asyncio.get_event_loop()
            logging.debug("Original loop: %s", old_loop)
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            logging.debug("Created and set new loop: %s", new_loop)

        # Patch subprocess creation to track child processes
        original_create_subprocess_exec = asyncio.create_subprocess_exec

        async def patched_create_subprocess_exec(*args, **kwargs):
            proc = await original_create_subprocess_exec(*args, **kwargs)
            child_processes.append(proc)
            return proc

        asyncio.create_subprocess_exec = patched_create_subprocess_exec

        logging.debug("About to run the component with run_single_component")
        inputs = {}

        from tests.integration.utils import run_single_component

        result = await run_single_component(
            MCPToolsComponent,
            inputs=inputs,  # test default inputs
        )

        # Verify the component ran
        logging.debug("Component ran successfully, result: %s", result)
        assert result is not None
    finally:
        logging.debug("Starting comprehensive cleanup")

        # Clean up any child processes we tracked
        for proc in child_processes:
            if proc.returncode is None:
                try:
                    logging.debug("Terminating subprocess with PID %d", proc.pid)
                    proc.terminate()
                    await asyncio.wait_for(proc.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    logging.debug("Killing subprocess with PID %d", proc.pid)
                    proc.kill()
                except Exception as e:  # noqa: BLE001
                    logging.debug("Error cleaning up subprocess: %s", e)

        # Reset subprocess function
        if "original_create_subprocess_exec" in locals():
            asyncio.create_subprocess_exec = original_create_subprocess_exec

        # Clean up threads
        for t in threading.enumerate():
            if t.name in ["PrometheusMetricsServer", "OtelBatchSpanProcessor"] and t.is_alive():
                logging.debug("Found running thread: %s, attempting to clean up", t.name)
                # We can't forcibly kill threads in Python, but we can try to shut them down gracefully

        # Run garbage collection to help release resources
        gc.collect()

        # Restore the original policy and loop if we changed them
        if using_uvloop:
            logging.debug("Restoring original event loop and policy")
            asyncio.set_event_loop(old_loop)
            asyncio.set_event_loop_policy(original_policy)

        logging.debug("Completed MCP component integration test")
