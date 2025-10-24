"""Genesis data models for specifications and components."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class ComponentProvides(BaseModel):
    """Represents what a component provides to other components."""
    useAs: str
    in_: Optional[str] = None  # Using in_ to avoid Python keyword conflict


class Component(BaseModel):
    """Represents a component in a Genesis specification."""
    id: str
    type: str
    name: Optional[str] = None
    provides: Optional[List[ComponentProvides]] = None
    asTools: Optional[bool] = None


class AgentSpec(BaseModel):
    """Represents a complete agent specification."""
    name: str
    description: Optional[str] = None
    components: List[Component]
    metadata: Optional[Dict[str, Any]] = None