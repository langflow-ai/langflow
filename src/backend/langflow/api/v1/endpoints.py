import random

from http import HTTPStatus
from typing import Optional
from langflow.cache.utils import save_uploaded_file
from langflow.database.models.flow import Flow
from langflow.processing.process import process_graph_cached, process_tweaks
from langflow.utils.logger import logger

from fastapi import APIRouter, Depends, HTTPException, UploadFile

# from langflow.api.extract_info_from_class import (
#     ClassCodeExtractor,
#     is_valid_class_template
# )

from langflow.interface.tools.custom import CustomComponent

from langflow.api.v1.schemas import (
    ProcessResponse,
    UploadFileResponse,
    CustomComponentCode,
    CustomComponentResponseError,
)

from langflow.interface.types import (
    build_langchain_types_dict,
    build_langchain_template_custom_component
)

from langflow.database.base import get_session
from sqlmodel import Session

# build router
router = APIRouter(tags=["Base"])


@router.get("/all")
def get_all():
    return build_langchain_types_dict()


# For backwards compatibility we will keep the old endpoint
@router.post("/predict/{flow_id}", response_model=ProcessResponse)
@router.post("/process/{flow_id}", response_model=ProcessResponse)
async def process_flow(
    flow_id: str,
    inputs: Optional[dict] = None,
    tweaks: Optional[dict] = None,
    session: Session = Depends(get_session),
):
    """
    Endpoint to process an input with a given flow_id.
    """

    try:
        flow = session.get(Flow, flow_id)
        if flow is None:
            raise ValueError(f"Flow {flow_id} not found")

        if flow.data is None:
            raise ValueError(f"Flow {flow_id} has no data")
        graph_data = flow.data
        if tweaks:
            try:
                graph_data = process_tweaks(graph_data, tweaks)
            except Exception as exc:
                logger.error(f"Error processing tweaks: {exc}")
        response = process_graph_cached(graph_data, inputs)
        return ProcessResponse(
            result=response,
        )
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/upload/{flow_id}", response_model=UploadFileResponse, status_code=HTTPStatus.CREATED)
async def create_upload_file(file: UploadFile, flow_id: str):
    # Cache file
    try:
        file_path = save_uploaded_file(file.file, folder_name=flow_id)

        return UploadFileResponse(
            flowId=flow_id,
            file_path=file_path,
        )
    except Exception as exc:
        logger.error(f"Error saving file: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


# get endpoint to return version of langflow
@router.get("/version")
def get_version():
    from langflow import __version__

    return {"version": __version__}


@router.post("/custom_component", status_code=HTTPStatus.OK)
async def custom_component(
    raw_code: CustomComponentCode,
):
    extractor = CustomComponent(code=raw_code.code)

    if not extractor.is_valid:
        print("ERROR")
        # TODO: Raise error

    return build_langchain_template_custom_component(extractor)


# TODO: Just for test - will be remove
@router.get("/custom_component_error",
            response_model=CustomComponentResponseError,
            status_code=HTTPStatus.BAD_REQUEST)
async def custom_component_error():
    error1 = {
        "detail": "'int' object has no attribute 'get'",
        "traceback": "Traceback (most recent call last):\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/errors.py\", line 162, in __call__\n    await self.app(scope, receive, _send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/cors.py\", line 83, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 79, in __call__\n    raise exc\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 68, in __call__\n    await self.app(scope, receive, sender)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 20, in __call__\n    raise e\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 17, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 718, in __call__\n    await route.handle(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 276, in handle\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 66, in app\n    response = await func(request)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 241, in app\n    raw_response = await run_endpoint_function(\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 167, in run_endpoint_function\n    return await dependant.call(**values)\n  File \"/Users/gustavopoa/Documents/Langspace/langflow/src/backend/langflow/api/v1/endpoints.py\", line 124, in custom_component_error\n    c = x.get(\"a\")\nAttributeError: 'int' object has no attribute 'get'\n"
    }

    error2 = {
        "detail": "division by zero",
        "traceback": "Traceback (most recent call last):\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/errors.py\", line 162, in __call__\n    await self.app(scope, receive, _send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/cors.py\", line 83, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 79, in __call__\n    raise exc\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 68, in __call__\n    await self.app(scope, receive, sender)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 20, in __call__\n    raise e\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 17, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 718, in __call__\n    await route.handle(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 276, in handle\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 66, in app\n    response = await func(request)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 241, in app\n    raw_response = await run_endpoint_function(\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 167, in run_endpoint_function\n    return await dependant.call(**values)\n  File \"/Users/gustavopoa/Documents/Langspace/langflow/src/backend/langflow/api/v1/endpoints.py\", line 130, in custom_component_error\n    return 1/0\nZeroDivisionError: division by zero\n"
    }

    error3 = {
        "detail": "name 'CreateObject' is not defined",
        "traceback": "Traceback (most recent call last):\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/errors.py\", line 162, in __call__\n    await self.app(scope, receive, _send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/cors.py\", line 83, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 79, in __call__\n    raise exc\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/middleware/exceptions.py\", line 68, in __call__\n    await self.app(scope, receive, sender)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 20, in __call__\n    raise e\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/middleware/asyncexitstack.py\", line 17, in __call__\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 718, in __call__\n    await route.handle(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 276, in handle\n    await self.app(scope, receive, send)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/starlette/routing.py\", line 66, in app\n    response = await func(request)\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 241, in app\n    raw_response = await run_endpoint_function(\n  File \"/Users/gustavopoa/Library/Caches/pypoetry/virtualenvs/langflow-3LyDxlRJ-py3.10/lib/python3.10/site-packages/fastapi/routing.py\", line 167, in run_endpoint_function\n    return await dependant.call(**values)\n  File \"/Users/gustavopoa/Documents/Langspace/langflow/src/backend/langflow/api/v1/endpoints.py\", line 130, in custom_component_error\n    error3 = CreateObject()\nNameError: name 'CreateObject' is not defined\n"
    }

    error = [error1, error2, error3]

    return error[random.randint(0, 2)]
