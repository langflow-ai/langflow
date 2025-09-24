"""Authentication models for Genesis Studio Backend."""

from typing import Optional

from pydantic import BaseModel


class CustomUser(BaseModel):
    """Custom user model for external authentication integration."""

    genesis_user_id: str
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    roles: list[str] = []
    permissions: list[str] = []

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class ManagedIdentityUser(BaseModel):
    """User model for Azure Managed Identity authentication."""

    object_id: str  # Azure AD object ID
    tenant_id: str  # Azure tenant ID
    client_id: Optional[str] = None  # For user-assigned managed identity
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: bool = True
    is_superuser: bool = False
    claims: dict = {}

    class Config:
        """Pydantic configuration."""

        from_attributes = True
