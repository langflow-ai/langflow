import importlib

from fastapi import status
from httpx import AsyncClient


async def test_get_starter_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK, response.text
    assert isinstance(result, list), "The result must be a list"


async def test_get_starter_projects_are_named(client: AsyncClient, logged_in_headers):
    """Every starter project must expose a non-empty, unique top-level name.

    Without this, API clients cannot select a template by name.
    """
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    result = response.json()

    assert result, "Expected at least one starter project"

    names = [project["name"] for project in result]
    assert all(names), f"Every starter project needs a name, got: {names}"
    assert len(set(names)) == len(names), f"Starter project names must be unique, got: {names}"

    descriptions = [project["description"] for project in result]
    assert all(descriptions), f"Every starter project needs a description, got: {descriptions}"

    # ``endpoint_name`` used to be stringified unconditionally, yielding the literal "None".
    endpoint_names = [project["endpoint_name"] for project in result]
    assert "None" not in endpoint_names, f"endpoint_name must be null, not the string 'None': {endpoint_names}"


def test_starter_projects_keep_optional_crewai_exports_lazy():
    from langflow.initial_setup import starter_projects

    optional_crewai_starters = {
        "complex_agent_graph",
        "hierarchical_tasks_agent_graph",
        "sequential_tasks_agent_graph",
    }
    for starter_name in optional_crewai_starters:
        starter_projects.__dict__.pop(starter_name, None)

    reloaded_starter_projects = importlib.reload(starter_projects)

    assert optional_crewai_starters.isdisjoint(reloaded_starter_projects.__dict__)
