"""Check a declared reference's actual project type after authorizing access."""

from fastapi import HTTPException
from lfx.projects.references import field_references

from langflow.services.authorization import ProjectAction, ensure_project_permission
from langflow.services.authorization.fetch import authorized_or_owner_scoped, deny_to_404
from langflow.services.database.models.folder.model import Folder


async def validate_project_references(session, user, definition, config):
    for field in definition.fields:
        if not field.references:
            continue
        try:
            references = field_references(field, config.get(field.name))
        except ValueError as exc:
            raise HTTPException(422, f"Choose valid {field.references} project references for {field.name}.") from exc
        for reference in references:
            project = await authorized_or_owner_scoped(
                session,
                Folder,
                id_column=Folder.id,
                resource_id=reference.project_id,
                owner_column=Folder.user_id,
                owner_id=user.id,
            )
            if project is None:
                raise HTTPException(404, "Referenced project not found")
            try:
                await ensure_project_permission(
                    user,
                    ProjectAction.READ,
                    project_id=project.id,
                    project_user_id=project.user_id,
                    workspace_id=project.workspace_id,
                )
            except HTTPException as exc:
                raise deny_to_404(exc, "Referenced project not found") from exc
            if project.project_type != field.references:
                raise HTTPException(422, f"Choose a {field.references} project for {field.name}.")
