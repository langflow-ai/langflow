from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class DeploymentAttachmentKey(BaseModel):
    deployment_id: UUID
    flow_version_id: UUID


class DeploymentAttachmentKeyBatch(BaseModel):
    keys: list[DeploymentAttachmentKey] = Field(default_factory=list)

    @model_validator(mode="after")
    def dedupe_keys(self) -> DeploymentAttachmentKeyBatch:
        seen: set[tuple[UUID, UUID]] = set()
        deduped: list[DeploymentAttachmentKey] = []
        for key in self.keys:
            key_tuple = (key.deployment_id, key.flow_version_id)
            if key_tuple in seen:
                continue
            seen.add(key_tuple)
            deduped.append(key)
        self.keys = deduped
        return self

    def as_tuples(self) -> list[tuple[UUID, UUID]]:
        return [(key.deployment_id, key.flow_version_id) for key in self.keys]
