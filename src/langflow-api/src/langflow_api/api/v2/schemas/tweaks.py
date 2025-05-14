from typing import Any

from pydantic import BaseModel, Field

class TweaksRequest(BaseModel):
    tweaks: dict[str, dict[str, Any]] | None = Field(default_factory=dict)
