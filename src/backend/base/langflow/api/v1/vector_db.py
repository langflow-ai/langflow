"""Vector Database API endpoints for storing and searching flow YAML specifications."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from langflow.api.utils import CurrentActiveUser
from langflow.logging import logger
from langflow.services.vector_database import VectorDatabaseService

router = APIRouter(prefix="/vector-db", tags=["Vector DB"])


# Vector Database Schemas
class StoreFlowRequest(BaseModel):
    """Request model for storing a flow in the vector database."""

    flow_id: str = Field(..., description="Unique flow ID (UUID format)")
    flow_name: str = Field(..., description="Name of the flow")
    yaml_content: str = Field(..., description="The YAML specification content")
    description: str = Field(default="", description="Flow description")
    components: list[str] = Field(default_factory=list, description="List of component types used in the flow")
    tags: list[str] = Field(default_factory=list, description="Tags for filtering and categorization")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "flow_id": "4e910e74-067e-44f9-988a-a0cff09dc57a",
                "flow_name": "EOC Validation Agent",
                "yaml_content": "id: 4e910e74-067e-44f9-988a-a0cff09dc57a\nname: EOC Validation Agent\n...",
                "description": "Validates insurance coverage against EOC documents",
                "components": ["PromptComponent", "AgentComponent", "ChatInput", "ChatOutput"],
                "tags": ["healthcare", "insurance", "validation"]
            }
        }
    )


class StoreFlowResponse(BaseModel):
    """Response model for storing a flow."""

    success: bool = Field(..., description="Whether the flow was stored successfully")
    flow_id: str = Field(..., description="The flow ID that was stored")
    message: str = Field(..., description="Status message")


class SearchFlowsRequest(BaseModel):
    """Request model for searching flows."""

    query: str = Field(..., description="Search query for finding similar flows", min_length=1)
    limit: int = Field(default=5, description="Maximum number of results to return", ge=1, le=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "insurance validation agent",
                "limit": 5
            }
        }
    )


class SearchFlowItem(BaseModel):
    """Individual flow item in search results."""

    flow_id: str = Field(..., description="The flow UUID")
    name: str = Field(..., description="Flow name")
    description: str = Field(..., description="Flow description")
    score: float = Field(..., description="Similarity score (0-1, higher is better)")
    components: list[str] = Field(default_factory=list, description="Component types used")
    tags: list[str] = Field(default_factory=list, description="Flow tags")
    yaml_preview: str = Field(..., description="Preview of the YAML content")


class SearchFlowsResponse(BaseModel):
    """Response model for flow search."""

    query: str = Field(..., description="The search query")
    results: list[SearchFlowItem] = Field(..., description="List of matching flows")
    count: int = Field(..., description="Number of results returned")


class FlowDetailResponse(BaseModel):
    """Response model for getting a specific flow."""

    flow_id: str = Field(..., description="The flow UUID")
    name: str = Field(..., description="Flow name")
    description: str = Field(..., description="Flow description")
    yaml_content: str = Field(..., description="Complete YAML specification")
    components: list[str] = Field(default_factory=list, description="Component types used")
    tags: list[str] = Field(default_factory=list, description="Flow tags")
    created_at: str = Field(..., description="Creation timestamp")
    yaml_length: int = Field(..., description="Length of YAML content")


class DeleteFlowResponse(BaseModel):
    """Response model for deleting a flow."""

    success: bool = Field(..., description="Whether the flow was deleted successfully")
    flow_id: str = Field(..., description="The flow ID that was deleted")
    message: str = Field(..., description="Status message")


@router.post("/store", response_model=StoreFlowResponse, status_code=201)
async def store_flow(
    request: StoreFlowRequest,
    current_user: CurrentActiveUser,
) -> StoreFlowResponse:
    """
    Store a flow YAML specification in the vector database.

    This endpoint stores the flow with its metadata and creates vector embeddings
    for semantic search capabilities.

    Args:
        request: Flow data including ID, name, YAML content, description, etc.
        current_user: Authenticated user

    Returns:
        StoreFlowResponse with success status and flow ID

    Raises:
        HTTPException: 500 if storage fails
    """
    try:
        logger.info(f"Storing flow in vector DB: {request.flow_name} (ID: {request.flow_id})")

        # Initialize vector database service
        service = VectorDatabaseService()

        # Store the flow
        success = service.store_flow(
            flow_id=request.flow_id,
            flow_name=request.flow_name,
            yaml_content=request.yaml_content,
            description=request.description,
            components=request.components,
            tags=request.tags
        )

        if not success:
            logger.error(f"Failed to store flow {request.flow_id} in vector database")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to store flow {request.flow_id} in vector database. Please check logs for details.",
            )

        logger.info(f"Successfully stored flow {request.flow_id} in vector database")
        return StoreFlowResponse(
            success=True,
            flow_id=request.flow_id,
            message=f"Flow '{request.flow_name}' stored successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error storing flow in vector database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while storing flow: {str(e)}",
        ) from e


@router.post("/search", response_model=SearchFlowsResponse)
async def search_flows(
    search_request: SearchFlowsRequest,
    current_user: CurrentActiveUser,
) -> SearchFlowsResponse:
    """
    Search for flows using semantic search.

    This endpoint performs semantic search to find flows similar to the query.
    It uses vector embeddings to match flows by meaning, not just keywords.

    Args:
        search_request: Search request with query and limit
        current_user: Authenticated user (optional)

    Returns:
        SearchFlowsResponse with matching flows and similarity scores

    Raises:
        HTTPException: 500 if search fails
    """
    try:
        logger.info(f"Searching for flows with query: '{search_request.query}' (limit: {search_request.limit})")

        # Initialize vector database service
        service = VectorDatabaseService()

        # Search for flows
        results = service.search_flows(query=search_request.query, limit=search_request.limit)

        # Convert to response format
        search_items = [
            SearchFlowItem(
                flow_id=result["flow_id"],
                name=result["name"],
                description=result["description"],
                score=result["score"],
                components=result["components"],
                tags=result["tags"],
                yaml_preview=result["yaml_preview"],
            )
            for result in results
        ]

        logger.info(f"Found {len(search_items)} matching flows")
        return SearchFlowsResponse(
            query=search_request.query,
            results=search_items,
            count=len(search_items),
        )

    except Exception as e:
        logger.exception(f"Error searching flows: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while searching flows: {str(e)}",
        ) from e


@router.get("/flow/{flow_id}", response_model=FlowDetailResponse)
async def get_flow(
    flow_id: str,
    current_user: CurrentActiveUser,
) -> FlowDetailResponse:
    """
    Get a specific flow by ID.

    Retrieves the complete flow data including full YAML content.

    Args:
        flow_id: The flow UUID
        current_user: Authenticated user

    Returns:
        FlowDetailResponse with complete flow data

    Raises:
        HTTPException: 404 if flow not found, 500 if retrieval fails
    """
    try:
        logger.info(f"Retrieving flow: {flow_id}")

        # Initialize vector database service
        service = VectorDatabaseService()

        # Get the flow
        flow_data = service.get_flow(flow_id)

        if not flow_data:
            logger.warning(f"Flow not found: {flow_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Flow with ID {flow_id} not found in vector database",
            )

        logger.info(f"Successfully retrieved flow: {flow_data.get('name')}")
        return FlowDetailResponse(
            flow_id=flow_data["flow_id"],
            name=flow_data["name"],
            description=flow_data["description"],
            yaml_content=flow_data["yaml_content"],
            components=flow_data["components"],
            tags=flow_data["tags"],
            created_at=flow_data["created_at"],
            yaml_length=flow_data["yaml_length"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error retrieving flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while retrieving flow: {str(e)}",
        ) from e


@router.delete("/flow/{flow_id}", response_model=DeleteFlowResponse)
async def delete_flow(
    flow_id: str,
    current_user: CurrentActiveUser,
) -> DeleteFlowResponse:
    """
    Delete a flow from the vector database.

    Args:
        flow_id: The flow UUID to delete
        current_user: Authenticated user

    Returns:
        DeleteFlowResponse with success status

    Raises:
        HTTPException: 500 if deletion fails
    """
    try:
        logger.info(f"Deleting flow from vector DB: {flow_id}")

        # Initialize vector database service
        service = VectorDatabaseService()

        # Delete the flow
        success = service.delete_flow(flow_id)

        if not success:
            logger.error(f"Failed to delete flow {flow_id} from vector database")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to delete flow {flow_id} from vector database",
            )

        logger.info(f"Successfully deleted flow {flow_id} from vector database")
        return DeleteFlowResponse(
            success=True,
            flow_id=flow_id,
            message=f"Flow {flow_id} deleted successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting flow: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal error while deleting flow: {str(e)}",
        ) from e
