import json

from fastapi import APIRouter, HTTPException

from langflow.api.v1.base import (
    Code,
    CodeValidationResponse,
    Prompt,
    PromptValidationResponse,
    validate_prompt,
)
from langflow.graph.vertex.types import VectorStoreVertex
from langflow.graph import Graph
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
        graph = Graph.from_payload(data)
        # validate node
        node = graph.get_node(node_id)
        if node is None:
            raise ValueError(f"Node {node_id} not found")
        if not isinstance(node, VectorStoreVertex):
            node.build()
        return json.dumps({"valid": True, "params": str(node._built_object_repr())})
    except Exception as e:
        logger.exception(e)
        return json.dumps({"valid": False, "params": str(e)})
