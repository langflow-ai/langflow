"""DB-backed 10k-flow regression benchmark for authorization list prefiltering.

This is intentionally a correctness benchmark, not a micro-benchmark contest:
the SQL path is compared with a frozen broad-fetch/in-memory oracle and uses a
generous wall-clock ceiling so slower CI hosts do not flap.
"""

from __future__ import annotations

from statistics import median
from time import perf_counter
from uuid import UUID, uuid4

import pytest
from langflow.services.authorization.listing import (
    resource_visible_in_scope,
    restrict_to_owned_or_visible_scope,
)
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.model import Folder
from lfx.services.authorization.base import ResourceVisibilityScope
from sqlalchemy import case, func
from sqlmodel import Session, col, create_engine, select

FLOW_COUNT = 10_000
PAGE_OFFSET = 25
PAGE_SIZE = 50


def _elapsed(callable_):
    started = perf_counter()
    result = callable_()
    return perf_counter() - started, result


@pytest.mark.benchmark
def test_flow_list_prefilter_matches_in_memory_oracle_at_ten_thousand_rows(tmp_path, record_property):
    """SQL authorization runs before count/pagination and avoids broad materialization."""
    owner_id = uuid4()
    other_user_id = uuid4()
    visible_workspace_id = uuid4()
    hidden_workspace_id = uuid4()
    visible_project_id = uuid4()
    visible_workspace_project_id = uuid4()
    hidden_project_id = uuid4()
    explicit_indexes = frozenset({3, 5, 7})

    rows: list[dict[str, object]] = []
    explicit_ids: list[UUID] = []
    for index in range(FLOW_COUNT):
        flow_id = uuid4()
        if index in explicit_indexes:
            explicit_ids.append(flow_id)
        project_id = (
            visible_project_id
            if index % 80 == 2
            else visible_workspace_project_id
            if index % 50 == 1
            else hidden_project_id
        )
        rows.append(
            {
                "id": flow_id,
                "name": f"flow-{index:05d}",
                "user_id": owner_id if index % 100 == 0 else other_user_id,
                # Deliberately wrong for workspace-visible project rows: the
                # benchmark oracle must use Folder.workspace_id, not this
                # denormalized value.
                "workspace_id": hidden_workspace_id,
                "folder_id": project_id,
            }
        )

    visibility = ResourceVisibilityScope(
        resource_ids=tuple(explicit_ids),
        workspace_ids=(visible_workspace_id,),
        project_ids=(visible_project_id,),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'flow-prefilter.db'}")
    Folder.__table__.create(engine)
    Flow.__table__.create(engine)

    with engine.begin() as connection:
        connection.execute(
            Folder.__table__.insert(),
            [
                {"id": visible_project_id, "name": "visible-project", "workspace_id": hidden_workspace_id},
                {
                    "id": visible_workspace_project_id,
                    "name": "visible-workspace-project",
                    "workspace_id": visible_workspace_id,
                },
                {"id": hidden_project_id, "name": "hidden-project", "workspace_id": hidden_workspace_id},
            ],
        )
        connection.execute(Flow.__table__.insert(), rows)

    with Session(engine) as session:
        # Frozen reference for the former shape: materialize every row, then
        # apply the owner override and structured visibility in Python.
        broad_seconds, broad_rows = _elapsed(lambda: session.exec(select(Flow)).all())
        oracle = [
            flow
            for flow in broad_rows
            if flow.user_id == owner_id
            or resource_visible_in_scope(
                resource_id=flow.id,
                workspace_id={
                    visible_project_id: hidden_workspace_id,
                    visible_workspace_project_id: visible_workspace_id,
                    hidden_project_id: hidden_workspace_id,
                }[flow.folder_id],
                project_id=flow.folder_id,
                visibility=visibility,
            )
        ]

        filtered_stmt = restrict_to_owned_or_visible_scope(
            select(Flow).outerjoin(Folder, Folder.id == Flow.folder_id),
            id_column=Flow.id,
            owner_clause=Flow.user_id == owner_id,
            workspace_expression=case(
                (col(Flow.folder_id).is_not(None), Folder.workspace_id),
                else_=Flow.workspace_id,
            ),
            project_column=Flow.folder_id,
            visibility=visibility,
        )
        sql_timings: list[float] = []
        sql_rows = []
        for _ in range(3):
            elapsed, sql_rows = _elapsed(lambda: session.exec(filtered_stmt).all())
            sql_timings.append(elapsed)

        sql_count = session.exec(select(func.count()).select_from(filtered_stmt.subquery())).one()
        ordered_stmt = filtered_stmt.order_by(Flow.name, Flow.id)
        sql_page = session.exec(ordered_stmt.offset(PAGE_OFFSET).limit(PAGE_SIZE)).all()
        oracle_page = sorted(oracle, key=lambda flow: (flow.name, flow.id))[PAGE_OFFSET : PAGE_OFFSET + PAGE_SIZE]

    oracle_ids = {flow.id for flow in oracle}
    sql_ids = {flow.id for flow in sql_rows}
    assert sql_ids == oracle_ids
    assert sql_count == len(oracle)
    assert len(sql_rows) == len(oracle)
    assert [flow.id for flow in sql_page] == [flow.id for flow in oracle_page]
    assert len(broad_rows) == FLOW_COUNT
    assert len(sql_rows) < FLOW_COUNT // 10, "prefilter should materialize only the authorized working set"

    median_sql_seconds = median(sql_timings)
    record_property("broad_fetch_seconds", broad_seconds)
    record_property("sql_prefilter_median_seconds", median_sql_seconds)
    record_property("broad_rows_materialized", len(broad_rows))
    record_property("prefilter_rows_materialized", len(sql_rows))
    assert median_sql_seconds < 2.0
