from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey
from sqlmodel import Column, Field, Index, SQLModel, UniqueConstraint

from langflow.schema.data import Data

# we enforce that each flow version can only be
# published, as recognized by Langflow with PublishStateEnum SUCCESS,
# to one single storage provider at a time.


class PublishStateEnum(Enum):
    PENDING = "PENDING"
    FAILED = "FAILED"
    SUCCESS = "SUCCESS"
    REMOVED = "REMOVED"  # went from published to unpublished


class PublishProviderEnum(Enum):
    S3 = "s3"


class FlowPublish(SQLModel, table=True):
    __tablename__ = "flow_publish"

    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id")
    flow_id: UUID = Field(sa_column=Column(ForeignKey("flow.id"), nullable=False))
    flow_version_id: UUID = Field(sa_column=Column(ForeignKey("flow_version.id"), nullable=False))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # for publish_state: a None value means
    # there is no intent to publish the flow
    # nor has any attempt been made to publish the flow.
    publish_state: PublishStateEnum | None = Field(default=None, nullable=True)
    # for publish_provider: a None value means
    # there is no intent to publish the flow,
    # or that the flow was unpublished.
    # Note the distinction from publish_state.
    publish_provider: PublishProviderEnum | None = Field(default=None, nullable=True)

    __table_args__ = (
        # create index for flow_version_id?
        # create index for user_id?
        Index("flow_id_index", "flow_id"),
        UniqueConstraint("flow_id", "flow_version_id", name="at_most_one_publish_per_flow_version"),
    )

    def to_data(self):
        serialized = self.model_dump()
        data = {
            "id": serialized.pop("id"),
            "user_id": serialized.pop("user_id"),
            "flow_id": serialized.pop("flow_id"),
            "flow_version_id": serialized.pop("flow_version_id"),
            "created_at": serialized.pop("created_at"),
            "publish_state": serialized.pop("publish_state"),
            "publish_provider": serialized.pop("publish_provider"),
        }
        return Data(data=data)
