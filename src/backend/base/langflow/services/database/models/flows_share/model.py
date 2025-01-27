from datetime import datetime, timezone
from uuid import UUID, uuid4
from sqlmodel import Relationship
from sqlmodel import Field, SQLModel
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from langflow.services.database.models.flow.model import Flow
    
class FlowShareBase(SQLModel):
    shared_with: UUID = Field(index=True, foreign_key="user.id", description="User ID of the receiver")  
    shared_by: UUID = Field(index=True, foreign_key="user.id", description="User ID of the sharer")
    flow_id: UUID = Field(index=True, foreign_key="flow.id", description="ID of the shared flow")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Timestamp when the flow was shared")

class FlowShare(FlowShareBase, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    flow: "Flow" = Relationship(back_populates="flow_shares")
    shared_with: UUID = Field(index=True, foreign_key="user.id", description="User ID of the receiver")  

class FlowShareCreate(SQLModel):
    shared_with: UUID  
    flow_id: UUID  

class FlowShareRead(FlowShareBase):
    id: UUID
    shared_with: UUID 

