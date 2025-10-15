from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import yaml
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from langflow.api.utils import CurrentActiveUser


router = APIRouter(prefix="/agent-marketplace", tags=["Agent Marketplace"])


class AgentSpecItem(BaseModel):
    """Represents a single agent specification loaded from YAML."""

    folder_name: str = Field(..., description="Folder under specifications_library/agents")
    file_name: str = Field(..., description="YAML file name containing the specification")
    spec: dict[str, Any] = Field(..., description="Agent specification converted from YAML to JSON")


class AgentMarketplaceResponse(BaseModel):
    """Response payload for agent marketplace listings."""

    items: list[AgentSpecItem] = Field(default_factory=list, description="List of agent specifications")
    total: int = Field(..., description="Total number of agent specifications returned")
    requested_folder: Optional[str] = Field(
        None, description="Folder name requested via query parameter, if any"
    )
    errors: list["AgentSpecError"] = Field(
        default_factory=list,
        description="List of files that could not be parsed, with error messages",
    )


class AgentSpecError(BaseModel):
    """Represents a parsing or loading error for a single YAML specification file."""

    folder_name: str = Field(..., description="Folder under specifications_library/agents")
    file_name: str = Field(..., description="YAML file name that failed to parse")
    message: str = Field(..., description="Human-readable error message explaining the failure")
    status_code: Optional[int] = Field(None, description="HTTP status code associated with the error, if any")


def _get_agents_base_path() -> Path:
    """Return the base path for agent specifications.

    Uses project-relative resolution to avoid hardcoding absolute paths.
    """
    return Path(__file__).parent.parent.parent / "specifications_library" / "agents"


def _load_yaml_file(file_path: Path) -> dict[str, Any]:
    """Load a YAML file safely and return its contents as a dict.

    Raises HTTPException if the file cannot be parsed.
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            # Ensure we always return a dict (empty dict for empty YAML)
            return data if isinstance(data, dict) else {}
    except yaml.YAMLError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid YAML format in '{file_path.name}': {e}"
        ) from e
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Specification file not found: {file_path.name}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read specification file '{file_path.name}': {e}"
        ) from e


@router.get(
    "/",
    response_model=AgentMarketplaceResponse,
    status_code=status.HTTP_200_OK,
)
async def list_agent_specifications(
    current_user: CurrentActiveUser,
    folder_name: str | None = Query(
        default=None,
        description=(
            "Optional folder filter. When provided, returns only agents in the specified folder "
            "under 'specifications_library/agents'."
        ),
        examples=["multi-tool", "patient-experience", "single-tool"],
    ),
) -> AgentMarketplaceResponse:
    """
    List agent specifications from the Agent Marketplace.

    - Without query parameters: returns all available agents found under 'specifications_library/agents'.
    - With 'folder_name' query parameter: returns only agents belonging to the specified folder.

    The YAML specifications are converted to JSON while preserving their original structure.
    """
    base_path = _get_agents_base_path()
    if not base_path.exists() or not base_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agents specifications library not found",
        )

    # Discover available folders
    available_folders = [p.name for p in base_path.iterdir() if p.is_dir()]

    # Resolve target paths to scan
    target_paths: list[Path]
    requested_folder = None
    if folder_name:
        # Harden against path traversal by only allowing known child folder names
        if folder_name not in available_folders:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Folder '{folder_name}' not found in Agent specifications",
            )
        requested_folder = folder_name
        target_paths = [base_path / folder_name]
    else:
        target_paths = [p for p in base_path.iterdir() if p.is_dir()]

    items: list[AgentSpecItem] = []
    errors: list[AgentSpecError] = []

    # Scan YAML files in target paths
    for folder_path in target_paths:
        # Only consider YAML files; ignore markdown or other assets
        for yaml_file in folder_path.glob("*.yaml"):
            try:
                spec_dict = _load_yaml_file(yaml_file)
                items.append(
                    AgentSpecItem(
                        folder_name=folder_path.name,
                        file_name=yaml_file.name,
                        spec=spec_dict,
                    )
                )
            except HTTPException as e:
                errors.append(
                    AgentSpecError(
                        folder_name=folder_path.name,
                        file_name=yaml_file.name,
                        message=str(e.detail) if hasattr(e, "detail") else str(e),
                        status_code=getattr(e, "status_code", None),
                    )
                )

    return AgentMarketplaceResponse(items=items, total=len(items), requested_folder=requested_folder, errors=errors)