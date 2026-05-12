"""Skill component — read-only knowledge wrapped as an MCP resource.

Skills are MCP resources distinguished by mime type
``application/vnd.langflow.skill+json`` (or ``text/markdown`` with a
``langflow-skill`` profile parameter). They carry prompt fragments, domain
ontologies, runbooks — content an agent needs but should not call as a tool.

See ``docs/docs/Agents/mcp-catalog-and-long-running.mdx#skills`` for the
design rationale.
"""

from __future__ import annotations

from typing import Any

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, MultilineInput, Output
from lfx.schema.data import Data

_DEFAULT_SKILL_MIME = "application/vnd.langflow.skill+json"
_MARKDOWN_SKILL_MIME = "text/markdown"
_VALID_MIME_TYPES = (_DEFAULT_SKILL_MIME, _MARKDOWN_SKILL_MIME)


class SkillComponent(Component):
    display_name: str = "Skill"
    description: str = (
        "Wrap read-only knowledge (markdown or JSON) as an MCP resource that "
        "agents can fetch but cannot call. Plugs into FastMCP Server's resources input."
    )
    documentation: str = "https://docs.langflow.org/mcp-catalog-and-long-running"
    icon = "BookOpen"
    name = "Skill"

    inputs = [
        MessageTextInput(
            name="skill_name",
            display_name="Skill Name",
            info="Human-readable name. Becomes the MCP resource ``name`` field.",
            required=True,
        ),
        MessageTextInput(
            name="uri",
            display_name="URI",
            info=("Resource URI. Must use the langflow-skill:// scheme. Example: langflow-skill://my-runbook"),
            required=True,
        ),
        DropdownInput(
            name="mime_type",
            display_name="Content Type",
            options=list(_VALID_MIME_TYPES),
            value=_DEFAULT_SKILL_MIME,
            info="application/vnd.langflow.skill+json for structured data; text/markdown for prose.",
        ),
        MultilineInput(
            name="content",
            display_name="Content",
            info="Skill body. Markdown or JSON depending on Content Type.",
            required=True,
        ),
        MessageTextInput(
            name="description",
            display_name="Description",
            info="Optional short summary of what this skill provides.",
            required=False,
        ),
    ]

    outputs = [
        Output(display_name="Resource", name="resource", method="resolve_resource"),
    ]

    def _validate_uri(self, uri: str) -> str:
        # Defensive: prevent path traversal in URIs that may be served from disk
        # later by FastMCP. The langflow-skill:// scheme is opaque, so reject
        # any traversal sequences in the body.
        if ".." in uri or uri.startswith(("file://", "/")):
            msg = f"invalid skill URI {uri!r} — must use langflow-skill:// scheme without traversal"
            raise ValueError(msg)
        if not uri.startswith("langflow-skill://"):
            msg = f"skill URI must start with langflow-skill://, got {uri!r}"
            raise ValueError(msg)
        return uri

    async def resolve_resource(self) -> Data:
        if not self.skill_name:
            msg = "skill_name is required"
            raise ValueError(msg)
        if not self.uri:
            msg = "uri is required"
            raise ValueError(msg)
        if not self.content:
            msg = "content is required"
            raise ValueError(msg)
        if self.mime_type not in _VALID_MIME_TYPES:
            msg = f"mime_type must be one of {_VALID_MIME_TYPES}"
            raise ValueError(msg)
        uri = self._validate_uri(str(self.uri))

        payload: dict[str, Any] = {
            "uri": uri,
            "name": str(self.skill_name),
            "mime_type": str(self.mime_type),
            "description": str(self.description or ""),
            "content": str(self.content),
            "kind": "skill",
        }
        return Data(data=payload)
