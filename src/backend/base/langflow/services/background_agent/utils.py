"""Utility functions for background agent execution."""

from uuid import UUID, uuid4

from lfx.log.logger import logger
from sqlmodel import select

from langflow.services.database.models.flow import Flow
from langflow.services.deps import session_scope
from langflow.services.flow.flow_runner import LangflowRunnerExperimental


async def execute_flow_background(
    flow_id: UUID,
    user_id: UUID,
    input_config: dict,
) -> dict:
    """Execute a flow in the background.

    Args:
        flow_id: UUID of the flow to execute
        user_id: UUID of the user
        input_config: Configuration for flow execution including input_value, input_type, etc.

    Returns:
        dict containing execution results
    """
    session_id = str(uuid4())

    try:
        # Get flow from database
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if not flow:
                msg = f"Flow {flow_id} not found"
                raise ValueError(msg)

            flow_dict = {
                "id": str(flow.id),
                "name": flow.name,
                "data": flow.data,
            }

        # Create runner
        runner = LangflowRunnerExperimental(
            should_initialize_db=False,
            disable_logs=False,
        )

        # Execute flow
        input_value = input_config.get("input_value", "")
        input_type = input_config.get("input_type", "chat")
        output_type = input_config.get("output_type", "all")
        tweaks_values = input_config.get("tweaks", None)

        result = await runner.run(
            session_id=session_id,
            flow=flow_dict,
            input_value=input_value,
            input_type=input_type,
            output_type=output_type,
            user_id=str(user_id),
            cleanup=True,
            tweaks_values=tweaks_values,
        )

        await logger.ainfo(f"Background execution completed for flow {flow_id}")

        return {
            "status": "success",
            "session_id": session_id,
            "result": result,
        }

    except ValueError as e:
        await logger.aerror(f"Invalid configuration for flow {flow_id}: {e}")
        raise
    except RuntimeError as e:
        await logger.aerror(f"Runtime error executing flow {flow_id}: {e}")
        raise
    except Exception as e:  # noqa: BLE001
        await logger.aerror(f"Unexpected error executing flow {flow_id}: {e}")
        raise
