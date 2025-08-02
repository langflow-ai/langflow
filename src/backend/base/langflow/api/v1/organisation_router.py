from fastapi import APIRouter, HTTPException

from langflow.services.database.organisation import OrganizationService

router = APIRouter(tags=["Organisation"])


@router.post("/create_organisation")
async def create_organisation():
    """Create a new organisation database."""
    service = OrganizationService()
    try:
        await service.create_database_and_tables_other_initializations_with_org()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"detail": "Organisation database created"}
