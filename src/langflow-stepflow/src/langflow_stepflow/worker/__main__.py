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
async def custom_code_component(input_data: dict[str, Any], context: StepflowContext) -> dict[str, Any]:
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
async def component_tool_component(input_data: dict[str, Any], context: StepflowContext) -> dict[str, Any]:
    """Create tool wrappers from Langflow components."""
    return await component_tool_executor(input_data, context)


def main():
    """Main entry point for the Langflow component server.

    Logging is automatically configured by the SDK via setup_observability().
    Configure via environment variables:
    - STEPFLOW_TASKS_URL: TasksService gRPC address (default: localhost:7837)
    - STEPFLOW_QUEUE_NAME: Queue name for gRPC transport (default: langflow)
    - STEPFLOW_MAX_CONCURRENT: Max concurrent tasks (default: 4)
    - STEPFLOW_LOG_LEVEL: Log level (DEBUG, INFO, WARNING, ERROR, default: INFO)
    - STEPFLOW_LOG_DESTINATION: Log destination (stderr, file, otlp)
    - STEPFLOW_OTLP_ENDPOINT: OTLP endpoint for tracing/logging
    - STEPFLOW_SERVICE_NAME: Service name (default: stepflow-python)
    """
    import argparse
    import asyncio
    import os

    import nest_asyncio  # type: ignore
    from stepflow_py.worker.observability import setup_observability

    setup_observability()

    nest_asyncio.apply()

    if os.environ.get("LANGFLOW_DATABASE_URL"):
        from langflow.services.utils import initialize_services, teardown_services

        # Teardown first to clear any stale state from a previous run,
        # then initialize fresh services for this worker process.
        asyncio.run(teardown_services())
        asyncio.run(initialize_services())

    parser = argparse.ArgumentParser(description="Langflow Stepflow Component Server")
    parser.add_argument(
        "--tasks-url",
        type=str,
        default=os.environ.get("STEPFLOW_TASKS_URL", "localhost:7837"),
        help="TasksService gRPC address (env: STEPFLOW_TASKS_URL)",
    )
    parser.add_argument(
        "--queue-name",
        type=str,
        default=os.environ.get("STEPFLOW_QUEUE_NAME", "langflow"),
        help="Queue name for gRPC transport (env: STEPFLOW_QUEUE_NAME)",
    )
    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=int(os.environ.get("STEPFLOW_MAX_CONCURRENT", "4")),
        help="Max concurrent tasks (env: STEPFLOW_MAX_CONCURRENT)",
    )
    args = parser.parse_args()

    from stepflow_py.worker.grpc_worker import run_grpc_worker

    asyncio.run(
        run_grpc_worker(
            server=server,
            tasks_url=args.tasks_url,
            queue_name=args.queue_name,
            max_concurrent=args.max_concurrent,
        )
    )


if __name__ == "__main__":
    main()
