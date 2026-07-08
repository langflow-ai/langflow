import importlib

from fastapi import status
from httpx import AsyncClient


async def test_get_starter_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK, response.text
    assert isinstance(result, list), "The result must be a list"


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
