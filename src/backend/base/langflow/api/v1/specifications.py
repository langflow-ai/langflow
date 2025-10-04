# Path: src/backend/base/langflow/api/v1/specifications.py

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from langflow.services.database.models.specification.model import (
    AgentSpecification,
    AgentSpecificationCreate,
    AgentSpecificationRead,
    AgentSpecificationUpdate,
)
from langflow.services.deps import get_session
from langflow.services.auth.utils import get_current_active_user
from langflow.services.database.models.user.model import User
from langflow.services.specification.models import (
    EnhancedAgentSpec,
    SpecificationQuery,
    SpecificationSummary,
    SimilarityMatch,
    ComponentPattern,
    ReusableComponent,
    SpecificationAnalytics,
    ConversionResult,
    ConversionRequest,
)
from langflow.services.specification.service import (
    SpecificationStorageService,
    SpecificationResearchService,
)
from langflow.services.specification.converter import EnhancedBidirectionalConverter
from langflow.api.v1.schemas import (
    BulkOperationResponse,
    BulkCreateSpecificationRequest,
    BulkUpdateSpecificationRequest,
    BulkDeleteSpecificationRequest,
    SpecificationExportResponse,
    SpecificationImportRequest,
    SpecificationImportResponse,
    SpecificationTemplateResponse,
)

router = APIRouter(prefix="/specifications", tags=["Specifications"])


@router.post("/validate")
async def validate_specification(
    spec_data: dict,
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Validate an agent specification without storing it"""

    try:
        # Try to create EnhancedAgentSpec to validate schema
        enhanced_spec = EnhancedAgentSpec(**spec_data)

        # Perform additional validation checks
        validation_errors = []
        validation_warnings = []

        # Check required fields
        if not enhanced_spec.name or not enhanced_spec.name.strip():
            validation_errors.append("Name is required and cannot be empty")

        if not enhanced_spec.description or not enhanced_spec.description.strip():
            validation_warnings.append("Description is recommended for better documentation")

        if not enhanced_spec.goal or not enhanced_spec.goal.strip():
            validation_errors.append("Goal is required and cannot be empty")

        if not enhanced_spec.components or len(enhanced_spec.components) == 0:
            validation_warnings.append("No components defined - specification may not be functional")

        # Check ID format
        if not enhanced_spec.id.startswith("urn:agent:genesis:"):
            validation_errors.append("ID must follow the pattern: urn:agent:genesis:{name}:{version}")

        # Check domain
        if not enhanced_spec.domain or not enhanced_spec.domain.strip():
            validation_errors.append("Domain is required")

        # Check owner email format
        if enhanced_spec.owner and "@" not in enhanced_spec.owner:
            validation_warnings.append("Owner should be a valid email address")

        # Validate components
        for i, component in enumerate(enhanced_spec.components):
            if not component.id or not component.id.strip():
                validation_errors.append(f"Component {i+1} is missing an ID")

            if not component.type or not component.type.strip():
                validation_errors.append(f"Component {i+1} is missing a type")

        # Validate variables if present
        if enhanced_spec.variables:
            for i, variable in enumerate(enhanced_spec.variables):
                if not variable.name or not variable.name.strip():
                    validation_errors.append(f"Variable {i+1} is missing a name")

                if not variable.type or not variable.type.strip():
                    validation_errors.append(f"Variable {i+1} is missing a type")

        # Determine validation result
        is_valid = len(validation_errors) == 0

        return {
            "valid": is_valid,
            "errors": validation_errors,
            "warnings": validation_warnings,
            "specification": enhanced_spec.model_dump() if is_valid else None
        }

    except Exception as e:
        # Schema validation failed
        return {
            "valid": False,
            "errors": [f"Schema validation failed: {str(e)}"],
            "warnings": [],
            "specification": None
        }


@router.post("/", response_model=AgentSpecificationRead)
async def create_specification(
    spec_data: EnhancedAgentSpec,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> AgentSpecificationRead:
    """Create a new agent specification"""

    try:
        storage_service = SpecificationStorageService(session)
        spec_id = await storage_service.store_specification(
            spec=spec_data,
            user_id=current_user.id
        )

        # Fetch the created specification
        from sqlalchemy import select
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.execute(stmt)
        spec = result.scalar_one()

        return AgentSpecificationRead(
            id=spec.id,
            name=spec.name,
            version=spec.version,
            spec_yaml=spec.spec_yaml,
            spec_json=spec.spec_json,
            domain=spec.domain,
            subdomain=spec.subdomain,
            owner_email=spec.owner_email,
            fully_qualified_name=spec.fully_qualified_name,
            kind=spec.kind,
            target_user=spec.target_user,
            value_generation=spec.value_generation,
            interaction_mode=spec.interaction_mode,
            run_mode=spec.run_mode,
            agency_level=spec.agency_level,
            status=spec.status,
            goal=spec.goal,
            description=spec.description,
            tags=spec.tags,
            components=spec.components,
            variables=spec.variables,
            reusability_score=spec.reusability_score,
            complexity_score=spec.complexity_score,
            deployment_mode=spec.deployment_mode,
            docker_image=spec.docker_image,
            helm_release=spec.helm_release,
            api_endpoint=spec.api_endpoint,
            created_at=spec.created_at,
            updated_at=spec.updated_at,
            published_at=spec.published_at,
            user_id=spec.user_id,
            flow_id=spec.flow_id,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create specification: {str(e)}"
        )


@router.get("/search", response_model=List[SpecificationSummary])
async def search_specifications(
    text_query: Optional[str] = None,
    domains: Optional[str] = None,  # Comma-separated
    kinds: Optional[str] = None,    # Comma-separated
    tags: Optional[str] = None,     # Comma-separated
    target_users: Optional[str] = None,  # Comma-separated
    value_generations: Optional[str] = None,  # Comma-separated
    interaction_modes: Optional[str] = None,  # Comma-separated
    run_modes: Optional[str] = None,  # Comma-separated
    min_reusability_score: Optional[float] = None,
    sort_by: str = "relevance",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> List[SpecificationSummary]:
    """Search agent specifications with advanced filters"""

    try:
        # Parse comma-separated values
        query = SpecificationQuery(
            text_query=text_query,
            domains=domains.split(",") if domains else None,
            kinds=kinds.split(",") if kinds else None,
            tags=tags.split(",") if tags else None,
            target_users=target_users.split(",") if target_users else None,
            value_generations=value_generations.split(",") if value_generations else None,
            interaction_modes=interaction_modes.split(",") if interaction_modes else None,
            run_modes=run_modes.split(",") if run_modes else None,
            min_reusability_score=min_reusability_score,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit,
            offset=offset,
        )

        storage_service = SpecificationStorageService(session)
        results = await storage_service.search_specifications(query)

        return results

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/{spec_id}", response_model=AgentSpecificationRead)
async def get_specification(
    spec_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> AgentSpecificationRead:
    """Get a specific agent specification"""

    try:
        from sqlalchemy import select
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.execute(stmt)
        spec = result.scalar_one_or_none()

        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found"
            )

        # Record usage
        storage_service = SpecificationStorageService(session)
        await storage_service.record_usage(
            spec_id=spec_id,
            usage_type="view",
            user_id=current_user.id
        )

        return AgentSpecificationRead(
            id=spec.id,
            name=spec.name,
            version=spec.version,
            spec_yaml=spec.spec_yaml,
            spec_json=spec.spec_json,
            domain=spec.domain,
            subdomain=spec.subdomain,
            owner_email=spec.owner_email,
            fully_qualified_name=spec.fully_qualified_name,
            kind=spec.kind,
            target_user=spec.target_user,
            value_generation=spec.value_generation,
            interaction_mode=spec.interaction_mode,
            run_mode=spec.run_mode,
            agency_level=spec.agency_level,
            status=spec.status,
            goal=spec.goal,
            description=spec.description,
            tags=spec.tags,
            components=spec.components,
            variables=spec.variables,
            reusability_score=spec.reusability_score,
            complexity_score=spec.complexity_score,
            deployment_mode=spec.deployment_mode,
            docker_image=spec.docker_image,
            helm_release=spec.helm_release,
            api_endpoint=spec.api_endpoint,
            created_at=spec.created_at,
            updated_at=spec.updated_at,
            published_at=spec.published_at,
            user_id=spec.user_id,
            flow_id=spec.flow_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get specification: {str(e)}"
        )


@router.get("/{spec_id}/similar", response_model=List[SimilarityMatch])
async def find_similar_specifications(
    spec_id: UUID,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> List[SimilarityMatch]:
    """Find specifications similar to the given specification"""

    try:
        # Get the specification
        from sqlalchemy import select
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.execute(stmt)
        spec = result.scalar_one_or_none()

        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found"
            )

        # Convert to enhanced spec for similarity matching
        enhanced_spec = EnhancedAgentSpec(**spec.spec_json)

        storage_service = SpecificationStorageService(session)
        similar_specs = await storage_service.find_similar_specifications(
            spec=enhanced_spec,
            limit=limit
        )

        return similar_specs

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar specifications: {str(e)}"
        )


@router.get("/{spec_id}/analytics", response_model=SpecificationAnalytics)
async def get_specification_analytics(
    spec_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> SpecificationAnalytics:
    """Get analytics for a specification"""

    try:
        storage_service = SpecificationStorageService(session)
        analytics = await storage_service.get_specification_analytics(spec_id)

        return analytics

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get analytics: {str(e)}"
        )


@router.post("/{spec_id}/usage")
async def record_specification_usage(
    spec_id: UUID,
    usage_type: str,
    context_info: Optional[dict] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Record specification usage for analytics"""

    try:
        storage_service = SpecificationStorageService(session)
        await storage_service.record_usage(
            spec_id=spec_id,
            usage_type=usage_type,
            user_id=current_user.id,
            context_info=context_info
        )

        return {"message": "Usage recorded successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to record usage: {str(e)}"
        )


@router.get("/patterns/components", response_model=List[ComponentPattern])
async def get_component_patterns(
    domain: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> List[ComponentPattern]:
    """Get component patterns for reuse"""

    try:
        storage_service = SpecificationStorageService(session)
        research_service = SpecificationResearchService(storage_service)

        if domain:
            patterns = await research_service.analyze_reusable_patterns(domain)
        else:
            # Get patterns for all domains (limit to avoid performance issues)
            patterns = []
            # TODO: Implement cross-domain pattern analysis

        return patterns

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get component patterns: {str(e)}"
        )


@router.post("/convert/from-flow", response_model=ConversionResult)
async def convert_flow_to_specification(
    flow_data: dict,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> ConversionResult:
    """Convert a Langflow flow to an agent specification"""

    try:
        converter = EnhancedBidirectionalConverter()
        result = await converter.flow_to_spec(flow_data)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversion failed: {str(e)}"
        )


@router.post("/convert/to-flow")
async def convert_specification_to_flow(
    request: ConversionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    """Convert an agent specification to a Langflow flow"""

    try:
        # Create EnhancedAgentSpec from the request specification
        spec_data = EnhancedAgentSpec(**request.specification)

        converter = EnhancedBidirectionalConverter()
        flow_data = await converter.spec_to_flow(spec_data)

        # Return in the format expected by genesis-agent-cli ConversionResponse
        return {
            "flow": flow_data,
            "metadata": {
                "conversion_timestamp": datetime.now().isoformat(),
                "converter_version": "1.0.0",
                "specification_id": spec_data.id,
                "specification_version": spec_data.version
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Conversion failed: {str(e)}"
        )


@router.put("/{spec_id}", response_model=AgentSpecificationRead)
async def update_specification(
    spec_id: UUID,
    spec_update: AgentSpecificationUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> AgentSpecificationRead:
    """Update an agent specification"""

    try:
        from sqlalchemy import select
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.execute(stmt)
        spec = result.scalar_one_or_none()

        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found"
            )

        # Check ownership
        if spec.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to update this specification"
            )

        # Update fields
        update_data = spec_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(spec, field, value)

        spec.updated_at = datetime.utcnow()

        await session.commit()
        await session.refresh(spec)

        return AgentSpecificationRead(
            id=spec.id,
            name=spec.name,
            version=spec.version,
            spec_yaml=spec.spec_yaml,
            spec_json=spec.spec_json,
            domain=spec.domain,
            subdomain=spec.subdomain,
            owner_email=spec.owner_email,
            fully_qualified_name=spec.fully_qualified_name,
            kind=spec.kind,
            target_user=spec.target_user,
            value_generation=spec.value_generation,
            interaction_mode=spec.interaction_mode,
            run_mode=spec.run_mode,
            agency_level=spec.agency_level,
            status=spec.status,
            goal=spec.goal,
            description=spec.description,
            tags=spec.tags,
            components=spec.components,
            variables=spec.variables,
            reusability_score=spec.reusability_score,
            complexity_score=spec.complexity_score,
            deployment_mode=spec.deployment_mode,
            docker_image=spec.docker_image,
            helm_release=spec.helm_release,
            api_endpoint=spec.api_endpoint,
            created_at=spec.created_at,
            updated_at=spec.updated_at,
            published_at=spec.published_at,
            user_id=spec.user_id,
            flow_id=spec.flow_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update specification: {str(e)}"
        )


@router.delete("/{spec_id}")
async def delete_specification(
    spec_id: UUID,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Delete an agent specification"""

    try:
        from sqlalchemy import select
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.execute(stmt)
        spec = result.scalar_one_or_none()

        if not spec:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Specification not found"
            )

        # Check ownership
        if spec.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to delete this specification"
            )

        await session.delete(spec)
        await session.commit()

        return {"message": "Specification deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete specification: {str(e)}"
        )


# ========================================
# BULK OPERATIONS
# ========================================

@router.post("/bulk", response_model=BulkOperationResponse)
async def bulk_create_specifications(
    request: BulkCreateSpecificationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> BulkOperationResponse:
    """Create multiple specifications in bulk"""

    successful = []
    failed = []

    try:
        storage_service = SpecificationStorageService(session)

        for spec_data in request.specifications:
            try:
                # Convert dict to EnhancedAgentSpec
                enhanced_spec = EnhancedAgentSpec(**spec_data)

                spec_id = await storage_service.store_specification(
                    spec=enhanced_spec,
                    user_id=current_user.id
                )
                successful.append(spec_id)

            except Exception as e:
                failed.append({
                    "data": spec_data,
                    "error": str(e)
                })

        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(request.specifications)
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk create failed: {str(e)}"
        )


@router.put("/bulk", response_model=BulkOperationResponse)
async def bulk_update_specifications(
    request: BulkUpdateSpecificationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> BulkOperationResponse:
    """Update multiple specifications in bulk"""

    successful = []
    failed = []

    try:
        from sqlalchemy import select

        for update_item in request.updates:
            try:
                spec_id = update_item["id"]
                update_data = update_item["data"]

                # Get the specification
                stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
                result = await session.exec(stmt)
                spec = result.scalar_one_or_none()

                if not spec:
                    failed.append({
                        "id": spec_id,
                        "error": "Specification not found"
                    })
                    continue

                # Check ownership
                if spec.user_id != current_user.id and not current_user.is_superuser:
                    failed.append({
                        "id": spec_id,
                        "error": "Access denied"
                    })
                    continue

                # Update fields
                for field, value in update_data.items():
                    if hasattr(spec, field):
                        setattr(spec, field, value)

                spec.updated_at = datetime.utcnow()
                successful.append(spec_id)

            except Exception as e:
                failed.append({
                    "id": update_item.get("id"),
                    "error": str(e)
                })

        await session.commit()

        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(request.updates)
        )

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk update failed: {str(e)}"
        )


@router.delete("/bulk", response_model=BulkOperationResponse)
async def bulk_delete_specifications(
    request: BulkDeleteSpecificationRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> BulkOperationResponse:
    """Delete multiple specifications in bulk"""

    successful = []
    failed = []

    try:
        from sqlalchemy import select

        for spec_id in request.specification_ids:
            try:
                # Get the specification
                stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
                result = await session.exec(stmt)
                spec = result.scalar_one_or_none()

                if not spec:
                    failed.append({
                        "id": spec_id,
                        "error": "Specification not found"
                    })
                    continue

                # Check ownership
                if spec.user_id != current_user.id and not current_user.is_superuser:
                    failed.append({
                        "id": spec_id,
                        "error": "Access denied"
                    })
                    continue

                await session.delete(spec)
                successful.append(spec_id)

            except Exception as e:
                failed.append({
                    "id": spec_id,
                    "error": str(e)
                })

        await session.commit()

        return BulkOperationResponse(
            successful=successful,
            failed=failed,
            total_processed=len(request.specification_ids)
        )

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Bulk delete failed: {str(e)}"
        )


# ========================================
# EXPORT/IMPORT OPERATIONS
# ========================================

@router.get("/{spec_id}/export", response_model=SpecificationExportResponse)
async def export_specification(
    spec_id: UUID,
    format: str = "yaml",  # "yaml" or "json"
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> SpecificationExportResponse:
    """Export a specification as YAML or JSON"""

    try:
        from sqlalchemy import select
        import yaml
        import json

        # Get the specification
        stmt = select(AgentSpecification).where(AgentSpecification.id == spec_id)
        result = await session.exec(stmt)
        spec = result.scalar_one_or_none()

        if not spec:
            raise HTTPException(status_code=404, detail="Specification not found")

        # Check access
        if spec.user_id != current_user.id and not current_user.is_superuser:
            raise HTTPException(status_code=403, detail="Access denied")

        # Prepare export data
        export_data = {
            "metadata": {
                "name": spec.name,
                "version": spec.version,
                "domain": spec.domain,
                "subdomain": spec.subdomain,
                "owner_email": spec.owner_email,
                "kind": spec.kind,
                "target_user": spec.target_user,
                "status": spec.status,
                "created_at": spec.created_at.isoformat(),
                "updated_at": spec.updated_at.isoformat(),
            },
            "specification": spec.spec_json,
            "yaml_content": spec.spec_yaml
        }

        # Generate content based on format
        if format.lower() == "yaml":
            content = yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
            filename = f"{spec.name}_{spec.version}.yaml"
        elif format.lower() == "json":
            content = json.dumps(export_data, indent=2, default=str)
            filename = f"{spec.name}_{spec.version}.json"
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'yaml' or 'json'")

        return SpecificationExportResponse(
            format=format.lower(),
            filename=filename,
            content=content,
            size=len(content.encode('utf-8'))
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {str(e)}"
        )


@router.post("/import", response_model=SpecificationImportResponse)
async def import_specifications(
    request: SpecificationImportRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> SpecificationImportResponse:
    """Import specifications from YAML or JSON"""

    try:
        import yaml
        import json

        # Parse content based on format
        if request.format.lower() == "yaml":
            data = yaml.safe_load(request.content)
        elif request.format.lower() == "json":
            data = json.loads(request.content)
        else:
            raise HTTPException(status_code=400, detail="Unsupported format. Use 'yaml' or 'json'")

        # Handle both single specification and list of specifications
        if isinstance(data, dict) and "metadata" in data:
            # Single specification
            specifications = [data]
        elif isinstance(data, list):
            # List of specifications
            specifications = data
        else:
            raise HTTPException(status_code=400, detail="Invalid file format")

        imported_count = 0
        skipped_count = 0
        failed_count = 0
        errors = []

        storage_service = SpecificationStorageService(session)

        for spec_data in specifications:
            try:
                metadata = spec_data.get("metadata", {})
                spec_json = spec_data.get("specification", {})

                # Check if specification already exists
                if not request.overwrite_existing:
                    from sqlalchemy import select
                    existing_stmt = select(AgentSpecification).where(
                        and_(
                            AgentSpecification.name == metadata.get("name"),
                            AgentSpecification.version == metadata.get("version"),
                            AgentSpecification.user_id == current_user.id
                        )
                    )
                    existing_result = await session.exec(existing_stmt)
                    if existing_result.first():
                        skipped_count += 1
                        continue

                # Create EnhancedAgentSpec from imported data
                enhanced_spec = EnhancedAgentSpec(**spec_json)

                # Store the specification
                await storage_service.store_specification(
                    spec=enhanced_spec,
                    user_id=current_user.id
                )
                imported_count += 1

            except Exception as e:
                failed_count += 1
                errors.append(f"Failed to import {metadata.get('name', 'unknown')}: {str(e)}")

        return SpecificationImportResponse(
            imported_count=imported_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            errors=errors
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Import failed: {str(e)}"
        )


# ========================================
# TEMPLATE OPERATIONS
# ========================================

@router.get("/templates", response_model=SpecificationTemplateResponse)
async def get_specification_templates(
    category: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
) -> SpecificationTemplateResponse:
    """Get specification templates"""

    try:
        # This would typically load from a template repository or database
        # For now, return some example healthcare templates
        templates = [
            {
                "id": "clinical-extraction",
                "name": "Clinical Data Extraction Agent",
                "description": "Template for extracting clinical information from medical records",
                "category": "Healthcare",
                "domain": "healthcare",
                "kind": "Single Agent",
                "target_user": "internal",
                "template": {
                    "metadata": {
                        "name": "Clinical Extraction Agent",
                        "version": "1.0.0",
                        "domain": "healthcare",
                        "kind": "Single Agent",
                        "target_user": "internal"
                    },
                    "components": [
                        {
                            "id": "text_input",
                            "type": "TextInput",
                            "config": {"placeholder": "Enter medical record text"}
                        },
                        {
                            "id": "clinical_extractor",
                            "type": "ClinicalExtractor",
                            "config": {"extract_entities": True}
                        }
                    ]
                }
            },
            {
                "id": "prior-auth",
                "name": "Prior Authorization Agent",
                "description": "Template for processing prior authorization requests",
                "category": "Healthcare",
                "domain": "healthcare",
                "kind": "Multi Agent",
                "target_user": "internal",
                "template": {
                    "metadata": {
                        "name": "Prior Authorization Agent",
                        "version": "1.0.0",
                        "domain": "healthcare",
                        "kind": "Multi Agent",
                        "target_user": "internal"
                    },
                    "components": [
                        {
                            "id": "document_analyzer",
                            "type": "DocumentAnalyzer",
                            "config": {"analyze_medical_records": True}
                        },
                        {
                            "id": "criteria_checker",
                            "type": "CriteriaChecker",
                            "config": {"check_eligibility": True}
                        }
                    ]
                }
            }
        ]

        # Filter by category if specified
        if category:
            templates = [t for t in templates if t["category"].lower() == category.lower()]

        categories = list(set(t["category"] for t in templates))

        return SpecificationTemplateResponse(
            templates=templates,
            categories=categories
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get templates: {str(e)}"
        )


@router.post("/from-template")
async def create_from_template(
    template_id: str,
    customizations: dict = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_active_user),
):
    """Create a specification from a template"""

    try:
        # Get templates (in a real implementation, this would fetch from a template store)
        templates_response = await get_specification_templates(session=session, current_user=current_user)

        # Find the requested template
        template = None
        for t in templates_response.templates:
            if t["id"] == template_id:
                template = t
                break

        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Create specification from template
        template_data = template["template"]

        # Apply customizations if provided
        if customizations:
            template_data.update(customizations)

        # Convert to EnhancedAgentSpec and store
        enhanced_spec = EnhancedAgentSpec(**template_data)

        storage_service = SpecificationStorageService(session)
        spec_id = await storage_service.store_specification(
            spec=enhanced_spec,
            user_id=current_user.id
        )

        return {"specification_id": spec_id, "message": "Specification created from template successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create from template: {str(e)}"
        )