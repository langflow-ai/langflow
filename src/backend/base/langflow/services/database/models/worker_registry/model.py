from datetime import datetime
from enum import Enum
from uuid import UUID

from sqlalchemy import Column, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlmodel import Field, SQLModel


class WorkerState(str, Enum):
    IDLE = "idle"
    BUSY = "busy"


class WorkerRegistryBase(SQLModel):
    owner: str = Field(primary_key=True)  # worker:{pid}:{rand}
    pid: int = Field()
    host: str = Field()
    started_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    last_heartbeat: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False, index=True))
    state: WorkerState = Field(
        sa_column=Column(
            SQLEnum(
                WorkerState,
                name="worker_state_enum",
                values_callable=lambda obj: [item.value for item in obj],
            ),
            nullable=False,
        ),
    )
    current_job_id: UUID | None = Field(default=None, nullable=True)


class WorkerRegistry(WorkerRegistryBase, table=True):  # type: ignore[call-arg]
    __tablename__ = "worker_registry"
