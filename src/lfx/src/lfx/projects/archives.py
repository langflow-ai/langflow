"""Project archive lifecycle with closed references and type-owned configuration hooks."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lfx.projects.archive_context import ArchiveContext, ArchiveMapping
from lfx.projects.archive_graphs import FlowArchiveGraph
from lfx.projects.bindings import flow_revision
from lfx.projects.references import field_references
from lfx.projects.registry import get_project_type

MAX_COMPOSITION_PROJECTS = 100
MAX_COMPOSITION_FLOWS = 500


class ArchivedProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str = Field(min_length=1)
    description: str | None = None
    project_type: str = Field(min_length=1)
    project_config: dict | None = None
    flows: list[dict]


class ProjectComposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["langflow-composition"] = "langflow-composition"
    version: Literal[1] = 1
    root_project_id: UUID
    projects: list[ArchivedProject] = Field(min_length=1, max_length=MAX_COMPOSITION_PROJECTS)


class CompositionGraph(FlowArchiveGraph):
    """Validate types and graph contracts before relocating any included resource."""

    def _context(self, project_id: str, **kwargs) -> ArchiveContext:
        return ArchiveContext(
            project_id=project_id,
            projects={key: value.model_dump(mode="json") for key, value in self.projects.items()},
            flows=deepcopy(self.flows),
            owners=dict(self.owners),
            **kwargs,
        )

    def validate(self, *, allow_missing_secrets: bool = False) -> None:
        for project_id, project in self.projects.items():
            definition = get_project_type(project.project_type)
            if not definition.exportable:
                msg = "An archived project type does not support import or export."
                raise ValueError(msg)
            ctx = self._context(project_id, allow_missing_secrets=allow_missing_secrets)
            # Reference integrity is host-owned, even if a plugin overrides validation.
            declared = tuple(
                ref
                for field in definition.fields
                if field.references
                for ref in field_references(field, (project.project_config or {}).get(field.name))
            )
            for reference in (*declared, *definition.archive_references(deepcopy(project.project_config))):
                ctx.project(str(reference.project_id), expected_type=reference.expected_type)
            for reference in definition.archive_sources(deepcopy(project.project_config)):
                if flow_revision(ctx.source(str(reference.flow_id))["data"]) != reference.revision:
                    msg = "A reviewed archive source changed. Review and save it before exporting."
                    raise ValueError(msg)
            definition.validate_archive(deepcopy(project.project_config), ctx)
        self.validate_flows(allow_missing_secrets=allow_missing_secrets)

    def relocate(
        self,
        *,
        project_ids: dict[str, str],
        flow_ids: dict[str, str],
        version_ids: dict[str, str],
        flow_names: dict[str, str] | None = None,
        project_names: dict[str, str] | None = None,
        operation: Literal["export", "import"] = "import",
    ) -> ProjectComposition:
        if operation not in {"export", "import"}:
            msg = "Unknown archive operation."
            raise ValueError(msg)
        result = self.relocate_flows(
            project_ids=project_ids,
            flow_ids=flow_ids,
            version_ids=version_ids,
            flow_names=flow_names,
            project_names=project_names,
        )
        original_ids = {new_id: old_id for old_id, new_id in flow_ids.items()}
        relocated_flows = {original_ids[str(flow["id"])]: flow for project in result.projects for flow in project.flows}
        projects = {str(project.id): project.model_dump(mode="json") for project in result.projects}
        for project in result.projects:
            project_id = str(project.id)
            definition = get_project_type(project.project_type)
            mapping = ArchiveMapping(
                project_id=project_id,
                projects=deepcopy(projects),
                flows=deepcopy(relocated_flows),
                owners=dict(self.owners),
                project_ids=dict(project_ids),
                flow_ids=dict(flow_ids),
                version_ids=dict(version_ids),
            )
            config = deepcopy(project.project_config)
            applied = config.pop("_applied", None) if config is not None else None
            hook = definition.export_config if operation == "export" else definition.import_config
            config = hook(config, mapping)
            if config is not None and (not isinstance(config, dict) or "_applied" in config):
                msg = "An archive hook must return a configuration object without host bookkeeping."
                raise ValueError(msg)
            json.dumps(config, allow_nan=False)
            if isinstance(applied, dict) and config is not None:
                config["_applied"] = {flow_ids[key]: value for key, value in applied.items() if key in flow_ids}
            project.project_config = deepcopy(config)
            project.id = UUID(project_ids[project_id])
        result.root_project_id = UUID(project_ids[str(result.root_project_id)])
        CompositionGraph(result).validate(allow_missing_secrets=True)
        return result
