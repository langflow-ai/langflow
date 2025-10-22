"""
Model Catalog API endpoints for AI Studio - AUTPE-6205.

This module provides REST API endpoints for querying available models,
including Autonomize models and their variants.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field

from langflow.services.model_catalog import ModelCatalogService
from langflow.services.deps import get_model_catalog_service

# Create router
router = APIRouter(prefix="/models", tags=["Models"])


class ModelResponse(BaseModel):
    """Response model for a single model."""

    id: str = Field(..., description="Unique model identifier")
    name: str = Field(..., description="Model name")
    display_name: str = Field(..., description="Display name for UI")
    type: str = Field(..., description="Model type (text, document, embedding, etc.)")
    category: str = Field(..., description="Model category (healthcare, general, etc.)")
    provider: str = Field(..., description="Model provider (autonomize, openai, etc.)")
    description: str = Field(..., description="Model description")
    input_types: List[str] = Field(default_factory=list, description="Supported input types")
    output_types: List[str] = Field(default_factory=list, description="Supported output types")
    supported_formats: List[str] = Field(default_factory=list, description="Supported file formats")
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="Model capabilities")
    healthcare_metadata: Optional[Dict[str, Any]] = Field(None, description="Healthcare compliance metadata")
    config_options: Dict[str, Any] = Field(default_factory=dict, description="Configuration options")
    version: str = Field(default="1.0.0", description="Model version")
    active: bool = Field(default=True, description="Whether model is active")
    beta: bool = Field(default=False, description="Whether model is in beta")


class ModelCatalogResponse(BaseModel):
    """Response model for the model catalog."""

    models: List[ModelResponse] = Field(..., description="List of available models")
    total: int = Field(..., description="Total number of models")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Catalog statistics")


class ModelSearchResponse(BaseModel):
    """Response model for model search results."""

    models: List[ModelResponse] = Field(..., description="Search results")
    query: str = Field(..., description="Search query")
    total: int = Field(..., description="Total results")


@router.get("/catalog", response_model=ModelCatalogResponse)
async def get_model_catalog(
    type: Optional[str] = Query(None, description="Filter by model type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    active_only: bool = Query(True, description="Return only active models"),
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> ModelCatalogResponse:
    """
    Get the complete model catalog with optional filtering.

    This endpoint returns all available models that can be used in agent specifications.
    You can filter by type, category, provider, or active status.

    Args:
        type: Optional filter by model type (text, document, embedding, etc.)
        category: Optional filter by category (healthcare, general, vision, etc.)
        provider: Optional filter by provider (autonomize, openai, anthropic, etc.)
        active_only: Whether to return only active models (default: true)

    Returns:
        ModelCatalogResponse containing list of models and statistics
    """
    try:
        # Get filtered models
        models = model_catalog_service.get_all_models(
            filter_by_type=type,
            filter_by_category=category,
            filter_by_provider=provider,
            active_only=active_only
        )

        # Get statistics
        statistics = model_catalog_service.get_catalog_statistics()

        # Convert to response format
        model_responses = [
            ModelResponse(**model.to_dict())
            for model in models
        ]

        return ModelCatalogResponse(
            models=model_responses,
            total=len(model_responses),
            statistics=statistics
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving model catalog: {str(e)}")


@router.get("/catalog/{model_id}", response_model=ModelResponse)
async def get_model_by_id(
    model_id: str,
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> ModelResponse:
    """
    Get detailed information about a specific model.

    Args:
        model_id: The unique identifier of the model

    Returns:
        ModelResponse with detailed model information
    """
    model = model_catalog_service.get_model_by_id(model_id)

    if not model:
        raise HTTPException(status_code=404, detail=f"Model with ID '{model_id}' not found")

    return ModelResponse(**model.to_dict())


@router.get("/search", response_model=ModelSearchResponse)
async def search_models(
    q: str = Query(..., min_length=1, description="Search query"),
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> ModelSearchResponse:
    """
    Search for models by name or description.

    Args:
        q: Search query (searches in name, display_name, and description)

    Returns:
        ModelSearchResponse with matching models
    """
    try:
        results = model_catalog_service.search_models(q)

        model_responses = [
            ModelResponse(**model.to_dict())
            for model in results
        ]

        return ModelSearchResponse(
            models=model_responses,
            query=q,
            total=len(model_responses)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching models: {str(e)}")


@router.get("/by-capability/{capability}", response_model=List[ModelResponse])
async def get_models_by_capability(
    capability: str,
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> List[ModelResponse]:
    """
    Get all models that have a specific capability.

    Args:
        capability: The capability to filter by (e.g., 'entity_extraction', 'image_analysis')

    Returns:
        List of models with the specified capability
    """
    models = model_catalog_service.get_models_by_capability(capability)

    return [
        ModelResponse(**model.to_dict())
        for model in models
    ]


@router.get("/healthcare-compliant", response_model=List[ModelResponse])
async def get_healthcare_compliant_models(
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> List[ModelResponse]:
    """
    Get all HIPAA-compliant healthcare models.

    Returns:
        List of healthcare-compliant models
    """
    models = model_catalog_service.get_healthcare_compliant_models()

    return [
        ModelResponse(**model.to_dict())
        for model in models
    ]


@router.get("/statistics")
async def get_catalog_statistics(
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> Dict[str, Any]:
    """
    Get statistics about the model catalog.

    Returns:
        Dictionary containing catalog statistics
    """
    return model_catalog_service.get_catalog_statistics()


@router.get("/autonomize", response_model=List[ModelResponse])
async def get_autonomize_models(
    model_type: Optional[str] = Query(None, description="Filter by model type (text or document)"),
    model_catalog_service: ModelCatalogService = Depends(get_model_catalog_service)
) -> List[ModelResponse]:
    """
    Get all Autonomize models.

    This endpoint specifically returns the 9 Autonomize model variants:
    - 6 text models: Clinical LLM, Clinical Note Classifier, Combined Entity Linking, CPT Code, ICD-10 Code, RxNorm Code
    - 3 document models: SRF Extraction, SRF Identification, Letter Split Model

    Args:
        model_type: Optional filter by model type (text or document)

    Returns:
        List of Autonomize models
    """
    models = model_catalog_service.get_all_models(
        filter_by_provider="autonomize",
        filter_by_type=model_type
    )

    return [
        ModelResponse(**model.to_dict())
        for model in models
    ]