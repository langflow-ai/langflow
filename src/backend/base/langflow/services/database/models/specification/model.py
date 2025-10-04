# Path: src/backend/base/langflow/services/database/models/specification/model.py

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer, field_validator
from sqlalchemy import Text, UniqueConstraint, text
from sqlalchemy import Enum as SQLEnum
from sqlmodel import JSON, Column, Field, SQLModel


class SpecificationStatusEnum(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    DEPRECATED = "deprecated"


class AgentKindEnum(str, Enum):
    SINGLE_AGENT = "Single Agent"
    MULTI_AGENT = "Multi Agent"
    ORCHESTRATOR = "Orchestrator"


class TargetUserEnum(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    BOTH = "both"


class AgentSpecificationBase(SQLModel):
    """Base model for agent specifications"""
    __mapper_args__ = {"confirm_deleted_rows": False}

    # Core Identity
    name: str = Field(index=True, max_length=255)
    version: str = Field(index=True, max_length=50)
    spec_yaml: str = Field(sa_column=Column(Text, nullable=False))
    spec_json: dict = Field(sa_column=Column(JSON, nullable=False))

    # Identity & Ownership
    domain: str = Field(index=True, max_length=255)
    subdomain: Optional[str] = Field(default=None, max_length=255)
    owner_email: str = Field(index=True, max_length=255)
    fully_qualified_name: str = Field(max_length=500)

    # Classification
    kind: AgentKindEnum = Field(
        default=AgentKindEnum.SINGLE_AGENT,
        sa_column=Column(
            SQLEnum(
                AgentKindEnum,
                name="agent_kind_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'Single Agent'"),
        ),
    )
    target_user: TargetUserEnum = Field(
        default=TargetUserEnum.INTERNAL,
        sa_column=Column(
            SQLEnum(
                TargetUserEnum,
                name="target_user_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'internal'"),
        ),
    )
    value_generation: Optional[str] = Field(default=None, max_length=100)
    interaction_mode: Optional[str] = Field(default=None, max_length=100)
    run_mode: Optional[str] = Field(default=None, max_length=50)
    agency_level: Optional[str] = Field(default=None, max_length=100)

    # Status & Lifecycle
    status: SpecificationStatusEnum = Field(
        default=SpecificationStatusEnum.DRAFT,
        sa_column=Column(
            SQLEnum(
                SpecificationStatusEnum,
                name="specification_status_enum",
                values_callable=lambda enum: [member.value for member in enum],
            ),
            nullable=False,
            server_default=text("'draft'"),
        ),
    )

    # Content & Description
    goal: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True, index=True))

    # Search & Discovery Fields
    tags: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    components: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    variables: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Metrics
    reusability_score: Optional[float] = Field(default=None, index=True)
    complexity_score: Optional[float] = Field(default=None)

    # Deployment Information
    deployment_mode: Optional[str] = Field(default=None, max_length=50)
    docker_image: Optional[str] = Field(default=None, max_length=500)
    helm_release: Optional[str] = Field(default=None, max_length=255)
    api_endpoint: Optional[str] = Field(default=None, max_length=500)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    published_at: Optional[datetime] = Field(default=None, nullable=True)

    @field_serializer("created_at", "updated_at", "published_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value

    @field_validator("created_at", "updated_at", "published_at", mode="before")
    @classmethod
    def validate_dt(cls, v):
        if v is None:
            return v
        if isinstance(v, datetime):
            return v
        return datetime.fromisoformat(v)


class AgentSpecification(AgentSpecificationBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id", nullable=True, index=True)
    flow_id: UUID | None = Field(default=None, foreign_key="flow.id", nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("name", "version", name="unique_spec_version"),
        UniqueConstraint("user_id", "name", name="unique_user_spec_name"),
    )


class SpecificationComponentBase(SQLModel):
    """Base model for specification components"""
    component_id: str = Field(max_length=255, index=True)
    component_type: str = Field(max_length=100, index=True)
    component_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    provides_config: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    reusable: bool = Field(default=False)
    usage_count: int = Field(default=0)


class SpecificationComponent(SpecificationComponentBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    spec_id: UUID = Field(foreign_key="agentspecification.id", index=True)


class ComponentRelationshipBase(SQLModel):
    """Base model for component relationships"""
    relationship_type: str = Field(max_length=50)  # 'provides', 'depends_on', 'similar_to'
    confidence_score: Optional[float] = Field(default=None)


class ComponentRelationship(ComponentRelationshipBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    source_component_id: UUID = Field(foreign_key="specificationcomponent.id")
    target_component_id: UUID = Field(foreign_key="specificationcomponent.id")


class SpecificationUsageBase(SQLModel):
    """Base model for specification usage tracking"""
    usage_type: str = Field(max_length=50)  # 'view', 'copy', 'reuse', 'template'
    context_info: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    @field_serializer("created_at")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            value = value.replace(microsecond=0)
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.isoformat()
        return value


class SpecificationUsage(SpecificationUsageBase, table=True):  # type: ignore[call-arg]
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    spec_id: UUID = Field(foreign_key="agentspecification.id", index=True)
    user_id: UUID | None = Field(default=None, foreign_key="user.id", nullable=True)


# Pydantic models for API
class AgentSpecificationCreate(AgentSpecificationBase):
    user_id: UUID | None = None
    flow_id: UUID | None = None


class AgentSpecificationRead(AgentSpecificationBase):
    id: UUID
    user_id: UUID | None = None
    flow_id: UUID | None = None


class AgentSpecificationUpdate(SQLModel):
    name: Optional[str] = None
    version: Optional[str] = None
    spec_yaml: Optional[str] = None
    spec_json: Optional[dict] = None
    status: Optional[SpecificationStatusEnum] = None
    goal: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None
    reusability_score: Optional[float] = None
    complexity_score: Optional[float] = None
    deployment_mode: Optional[str] = None
    docker_image: Optional[str] = None
    helm_release: Optional[str] = None
    api_endpoint: Optional[str] = None
    published_at: Optional[datetime] = None