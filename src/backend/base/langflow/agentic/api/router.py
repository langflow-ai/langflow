"""Agentic API router."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from lfx.log.logger import logger
from lfx.run.base import run_flow

from langflow.api.utils import CurrentActiveUser, DbSession
from langflow.services.deps import get_variable_service
from langflow.services.variable.service import DatabaseVariableService
from pydantic import BaseModel


class FlowRequest(BaseModel):
    flow_id: str
    component_id: str | None = None
    field_name: str | None = None
    input_value: str | None = None


router = APIRouter(prefix="/agentic", tags=["Agentic"])


async def get_openai_api_key(variable_service: DatabaseVariableService, user_id: UUID | str, session) -> str:
    """Get OPENAI_API_KEY from Langflow global variables."""
    try:
        return await variable_service.get_variable(user_id, "OPENAI_API_KEY", "", session)
    except ValueError as e:
        logger.error(f"Failed to retrieve OPENAI_API_KEY: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve OPENAI_API_KEY: {e}") from e


@router.post("/prompt")
async def run_prompt_flow(
    request: FlowRequest,
    current_user: CurrentActiveUser,
    session: DbSession
) -> dict:
    """Execute the prompt flow with provided parameters."""
    variable_service = get_variable_service()

    # Get OPENAI_API_KEY from global variables
    user_id = current_user.id
    logger.debug(f"USER ID: {user_id}")
    openai_key = await get_openai_api_key(variable_service, user_id, session)

    # Prepare global variables
    global_vars = {
        "FLOW_ID": request.flow_id,
        "OPENAI_API_KEY": openai_key,
        "USER_ID": str(user_id)
    }
    if request.component_id:
        global_vars["COMPONENT_ID"] = request.component_id
    if request.field_name:
        global_vars["FIELD_NAME"] = request.field_name

    logger.debug(f"GLOBAL VARIABLES: {global_vars}")
    # Path to the flow file
    flow_path = Path(__file__).parent.parent / "flows" / "LFX_TEST3.json"
    logger.debug(f"FLOW PATH: {flow_path}")
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow {request.flow_id} not found")
    try:
        # Execute the flow using run_flow
        logger.debug(f"Executing flow: {flow_path}")
        result = await run_flow(
            script_path=flow_path,
            input_value=request.input_value,
            global_variables=global_vars,
            verbose=False,
            check_variables=False
        )
        logger.debug("Flow execution completed")
        return result

    except Exception as e:
        logger.error(f"Error executing flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e


@router.post("/next_component")
async def run_next_component_flow(
    request: FlowRequest,
    current_user: CurrentActiveUser,
    session: DbSession
) -> dict:
    """Execute the next component flow with provided parameters."""
    variable_service = get_variable_service()

    # Get OPENAI_API_KEY from global variables
    user_id = current_user.id
    openai_key = await get_openai_api_key(variable_service, user_id, session)

    # Prepare global variables
    global_vars = {
        "FLOW_ID": request.flow_id,
        "OPENAI_API_KEY": openai_key,
        "USER_ID": str(user_id)
    }
    if request.component_id:
        global_vars["COMPONENT_ID"] = request.component_id
    if request.field_name:
        global_vars["FIELD_NAME"] = request.field_name

    # Path to the flow file
    flow_path = Path(__file__).parent.parent / "flows" / f"{request.flow_id}.json"
    if not flow_path.exists():
        raise HTTPException(status_code=404, detail=f"Flow {request.flow_id} not found")

    try:
        # Execute the flow using run_flow
        logger.debug(f"Executing flow: {flow_path}")
        result = await run_flow(
            script_path=flow_path,
            input_value=request.input_value,
            global_variables=global_vars,
            verbose=False,
            check_variables=False
        )
        logger.debug("Flow execution completed")
        return result

    except Exception as e:
        logger.error(f"Error executing flow: {e}")
        raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e


if __name__ == "__main__":
    import asyncio
    flow_path = Path(__file__).parent.parent / "flows" / "LFX_TEST3.json"
    logger.debug(f"FLOW PATH: {flow_path}")

    async def main():
        try:
            # Execute the flow
            result = await run_flow(
                script_path=flow_path,
                input_value=None,
                global_variables={
                    "FLOW_ID": "LFX_TEST3",
                    "OPENAI_API_KEY": "sk-proj-1234567890",
                },
                verbose=True,
                check_variables=False
            )
            print(f"Result: {result}")
        except Exception as e:
            logger.error(f"Error executing flow: {e}")
            raise HTTPException(status_code=500, detail=f"Error executing flow: {e}") from e

    asyncio.run(main())