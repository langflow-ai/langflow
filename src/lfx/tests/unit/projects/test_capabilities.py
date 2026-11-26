"""Capabilities and reference rules belong to declarations, including plugin types."""

from dataclasses import replace
from uuid import uuid4

import pytest
from lfx.inputs.inputs import StrInput
from lfx.projects import ProjectTypeDefinition, ProjectTypeField, get_project_type, register_project_type
from lfx.projects.references import field_references


class LibraryType(ProjectTypeDefinition):
    name = "library"
    display_name = "Library"
    icon = "Book"
    allows_empty_project = True
    exportable = False
    panels = ("reports",)
    fields = (
        ProjectTypeField(
            name="sources",
            input=StrInput(name="sources", list=True),
            references="document-library",
        ),
    )


def test_custom_capabilities_and_reference_target_survive_registration():
    register_project_type(LibraryType)
    definition = get_project_type("library")
    assert definition.allows_empty_project is True
    assert definition.exportable is False
    assert definition.panels == ("reports",)
    assert definition.to_template()["sources"]["references"] == "document-library"


@pytest.mark.parametrize(
    ("attribute", "value", "error"),
    [
        ("allows_empty_project", "yes", TypeError),
        ("exportable", 1, TypeError),
        ("panels", ["reports"], ValueError),
        ("panels", ("reports", "reports"), ValueError),
        ("panels", (" ",), ValueError),
    ],
)
def test_invalid_capabilities_do_not_register(attribute, value, error):
    class InvalidType(LibraryType):
        name = "invalid-library"

    setattr(InvalidType, attribute, value)
    with pytest.raises(error, match="must declare"):
        register_project_type(InvalidType)


def test_reference_type_is_checked_without_resolving_other_types_during_registration():
    field = LibraryType.fields[0]
    reference = {"project_id": str(uuid4()), "revision": "a" * 64}
    assert field_references(field, [reference])[0].expected_type == "document-library"
    assert "expected_type" not in reference
    with pytest.raises(ValueError, match="requires references"):
        field_references(field, [{**reference, "expected_type": "tool-pack"}])
    with pytest.raises(ValueError, match="Select each project once"):
        field_references(field, [reference, reference])
    with pytest.raises(ValueError, match="needs a list"):
        field_references(field, reference)
    single = replace(field, input=StrInput(name="source"))
    assert field_references(single, reference)[0].project_id == field_references(field, [reference])[0].project_id


@pytest.mark.parametrize("target", [None, 7, "  "])
def test_invalid_reference_target_does_not_register(target):
    class InvalidType(LibraryType):
        name = "invalid-reference"
        fields = (replace(LibraryType.fields[0], references=target),)

    with pytest.raises(ValueError, match="referenced project type"):
        register_project_type(InvalidType)
