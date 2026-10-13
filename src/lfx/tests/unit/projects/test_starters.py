"""Starter declarations stay lazy and unambiguous across installed types."""

from importlib import import_module

import pytest
from lfx.projects import ProjectTypeDefinition
from lfx.projects.starters import ProjectStarter, get_project_starter, project_starters


def test_starter_catalog_does_not_build_graphs(monkeypatch):
    def build():
        pytest.fail("Catalog lookup must not build graphs")

    starter = ProjectStarter("support-inbox", "Support inbox", "Start here", build)

    class SupportType(ProjectTypeDefinition):
        name = "support-desk"

        def starters(self):
            return (starter,)

    monkeypatch.setattr(import_module("lfx.projects.registry"), "all_project_types", lambda: (SupportType(),))
    definition, found = get_project_starter("support-inbox")
    assert definition.name == "support-desk"
    assert found.to_dict() == {"name": "support-inbox", "display_name": "Support inbox", "description": "Start here"}
    with pytest.raises(LookupError, match="not found"):
        get_project_starter("missing")


def test_duplicate_starter_names_are_rejected(monkeypatch):
    starter = ProjectStarter("same-name", "Start", "Description", lambda: None)

    class First(ProjectTypeDefinition):
        name = "first"

        def starters(self):
            return (starter,)

    class Second(First):
        name = "second"

    monkeypatch.setattr(import_module("lfx.projects.registry"), "all_project_types", lambda: (First(), Second()))
    with pytest.raises(ValueError, match="declared more than once"):
        project_starters()


@pytest.mark.parametrize("name", ["UPPER", "path/to/file", "", " whitespace "])
def test_starter_names_are_route_slugs(name):
    with pytest.raises(ValueError, match="lowercase slug"):
        ProjectStarter(name, "Start", "Description", lambda: None)


def test_async_starter_factory_is_rejected():
    async def build():
        return None

    with pytest.raises(TypeError, match="synchronous"):
        ProjectStarter("async-start", "Start", "Description", build)
