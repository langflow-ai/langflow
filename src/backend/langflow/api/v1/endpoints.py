from langflow.database.models.flow import Flow
from langflow.processing.process import process_graph_cached, process_tweaks
from langflow.utils.logger import logger
from langflow.api.extract_info_from_class import (
    ClassCodeExtractor,
    is_valid_class_template
)
from fastapi import APIRouter, Depends, HTTPException

from langflow.api.v1.schemas import (
    PredictRequest,
    PredictResponse,
    CustomComponentCode,
    CustomComponentResponse
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


@router.post("/predict/{flow_id}", response_model=PredictResponse)
async def predict_flow(
    predict_request: PredictRequest,
    flow_id: str,
    session: Session = Depends(get_session),
):
    """
    Endpoint to process a message using the flow passed in the bearer token.
    """

    try:
        flow = session.get(Flow, flow_id)
        if flow is None:
            raise ValueError(f"Flow {flow_id} not found")

        if flow.data is None:
            raise ValueError(f"Flow {flow_id} has no data")
        graph_data = flow.data
        if predict_request.tweaks:
            try:
                graph_data = process_tweaks(graph_data, predict_request.tweaks)
            except Exception as exc:
                logger.error(f"Error processing tweaks: {exc}")
        response = process_graph_cached(graph_data, predict_request.message)
        return PredictResponse(
            result=response.get("result", ""),
            intermediate_steps=response.get("thought", ""),
        )
    except Exception as e:
        # Log stack trace
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# get endpoint to return version of langflow
@router.get("/version")
def get_version():
    from langflow import __version__

    return {"version": __version__}


# @router.post("/custom_component", response_model=CustomComponentResponse, status_code=200)
@router.post("/custom_component", status_code=200)
def custom_component(
    code: CustomComponentCode,
    session: Session = Depends(get_session),
):
    code_test = """
from langflow.interface.chains.base import ChainCreator
from langflow.interface.tools.base import ToolCreator


class MyPythonClass():
    def __init__(self, title: str, author: str, year_published: int):
        self.title = title
        self.author = author
        self.year_published = year_published

    def get_details(self):
        return f"Title: {self.title}, Author: {self.author}, Year Published: {self.year_published}"

    def update_year_published(self, new_year: int):
        self.year_published = new_year
        print(f"The year of publication has been updated to {new_year}.")

    def build(self, name: str, id: int, other: str) -> ChainCreator:
        return ChainCreator()
"""

    extractor = ClassCodeExtractor(code_test)
    data = extractor.extract_class_info()
    valid = is_valid_class_template(data)

    function_args, function_return_type = extractor.get_entrypoint_function_args_and_return_type()

    return build_langchain_template_custom_component(
        code_test,
        function_args,
        function_return_type
    )
