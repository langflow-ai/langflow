"""Database contracts for catalog policy rules."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from langflow.services.database.models.catalog_policy import (
    CatalogPolicyMode,
    CatalogPolicyRule,
    CatalogPolicyScope,
    CatalogResourceKind,
)
from langflow.services.database.models.user.model import User
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

_TEST_PASSWORD = "hashed"  # noqa: S105  # pragma: allowlist secret


@pytest.fixture(name="catalog_policy_engine")
def catalog_policy_engine():
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    yield engine
    engine.sync_engine.dispose()


@pytest.fixture(name="catalog_policy_session")
async def catalog_policy_session(catalog_policy_engine):
    async with catalog_policy_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(catalog_policy_engine, expire_on_commit=False) as session:
        yield session
    async with catalog_policy_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await catalog_policy_engine.dispose()


def test_catalog_policy_rule_defaults_and_schema_contract():
    rule = CatalogPolicyRule(
        resource_kind=CatalogResourceKind.COMPONENT.value,
        resource_key="OpenAIModel",
    )

    assert rule.mode == CatalogPolicyMode.BLOCK.value
    assert rule.scope == CatalogPolicyScope.GLOBAL.value
    assert rule.domain_id is None
    assert rule.created_by is None
    assert rule.created_at.utcoffset() == timedelta(0)
    assert rule.updated_at.utcoffset() == timedelta(0)

    table = CatalogPolicyRule.__table__
    assert table.c.created_at.type.timezone is True
    assert table.c.updated_at.type.timezone is True

    constraint_names = {constraint.name for constraint in table.constraints}
    assert {
        "ck_catalog_policy_rule_resource_kind",
        "ck_catalog_policy_rule_mode",
        "ck_catalog_policy_rule_scope",
        "ck_catalog_policy_rule_scope_domain_consistency",
    } <= constraint_names

    indexes = {index.name: index for index in table.indexes}
    assert tuple(column.name for column in indexes["uq_catalog_policy_rule_scoped"].columns) == (
        "resource_kind",
        "resource_key",
        "scope",
        "domain_id",
    )
    assert tuple(column.name for column in indexes["uq_catalog_policy_rule_unscoped"].columns) == (
        "resource_kind",
        "resource_key",
        "scope",
    )
    assert indexes["uq_catalog_policy_rule_scoped"].unique is True
    assert indexes["uq_catalog_policy_rule_unscoped"].unique is True


@pytest.mark.anyio
async def test_catalog_policy_rule_persists_and_creator_deletion_sets_null(
    catalog_policy_session: AsyncSession,
):
    creator = User(username="catalog-policy-creator", password=_TEST_PASSWORD)
    catalog_policy_session.add(creator)
    await catalog_policy_session.commit()
    await catalog_policy_session.refresh(creator)

    rule = CatalogPolicyRule(
        resource_kind=CatalogResourceKind.TEMPLATE.value,
        resource_key="starter-template-id",
        created_by=creator.id,
    )
    catalog_policy_session.add(rule)
    await catalog_policy_session.commit()
    await catalog_policy_session.refresh(rule)

    assert rule.mode == CatalogPolicyMode.BLOCK.value
    assert rule.scope == CatalogPolicyScope.GLOBAL.value
    assert rule.created_by == creator.id

    await catalog_policy_session.delete(creator)
    await catalog_policy_session.commit()
    await catalog_policy_session.refresh(rule)
    assert rule.created_by is None


@pytest.mark.anyio
async def test_catalog_policy_rule_enforces_null_safe_uniqueness(
    catalog_policy_session: AsyncSession,
):
    global_rule = CatalogPolicyRule(
        resource_kind=CatalogResourceKind.COMPONENT.value,
        resource_key="OpenAIModel",
    )
    catalog_policy_session.add(global_rule)
    await catalog_policy_session.commit()

    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind=CatalogResourceKind.COMPONENT.value,
            resource_key="OpenAIModel",
        )
    )
    with pytest.raises(IntegrityError):
        await catalog_policy_session.commit()
    await catalog_policy_session.rollback()

    workspace_id = uuid4()
    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind=CatalogResourceKind.COMPONENT.value,
            resource_key="OpenAIModel",
            scope=CatalogPolicyScope.WORKSPACE.value,
            domain_id=workspace_id,
        )
    )
    await catalog_policy_session.commit()

    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind=CatalogResourceKind.COMPONENT.value,
            resource_key="OpenAIModel",
            scope=CatalogPolicyScope.WORKSPACE.value,
            domain_id=workspace_id,
        )
    )
    with pytest.raises(IntegrityError):
        await catalog_policy_session.commit()
    await catalog_policy_session.rollback()

    other_workspace_rule = CatalogPolicyRule(
        resource_kind=CatalogResourceKind.COMPONENT.value,
        resource_key="OpenAIModel",
        scope=CatalogPolicyScope.WORKSPACE.value,
        domain_id=uuid4(),
    )
    catalog_policy_session.add(other_workspace_rule)
    await catalog_policy_session.commit()

    rules = (
        await catalog_policy_session.exec(
            select(CatalogPolicyRule).where(CatalogPolicyRule.resource_key == "OpenAIModel")
        )
    ).all()
    assert len(rules) == 3


@pytest.mark.anyio
async def test_catalog_policy_rule_check_constraints_reject_invalid_rows(
    catalog_policy_session: AsyncSession,
):
    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind="flow",
            resource_key="unsupported-kind",
        )
    )
    with pytest.raises(IntegrityError):
        await catalog_policy_session.commit()
    await catalog_policy_session.rollback()

    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind=CatalogResourceKind.COMPONENT.value,
            resource_key="bad-global-scope",
            domain_id=uuid4(),
        )
    )
    with pytest.raises(IntegrityError):
        await catalog_policy_session.commit()
    await catalog_policy_session.rollback()

    catalog_policy_session.add(
        CatalogPolicyRule(
            resource_kind=CatalogResourceKind.TEMPLATE.value,
            resource_key="future-allow-rule",
            mode=CatalogPolicyMode.ALLOW.value,
        )
    )
    await catalog_policy_session.commit()
