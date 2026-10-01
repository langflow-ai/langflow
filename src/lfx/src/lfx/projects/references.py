"""Reviewed project identities and the target type declared by a form field."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from lfx.projects.schema import ProjectTypeField


class ProjectReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: UUID
    expected_type: str = Field(min_length=1)
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")


def field_references(field: ProjectTypeField, value: object) -> tuple[ProjectReference, ...]:
    """Validate shape and declared type. Access and revision checks belong to the host."""
    if not field.references:
        msg = f"Field {field.name!r} does not declare a project reference."
        raise ValueError(msg)
    if value is None:
        return ()
    if getattr(field.input, "is_list", False):
        if not isinstance(value, list):
            msg = f"Field {field.name!r} needs a list of reviewed project references."
            raise ValueError(msg)
        values = value
    else:
        values = [value]
    references = tuple(
        ProjectReference.model_validate({"expected_type": field.references, **item})
        if isinstance(item, dict)
        else ProjectReference.model_validate(item)
        for item in values
    )
    if any(reference.expected_type != field.references for reference in references):
        msg = f"Field {field.name!r} requires references to {field.references!r} projects."
        raise ValueError(msg)
    if len({reference.project_id for reference in references}) != len(references):
        msg = f"Select each project once in {field.name!r}."
        raise ValueError(msg)
    return references
