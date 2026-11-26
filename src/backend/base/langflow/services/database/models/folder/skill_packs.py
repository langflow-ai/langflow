"""Authorize a Skill Pack and validate the reviewed Tool Packs it requires."""

from uuid import UUID

from fastapi import HTTPException
from lfx.projects.skills import skill_pack_manifest

from langflow.services.authorization import FlowAction, ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.folder.model import Folder
from langflow.services.database.models.folder.tool_packs import resolve_tool_pack


async def resolve_skill_pack(session, user, project_id: UUID, *, action=FlowAction.READ):
    project = await authorized_or_owner_scoped(
        session, Folder, id_column=Folder.id, resource_id=project_id, owner_column=Folder.user_id, owner_id=user.id
    )
    if project is None:
        raise HTTPException(404, "Skill Pack not found")
    try:
        await ensure_project_permission(
            user,
            ProjectAction.READ,
            project_id=project.id,
            project_user_id=project.user_id,
            workspace_id=project.workspace_id,
        )
    except HTTPException as exc:
        raise deny_to_404(exc, "Skill Pack not found") from exc
    if project.project_type != "skill-pack":
        raise HTTPException(422, "Choose a project of type Skill Pack.")
    try:
        manifest = skill_pack_manifest(project.id, project.name, project.project_config)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, f"Invalid Skill Pack: {exc}") from exc
    references = {}
    for skill in manifest.skills:
        for reference in skill.tool_packs:
            if reference.project_id not in references:
                current, _ = await resolve_tool_pack(session, user, reference.project_id, action=action)
                references[reference.project_id] = current.reference
            if reference != references[reference.project_id]:
                raise HTTPException(
                    422, f"A Tool Pack used by skill '{skill.name}' changed. Review it in the Skill Pack."
                )
    return manifest
