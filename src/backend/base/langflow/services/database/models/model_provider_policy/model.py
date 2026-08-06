import sqlalchemy as sa
from sqlmodel import Field, SQLModel

MODEL_PROVIDER_POLICY_SINGLETON_ID = 1


class ModelProviderPolicy(SQLModel, table=True):  # type: ignore[call-arg]
    """Versioned singleton containing the install-wide provider ceiling."""

    __tablename__ = "model_provider_policy"
    __table_args__ = (
        sa.CheckConstraint(
            f"id = {MODEL_PROVIDER_POLICY_SINGLETON_ID}",
            name="ck_model_provider_policy_singleton",
        ),
        sa.CheckConstraint("version >= 0", name="ck_model_provider_policy_version"),
    )

    id: int = Field(default=MODEL_PROVIDER_POLICY_SINGLETON_ID, primary_key=True)
    approved_provider_ids: list[str] = Field(default_factory=list, sa_column=sa.Column(sa.JSON, nullable=False))
    version: int = Field(default=0, nullable=False, ge=0)
