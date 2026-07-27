import importlib

from fastapi import status
from httpx import AsyncClient


async def test_get_starter_projects(client: AsyncClient, logged_in_headers):
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    result = response.json()

    assert response.status_code == status.HTTP_200_OK, response.text
    assert isinstance(result, list), "The result must be a list"


EXPECTED_STARTER_PROJECTS = {
    "Basic Prompting": "Perform basic prompting with an OpenAI model.",
    "Blog Writer": (
        "Write blog posts from web references using an Agent. URL fetches references, you provide the "
        "topic via Chat Input, and the Agent writes a grounded post. Core components only."
    ),
    "Document Q&A": (
        "Ask questions about your own document using a built-in Knowledge Base (RAG). File ingests into "
        "the KB; an Agent answers from retrieved context. No external vector database required."
    ),
    "Memory Chatbot": (
        "Create a chatbot that saves and references previous messages, enabling the model to maintain "
        "context throughout the conversation."
    ),
    "Vector Store RAG": "Load your data for chat context with Retrieval Augmented Generation.",
}


async def test_get_starter_projects_expose_canonical_metadata(client: AsyncClient, logged_in_headers):
    """Each starter project must expose its canonical name and description.

    Without a populated top-level name, API clients cannot select a template by name.
    Comparing the full mapping also catches a graph paired with the wrong metadata.
    """
    response = await client.get("api/v1/starter-projects/", headers=logged_in_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    result = response.json()

    assert len(result) == len(EXPECTED_STARTER_PROJECTS), (
        f"Expected {len(EXPECTED_STARTER_PROJECTS)} starter projects, got {len(result)}"
    )

    names = [project["name"] for project in result]
    assert len(set(names)) == len(names), f"Starter project names must be unique, got: {names}"

    actual = {project["name"]: project["description"] for project in result}
    assert actual == EXPECTED_STARTER_PROJECTS

    # ``endpoint_name`` used to be stringified unconditionally, yielding the literal "None".
    # The response model always emits the field, so it must be present and null here.
    endpoint_names = [project["endpoint_name"] for project in result]
    assert endpoint_names == [None] * len(result), (
        f"endpoint_name must be null, not the string 'None': {endpoint_names}"
    )


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
