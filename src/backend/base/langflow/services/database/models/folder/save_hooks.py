"""Apply a type's proposed save through the host's transaction and write guards."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone

from fastapi import HTTPException
from lfx.log.logger import logger
from lfx.projects.lifecycle import (
    CompositionContext,
    FlowChange,
    FlowSelector,
    PreparedSave,
    ProjectConfigError,
    ProjectResourceUnavailableError,
    SaveRequest,
)
from lfx.projects.references import field_references
from lfx.projects.writer import apply_project_config
from sqlmodel import select

from langflow.services.database.lock_retry import is_database_lock_error
from langflow.services.database.models.deployment.exceptions import araise_if_deployment_guard_error_or_skip
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.folder.save_context import (
    LangflowProjectSaveContext,
    project_error_http,
    public_config,
)


def _json_dict(value, label, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, dict):
        msg = f"{label} must be a JSON object."
        raise ProjectConfigError(msg)
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        msg = f"{label} must contain only JSON values."
        raise ProjectConfigError(msg) from exc


async def _references(ctx, definition, config):
    for field in definition.fields:
        if field.references:
            try:
                references = field_references(field, (config or {}).get(field.name))
            except ValueError as exc:
                msg = f"Choose valid {field.references} project references for {field.name}."
                raise ProjectConfigError(msg) from exc
            for reference in references:
                await ctx.read_project(reference.project_id, expected_type=field.references)


async def write_with_hooks(session, project, definition, *, current_user, previous_config=None, creating=False):
    from langflow.services.database.models.folder.config_writer import ProjectConfigWrite, _restore_point

    try:
        ctx = LangflowProjectSaveContext(session, current_user)
        identity = await ctx.start_save(project)
        rows = list(
            (
                await session.exec(
                    select(Flow).where(Flow.folder_id == project.id, Flow.user_id == project.user_id).order_by(Flow.id)
                )
            ).all()
        )
        views = []
        # Do not expose unreadable candidates or require unused pack members.
        for row in rows:
            try:
                views.append(await ctx.read_flow(FlowSelector(id=row.id), access="read"))
            except ProjectResourceUnavailableError:
                continue
        config = public_config(project.project_config)
        previous = public_config(previous_config)
        operation = "create" if creating else "clear" if config is None else "replace"
        request = SaveRequest(identity, operation, config, previous, tuple(views))
        await _references(ctx, definition, config)
        prepared = await definition.save_config(deepcopy(request), ctx)
        if not isinstance(prepared, PreparedSave):
            msg = "A project save hook must return PreparedSave."
            raise ProjectConfigError(msg)
        _json_dict(prepared.config, "Project configuration", nullable=True)
        if prepared.config is not None and "_applied" in prepared.config:
            msg = "Applied values are managed by the host."
            raise ProjectConfigError(msg)
        if config is None and prepared.config is not None:
            msg = "Clearing configuration must retain a null configuration."
            raise ProjectConfigError(msg)
        await _references(ctx, definition, prepared.config)
        local = {view.id: view for view in views}
        if len(set(prepared.target_flow_ids)) != len(prepared.target_flow_ids) or any(
            flow_id not in local for flow_id in prepared.target_flow_ids
        ):
            msg = "Choose each target once from this project's flows."
            raise ProjectConfigError(msg)
        result = ProjectConfigWrite()
        await ctx.verify_unchanged()
        targets = {}
        for flow_id in prepared.target_flow_ids:
            row = await ctx.writable_target(flow_id, project)
            if row.locked:
                result.flows_locked += 1
            else:
                targets[flow_id] = row
        applied = deepcopy((previous_config or {}).get("_applied", {}))
        applied = applied if isinstance(applied, dict) else {}
        if (
            previous_config
            and "_applied" not in previous_config
            and any(field.writes_to for field in definition.fields)
        ):
            for view in views:
                applied.setdefault(str(view.id), apply_project_config(view.data, definition, previous).applied_values)
        composition = CompositionContext(identity, tuple(local[flow_id] for flow_id in targets), applied)
        changes = definition.compose(prepared, deepcopy(composition))
        if not isinstance(changes, tuple):
            msg = "A compose hook must return a tuple of FlowChange records."
            raise ProjectConfigError(msg)
        seen = set()
        for change in changes:
            if not isinstance(change, FlowChange):
                msg = "A compose hook must return FlowChange records."
                raise ProjectConfigError(msg)
            if change.flow_id in seen or change.flow_id not in targets or change.token != local[change.flow_id].token:
                msg = "A compose hook may change each supplied target only once."
                raise ProjectConfigError(msg)
            seen.add(change.flow_id)
            _json_dict(change.data, "Flow data")
            _json_dict(change.applied_values, "Applied values")
            if type(change.fields_skipped) is not int or change.fields_skipped < 0:
                msg = "Skipped fields must be a non-negative count."
                raise ProjectConfigError(msg)
        await ctx.verify_unchanged()
        for change in changes:
            row = targets[change.flow_id]
            applied[str(row.id)] = deepcopy(change.applied_values)
            result.fields_skipped += change.fields_skipped
            if change.data == row.data:
                continue
            version = await _restore_point(session, row)
            if version:
                result.restore_version_ids[str(row.id)] = version
            row.data = deepcopy(change.data)
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
            result.flows.append(row)
        normalized = deepcopy(prepared.config)
        if normalized is not None and (applied or "_applied" in (previous_config or {})):
            normalized["_applied"] = applied
        project.project_config = normalized
        session.add(project)
        # Deployment ORM guards and required snapshot failures precede the response.
        await session.flush()
    except ProjectConfigError as exc:
        raise project_error_http(exc) from exc
    except HTTPException:
        raise
    except Exception as exc:
        if is_database_lock_error(exc):
            raise HTTPException(409, "The project changed during save. Reload and try again.") from exc
        await araise_if_deployment_guard_error_or_skip(exc, log_message="op=project_type_save")
        await logger.aexception("Project type save failed for project %s", project.id)
        raise HTTPException(500, "Could not save project configuration.") from exc
    else:
        return result
