"""Models for package manager service."""

from enum import Enum

from pydantic import BaseModel, Field


class PackageStatus(str, Enum):
    """Status of a package installation."""
    NOT_INSTALLED = "not_installed"
    INSTALLED = "installed"
    INSTALLING = "installing"
    FAILED = "failed"
    UNKNOWN = "unknown"


class OptionalDependency(BaseModel):
    """Model for an optional dependency group."""
    name: str = Field(..., description="Name of the optional dependency group")
    display_name: str = Field(..., description="User-friendly display name")
    description: str = Field(..., description="Description of what this dependency provides")
    packages: list[str] = Field(..., description="List of packages in this group")
    status: PackageStatus = Field(default=PackageStatus.UNKNOWN, description="Installation status")
    error: str | None = Field(None, description="Error message if installation failed")


class InstallRequest(BaseModel):
    """Request to install an optional dependency group."""
    dependency_name: str = Field(..., description="Name of the optional dependency group to install")
    auto_restart: bool = Field(default=False, description="Whether to automatically restart the server after installation")


class InstallResponse(BaseModel):
    """Response from an installation request."""
    dependency_name: str
    status: PackageStatus
    message: str
    error: str | None = None
    restart_required: bool = Field(default=False, description="Whether a restart is required to use the installed packages")
    auto_restart: bool = Field(default=False, description="Whether the server will automatically restart")