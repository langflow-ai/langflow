"""Add component mapping tables for runtime-agnostic component mappings

Revision ID: a1b2c3d4e5f6
Revises: fd531f8868b1
Create Date: 2025-01-16 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "fd531f8868b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create component mapping and runtime adapter tables."""

    # Create component_category enum
    component_category_enum = sa.Enum(
        "healthcare",
        "agent",
        "tool",
        "data",
        "prompt",
        "memory",
        "llm",
        "embedding",
        "vector_store",
        "io",
        "processing",
        "integration",
        name="componentcategoryenum",
        create_type=True
    )

    # Create runtime_type enum
    runtime_type_enum = sa.Enum(
        "langflow",
        "temporal",
        "kafka",
        "airflow",
        "dagster",
        name="runtimetypeenum",
        create_type=True
    )

    # Create component_mappings table
    op.create_table(
        "component_mappings",
        sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
        sa.Column("genesis_type", sa.String(length=100), nullable=False),
        sa.Column("base_config", sa.JSON(), nullable=True),
        sa.Column("io_mapping", sa.JSON(), nullable=True),
        sa.Column("component_category", component_category_enum, nullable=False),
        sa.Column("healthcare_metadata", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create runtime_adapters table
    op.create_table(
        "runtime_adapters",
        sa.Column("id", sqlmodel.sql.sqltypes.types.Uuid(), nullable=False),
        sa.Column("genesis_type", sa.String(length=100), nullable=False),
        sa.Column("runtime_type", runtime_type_enum, nullable=False),
        sa.Column("target_component", sa.String(length=100), nullable=False),
        sa.Column("adapter_config", sa.JSON(), nullable=True),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("compliance_rules", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for component_mappings
    op.create_index("idx_genesis_type_active", "component_mappings", ["genesis_type", "active"])
    op.create_index("idx_category_active", "component_mappings", ["component_category", "active"])
    op.create_index("idx_version_active", "component_mappings", ["version", "active"])
    op.create_index("idx_created_at", "component_mappings", ["created_at"])
    op.create_index(op.f("ix_component_mappings_genesis_type"), "component_mappings", ["genesis_type"])

    # Create indexes for runtime_adapters
    op.create_index("idx_genesis_runtime_active", "runtime_adapters", ["genesis_type", "runtime_type", "active"])
    op.create_index("idx_runtime_active", "runtime_adapters", ["runtime_type", "active"])
    op.create_index("idx_priority_active", "runtime_adapters", ["priority", "active"])
    op.create_index("idx_target_component", "runtime_adapters", ["target_component"])
    op.create_index(op.f("ix_runtime_adapters_genesis_type"), "runtime_adapters", ["genesis_type"])


def downgrade() -> None:
    """Drop component mapping and runtime adapter tables."""

    # Drop indexes
    op.drop_index(op.f("ix_runtime_adapters_genesis_type"), table_name="runtime_adapters")
    op.drop_index("idx_target_component", table_name="runtime_adapters")
    op.drop_index("idx_priority_active", table_name="runtime_adapters")
    op.drop_index("idx_runtime_active", table_name="runtime_adapters")
    op.drop_index("idx_genesis_runtime_active", table_name="runtime_adapters")

    op.drop_index(op.f("ix_component_mappings_genesis_type"), table_name="component_mappings")
    op.drop_index("idx_created_at", table_name="component_mappings")
    op.drop_index("idx_version_active", table_name="component_mappings")
    op.drop_index("idx_category_active", table_name="component_mappings")
    op.drop_index("idx_genesis_type_active", table_name="component_mappings")

    # Drop tables
    op.drop_table("runtime_adapters")
    op.drop_table("component_mappings")

    # Drop enums
    sa.Enum(name="runtimetypeenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="componentcategoryenum").drop(op.get_bind(), checkfirst=True)