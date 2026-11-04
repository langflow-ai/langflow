"""The editor's Update posts the saved node to /api/v1/custom_component and replaces it with the response."""

import inspect
import json
from pathlib import Path

import pytest
from fastapi import status
from httpx import AsyncClient
from lfx.components.files_and_knowledge import file as file_module
from lfx.components.input_output.text import TextInputComponent
from lfx.components.models_and_agents.prompt import PromptComponent
from lfx.custom.custom_component.component import Component
from lfx.custom.utils import build_custom_component_template
from lfx.custom.validate import extract_class_name
from lfx.graph import Graph
from lfx.services.deps import get_settings_service
from lfx.template import utils as template_utils

STARTER_FLOWS_V1_11_6 = Path(__file__).parents[5] / "lfx" / "tests" / "fixtures" / "starter_flows" / "v1.11.6"
STARTER_PROJECTS = Path(__file__).parents[4] / "base" / "langflow" / "initial_setup" / "starter_projects"

SEO_V1_11_6 = STARTER_FLOWS_V1_11_6 / "seo_keyword_generator.json"
TWITTER_V1_11_6 = STARTER_FLOWS_V1_11_6 / "twitter_thread_generator.json"
TWITTER_STARTER = STARTER_PROJECTS / "Twitter Thread Generator.json"
SEO_STARTER = STARTER_PROJECTS / "SEO Keyword Generator.json"

# Flows saved before nodes named their component class carry only their code.
SEO_FLOWS = [
    pytest.param(SEO_V1_11_6, id="seo-keyword-generator-v1.11.6"),
    pytest.param(SEO_STARTER, id="seo-keyword-generator-starter"),
]

# Saved code that parsing would cache, blow up in memory, or fail on with MemoryError.
SAVED_CODE_HEADER = "from lfx.custom import Component\nclass PromptComponent(Component):\n    pass\n"
SAVED_CODE_PROBES = [
    pytest.param(SAVED_CODE_HEADER + "#" * 2_000_000, id="2-mb-comment"),
    pytest.param(SAVED_CODE_HEADER + "a;" * 100_000, id="many-statements"),
    pytest.param(SAVED_CODE_HEADER + "x = " + "-" * 10_000 + "1\n", id="deeply-nested"),
]


def _saved_prompt(flow_path: Path) -> dict:
    flow = json.loads(flow_path.read_text(encoding="utf-8"))
    return next(node for node in flow["data"]["nodes"] if node["data"]["type"] == "Prompt")["data"]


async def _editor_update(client: AsyncClient, headers: dict, saved_node: dict, component=PromptComponent) -> dict:
    code = Path(inspect.getsourcefile(component)).read_text(encoding="utf-8")
    response = await client.post(
        "api/v1/custom_component", json={"code": code, "frontend_node": saved_node}, headers=headers
    )
    assert response.status_code == status.HTTP_200_OK, response.text
    return response.json()["data"]


@pytest.mark.parametrize(
    "flow_path",
    [
        pytest.param(SEO_V1_11_6, id="seo-keyword-generator-v1.11.6"),
        pytest.param(TWITTER_V1_11_6, id="twitter-thread-generator-v1.11.6"),
        pytest.param(TWITTER_STARTER, id="twitter-thread-generator-starter"),
    ],
)
async def test_editor_update_keeps_prompt_variables_and_values(
    client: AsyncClient, logged_in_headers: dict, flow_path: Path
):
    saved = _saved_prompt(flow_path)["node"]
    variables = saved["custom_fields"]["template"]
    assert len(variables) == 6
    assert all(saved["template"][name]["value"] for name in variables)

    updated = await _editor_update(client, logged_in_headers, saved)

    assert sorted(updated["custom_fields"]["template"]) == sorted(variables)
    assert {name: updated["template"].get(name, {}).get("value") for name in variables} == {
        name: saved["template"][name]["value"] for name in variables
    }


@pytest.mark.parametrize(
    "flow_path",
    [
        pytest.param(TWITTER_V1_11_6, id="twitter-thread-generator-v1.11.6"),
        pytest.param(TWITTER_STARTER, id="twitter-thread-generator-starter"),
    ],
)
async def test_updated_twitter_thread_prompt_still_runs(client: AsyncClient, logged_in_headers: dict, flow_path: Path):
    """Its template uses {PROFILE_TYPE} as well as {{PROFILE_TYPE}}, which once made the parser drop every variable."""
    saved = _saved_prompt(flow_path)
    updated = await _editor_update(client, logged_in_headers, saved["node"])
    node_id = saved["id"]
    graph = Graph.from_payload(
        {"nodes": [{"id": node_id, "type": "genericNode", "data": {**saved, "node": updated}}], "edges": []},
        flow_id="twitter-thread-generator",
    )

    async for _ in graph.async_start():
        pass

    prompt = graph.get_vertex(node_id).built_object["prompt"]
    assert saved["node"]["template"]["PROFILE_TYPE"]["value"] in prompt.text


@pytest.mark.parametrize("flow_path", SEO_FLOWS)
async def test_code_swapped_for_another_component_drops_the_prompt_variables(
    client: AsyncClient, logged_in_headers: dict, flow_path: Path
):
    """The code editor posts to the same route, so the new component must not inherit the Prompt's variables."""
    saved = _saved_prompt(flow_path)["node"]

    updated = await _editor_update(client, logged_in_headers, saved, component=TextInputComponent)

    assert not set(saved["custom_fields"]["template"]) & set(updated["template"])
    assert not any(updated.get("custom_fields", {}).values())


@pytest.mark.parametrize("saved_code", SAVED_CODE_PROBES)
async def test_editor_update_never_parses_the_saved_code(client: AsyncClient, logged_in_headers: dict, saved_code: str):
    """The saved node comes from the client, so its code is not parsed (nor cached) to tell which component it is."""
    saved = _saved_prompt(SEO_V1_11_6)["node"]
    variables = saved["custom_fields"]["template"]
    await _editor_update(client, logged_in_headers, saved)
    saved["template"]["code"]["value"] = saved_code
    misses = extract_class_name.cache_info().misses

    updated = await _editor_update(client, logged_in_headers, saved)

    assert extract_class_name.cache_info().misses == misses
    assert {name: updated["template"][name]["value"] for name in variables} == {
        name: saved["template"][name]["value"] for name in variables
    }


async def test_a_variable_no_longer_in_the_template_is_not_brought_back(client: AsyncClient, logged_in_headers: dict):
    """Variables come from the template text: a saved field the template no longer names is not kept."""
    saved = _saved_prompt(SEO_V1_11_6)["node"]
    saved["custom_fields"]["template"].append("gone")
    saved["template"]["gone"] = {**saved["template"][saved["custom_fields"]["template"][0]], "value": "stale"}

    updated = await _editor_update(client, logged_in_headers, saved)

    assert "gone" not in updated["custom_fields"]["template"]
    assert "gone" not in updated["template"]


@pytest.mark.parametrize(
    "flow_path",
    [
        pytest.param(TWITTER_V1_11_6, id="twitter-thread-generator-v1.11.6"),
        pytest.param(TWITTER_STARTER, id="twitter-thread-generator-starter"),
    ],
)
async def test_editing_the_twitter_thread_template_keeps_its_variables(
    client: AsyncClient, logged_in_headers: dict, flow_path: Path
):
    """The template editor rebuilds the variables through the same parser."""
    saved = _saved_prompt(flow_path)["node"]
    template = saved["template"]["template"]["value"]

    response = await client.post(
        "api/v1/validate/prompt",
        json={"name": "template", "template": template + "\n", "frontend_node": saved},
        headers=logged_in_headers,
    )

    assert response.status_code == status.HTTP_200_OK, response.text
    assert sorted(response.json()["frontend_node"]["custom_fields"]["template"]) == sorted(
        saved["custom_fields"]["template"]
    )


@pytest.fixture
def storage_root(tmp_path: Path, monkeypatch) -> Path:
    """A local storage root (config_dir) and cache folder of this test's own."""
    root = (tmp_path / "storage").resolve()
    root.mkdir()
    monkeypatch.setattr(get_settings_service().settings, "config_dir", str(root))
    monkeypatch.setattr(template_utils, "user_cache_dir", lambda _app_name, _app_author: str(tmp_path / "cache"))
    return root


async def test_custom_component_clears_an_overlong_storage_key(
    client, logged_in_headers: dict, active_user, storage_root: Path
) -> None:
    """The response is the cleared field, not a 500 whose body names the storage folder."""
    user_id = str(active_user.id)
    (storage_root / user_id).mkdir()
    code = Path(file_module.__file__).read_text(encoding="utf-8")
    saved, _ = build_custom_component_template(Component(_code=code), user_id=user_id)
    saved["template"]["path"]["value"] = ["report.pdf"]
    saved["template"]["path"]["file_path"] = [f"{user_id}/" + "a" * 300]

    response = await client.post(
        "api/v1/custom_component", json={"code": code, "frontend_node": saved}, headers=logged_in_headers
    )

    assert response.status_code == 200, response.text
    assert str(storage_root) not in response.text
    assert response.json()["data"]["template"]["path"]["file_path"] == ""
