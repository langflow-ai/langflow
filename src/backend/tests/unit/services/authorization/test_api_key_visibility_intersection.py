"""Intersect API key ceilings before pagination, including owned rows."""

from uuid import uuid4

from langflow.services.authorization.listing import resource_visible_in_scope, restrict_to_owned_or_visible_scope
from lfx.services.authorization import ResourceVisibilityScope
from sqlalchemy import Column, MetaData, String, Table, Uuid, create_engine, select


def test_sql_intersection_limits_owned_and_shared_rows_before_counting():
    resources = Table("resources", MetaData(), Column("id", Uuid), Column("owner", String), Column("project", Uuid))
    engine = create_engine("sqlite://")
    resources.metadata.create_all(engine)
    project_a, project_b, shared_id, owned_a, owned_b, unshared = (uuid4() for _ in range(6))
    visibility = ResourceVisibilityScope(
        resource_ids=(shared_id,),
        intersections=(ResourceVisibilityScope(project_ids=(project_a,)),),
    )
    statement = restrict_to_owned_or_visible_scope(
        select(resources.c.id),
        id_column=resources.c.id,
        owner_clause=resources.c.owner == "owner",
        project_column=resources.c.project,
        visibility=visibility,
    )
    with engine.begin() as connection:
        connection.execute(
            resources.insert(),
            [
                {"id": owned_a, "owner": "owner", "project": project_a},
                {"id": owned_b, "owner": "owner", "project": project_b},
                {"id": shared_id, "owner": "other", "project": project_a},
                {"id": unshared, "owner": "other", "project": project_a},
            ],
        )
        assert set(connection.scalars(statement)) == {owned_a, shared_id}
    engine.dispose()


def test_empty_intersection_denies_every_owned_row():
    resources = Table("resources", MetaData(), Column("id", String), Column("owner", String))
    statement = restrict_to_owned_or_visible_scope(
        select(resources),
        id_column=resources.c.id,
        owner_clause=resources.c.owner == "owner",
        visibility=ResourceVisibilityScope(all_resources=True, intersections=(ResourceVisibilityScope(),)),
    )
    assert "false" in str(statement).lower()


def test_in_memory_visibility_applies_every_ceiling():
    allowed_project, denied_project, resource_id = uuid4(), uuid4(), uuid4()
    visibility = ResourceVisibilityScope(
        all_resources=True, intersections=(ResourceVisibilityScope(project_ids=(allowed_project,)),)
    )
    assert resource_visible_in_scope(resource_id=resource_id, visibility=visibility, project_id=allowed_project)
    assert not resource_visible_in_scope(resource_id=resource_id, visibility=visibility, project_id=denied_project)
