"""Standalone Stepflow component server for Langflow integration.

Run with: python -m langflow_stepflow.worker
"""

from typing import Any

from stepflow_py.worker import StepflowContext, StepflowServer

from langflow_stepflow.worker.component_tool import component_tool_executor
from langflow_stepflow.worker.core_executor import CoreExecutor
from langflow_stepflow.worker.custom_code_executor import CustomCodeExecutor

# Create server instance
server = StepflowServer()

# Create executors
custom_code_executor = CustomCodeExecutor()
core_executor = CoreExecutor()


@server.component(name="custom_code")
async def custom_code_component(
    input_data: dict[str, Any], context: StepflowContext
) -> dict[str, Any]:
    """Execute a Langflow custom code component."""
    return await custom_code_executor.execute(input_data, context)


@server.component(name="core/{*component}")
async def core_component(
    input_data: dict[str, Any],
    context: StepflowContext,
    component: str,
) -> dict[str, Any]:
    """Execute a known core Langflow component by module path."""
    return await core_executor.execute(component, input_data, context)


@server.component(name="component_tool")
async def component_tool_component(
    input_data: dict[str, Any], context: StepflowContext
) -> dict[str, Any]:
    """Create tool wrappers from Langflow components."""
    return await component_tool_executor(input_data, context)


def main():
    """Main entry point for the Langflow component server.

    Logging is automatically configured by the SDK via setup_observability().
    Configure via environment variables:
    - STEPFLOW_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, default: INFO)
    - STEPFLOW_LOG_DESTINATION: Log destination (stderr, file, otlp)
    - STEPFLOW_OTLP_ENDPOINT: OTLP endpoint for tracing/logging
    - STEPFLOW_SERVICE_NAME: Service name (default: stepflow-workerthon)
    """
    import asyncio
    import os

    import nest_asyncio  # type: ignore

    from stepflow_py.worker.observability import setup_observability

    setup_observability()

    nest_asyncio.apply()

    if os.environ.get("LANGFLOW_DATABASE_URL"):
        from langflow.services.utils import initialize_services, teardown_services

        asyncio.run(teardown_services())
        asyncio.run(initialize_services())

    asyncio.run(server.run())


if __name__ == "__main__":
    main()
