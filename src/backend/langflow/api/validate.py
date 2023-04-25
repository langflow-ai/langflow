from fastapi import APIRouter, HTTPException

from langflow.api.base import (
    Code,
    CodeValidationResponse,
    Prompt,
    PromptValidationResponse,
    validate_prompt,
)
from langflow.interface.run import build_graph
from langflow.utils.logger import logger
from langflow.utils.validate import validate_code

# build router
router = APIRouter(prefix="/validate", tags=["validate"])


@router.post("/code", status_code=200, response_model=CodeValidationResponse)
def post_validate_code(code: Code):
    try:
        errors = validate_code(code.code)
        return CodeValidationResponse(
            imports=errors.get("imports", {}),
            function=errors.get("function", {}),
        )
    except Exception as e:
        return HTTPException(status_code=500, detail=str(e))


@router.post("/prompt", status_code=200, response_model=PromptValidationResponse)
def post_validate_prompt(prompt: Prompt):
    try:
        return validate_prompt(prompt.template)
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


# validate node
@router.post("/node/{node_id}", status_code=200)
def post_validate_node(node_id: str, data: dict):
    try:
        # build graph
        graph = build_graph(data)
        # validate node
        node = graph.get_node(node_id)
        if node is not None:
            _ = node.build()
            return str(node.params)
        raise Exception(f"Node {node_id} not found")
    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e)) from e
