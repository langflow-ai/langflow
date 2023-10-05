from langflow.services.database.models.base import SQLModel, SQLModelSerializable
from sqlmodel import Field, Relationship


from datetime import datetime
from typing import Optional, TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from langflow.services.database.models.api_key import ApiKey
    from langflow.services.database.models.flow import Flow


class User(SQLModelSerializable, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, unique=True)
    username: str = Field(index=True, unique=True)
    password: str = Field()
    profile_image: Optional[str] = Field(default=None, nullable=True)
    is_active: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    create_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = Field()
    api_keys: list["ApiKey"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "delete"},
    )
    flows: list["Flow"] = Relationship(back_populates="user")


class UserCreate(SQLModel):
    username: str = Field()
    password: str = Field()


class UserRead(SQLModel):
    id: UUID = Field(default_factory=uuid4)
    username: str = Field()
    profile_image: Optional[str] = Field()
    is_active: bool = Field()
    is_superuser: bool = Field()
    create_at: datetime = Field()
    updated_at: datetime = Field()
    last_login_at: Optional[datetime] = Field()


class UserUpdate(SQLModel):
    username: Optional[str] = Field()
    profile_image: Optional[str] = Field()
    password: Optional[str] = Field()
    is_active: Optional[bool] = Field()
    is_superuser: Optional[bool] = Field()
    last_login_at: Optional[datetime] = Field()
