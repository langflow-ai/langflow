"""Closed, detached archive data. Hooks cannot resolve resources outside this archive."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ArchiveContext:
    project_id: str
    projects: dict[str, dict]
    flows: dict[str, dict]
    owners: dict[str, str]
    allow_missing_secrets: bool = False

    def source(self, flow_id: str, *, local: bool = False) -> dict:
        if flow_id not in self.flows:
            msg = "A referenced flow is missing from the composition archive."
            raise ValueError(msg)
        if local and self.owners[flow_id] != self.project_id:
            msg = "A project binding or local tool must belong to its archived project."
            raise ValueError(msg)
        return deepcopy(self.flows[flow_id])

    def project(self, project_id: str, *, expected_type: str) -> dict:
        project = self.projects.get(project_id)
        if project is None or project["project_type"] != expected_type:
            msg = "A referenced project is missing or has the wrong type in the archive."
            raise ValueError(msg)
        return deepcopy(project)


@dataclass(frozen=True)
class ArchiveMapping(ArchiveContext):
    # Sources retain their old dictionary keys, with relocated IDs and graph data as values.
    project_ids: dict[str, str] = field(default_factory=dict)
    flow_ids: dict[str, str] = field(default_factory=dict)
    version_ids: dict[str, str] = field(default_factory=dict)
