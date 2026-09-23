"""The shipped research composition runs real tool graphs against offline source responses."""

import json
import re
from html import escape
from pathlib import Path
from uuid import UUID

import httpx
import pytest
import requests
from fastapi import HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langflow.services.database.models.folder.model import Folder
from langflow.services.deps import session_scope
from lfx.graph.graph.base import Graph
from lfx.projects.artifacts import SourcedReport
from lfx.projects.starters import RESEARCH_INSTRUCTIONS
from pydantic import Field
from sqlmodel import select

from tests.unit.api.v1.test_project_composition_archives import download, upload
from tests.unit.api.v1.test_project_config_write_through import stored_flow

SOURCES = json.loads((Path(__file__).parent / "fixtures" / "research_sources.json").read_text())


@pytest.fixture
def offline_research_web(monkeypatch):
    from lfx.utils import ssrf_protection, ssrf_transport

    visited = []
    pages = {item["url"]: item for item in SOURCES}

    def validate(url, **kwargs):  # noqa: ARG001
        assert url in pages, "The offline fixture may read only its included sources."
        return url, ["93.184.216.34"]

    def page(request):
        visited.append(str(request.url))
        source = pages[str(request.url)]
        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text=f"<html><title>{escape(source['title'])}</title><body><p>{escape(source['text'])}</p></body></html>",
            request=request,
        )

    def search(url, **kwargs):
        assert url == "https://html.duckduckgo.com/html/"
        assert kwargs["params"]["q"]
        response = requests.Response()
        response.status_code = 200
        response.headers["content-type"] = "text/html"
        response._content = "".join(
            f'<div class="result"><a class="result__a" href="{item["url"]}">{item["title"]}</a>'
            '<div class="result__snippet">Offline discovery fixture; read the source.</div></div>'
            for item in SOURCES
        ).encode()
        return response

    monkeypatch.setattr(requests, "get", search)
    monkeypatch.setattr(ssrf_protection, "validate_and_resolve_url", validate)
    monkeypatch.setattr(
        ssrf_transport,
        "create_ssrf_protected_client",
        lambda *_a, **_kw: httpx.AsyncClient(transport=httpx.MockTransport(page)),
    )
    monkeypatch.setattr(
        ssrf_transport,
        "create_ssrf_protected_sync_client",
        lambda *_a, **_kw: httpx.Client(transport=httpx.MockTransport(page)),
    )
    return visited


class OfflineResearchModel(BaseChatModel):
    tools: dict = Field(default_factory=dict)

    @property
    def _llm_type(self):
        return "offline-research-starter-verification"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        for tool in tools:
            assert "harness_tool_pack" in (tool.metadata or {}), (tool.name, sorted(tool.metadata or {}))
            name = tool.metadata["harness_tool_pack"]["tool"]["name"]
            self.tools["search" if name.startswith("Search sources") else "read"] = tool.name
        assert len(self.tools) == 2
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        results = [message for message in messages if isinstance(message, ToolMessage)]
        assert all(message.status != "error" for message in results), [
            str(message.content)[:250] for message in results
        ]
        step = len(results)
        if step == 3:
            citations = list(dict.fromkeys(re.findall(r"source-[a-f0-9]{24}", str([item.content for item in results]))))
            assert len(citations) == 2
            message = AIMessage(
                content=(
                    "## Offline research verification\n\nSaved graph state supports resuming an execution. "
                    f"[@{citations[0]}]\n\nApproval is separate from reversing external effects. [@{citations[1]}]\n\n"
                    "These conclusions exercise synthetic source fixtures; no live research was performed."
                )
            )
        else:
            tool = "search" if step == 0 else "read"
            field = "ChatInput-query~input_value" if step == 0 else "ChatInput-url~input_value"
            value = "checkpoints and approvals" if step == 0 else SOURCES[step - 1]["url"]
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": self.tools[tool],
                        "args": {"flow_tweak_data": {field: value}},
                        "id": f"starter-call-{step}",
                    }
                ],
            )
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.mark.parametrize("roundtrip", [False, True])
async def test_research_starter_runs_tools_and_saves_report_before_and_after_handoff(
    client, logged_in_headers, active_user, offline_research_web, roundtrip
):
    response = await client.post("/api/v1/projects/starters/research", headers=logged_in_headers)
    assert response.status_code == 201, response.text[:500]
    project = response.json()
    assert project["project_type"] == "agent-harness"
    if roundtrip:
        original_project = project["id"]
        imported = await upload(client, logged_in_headers, await download(client, logged_in_headers, original_project))
        assert imported.status_code == 201, imported.text[:500]
        project = (
            await client.get(f"/api/v1/projects/{imported.json()[0]['folder_id']}", headers=logged_in_headers)
        ).json()
        assert project["id"] != original_project
    config = project["project_config"]
    assert config["system_prompt"] == RESEARCH_INSTRUCTIONS
    assert config["tools"] == []
    pack_id = config["tool_packs"][0]["project_id"]
    async with session_scope() as session:
        pack = await session.get(Folder, UUID(pack_id))
        assert pack.project_type == "tool-pack"
        assert pack.user_id == active_user.id
        assert len(pack.project_config["tools"]) == 2
    flow = await stored_flow(config["agent_flow_id"])
    graph = Graph.from_payload(flow.data, flow_id=str(flow.id), user_id=str(active_user.id))
    graph.get_vertex("Agent-research").update_raw_params({"model": OfflineResearchModel()}, overwrite=True)
    async for result in graph.async_start():
        assert getattr(result, "valid", True)
    value = graph.get_vertex("SourcedReport-report").custom_component.get_output("artifact").value
    report = SourcedReport.model_validate(value.data["artifact"])
    report.require_resolved_citations()
    assert len(report.sources) == 2
    assert len(report.tool_dependencies) == 3
    assert all(str(use.binding.reference.project_id) == pack_id for use in report.tool_dependencies)
    assert {source.uri for source in report.sources} == {source["url"] for source in SOURCES}
    for source in report.sources:
        assert source.title == source.uri
        original = next(item for item in SOURCES if item["url"] == source.uri)
        assert original["text"] in source.content
    assert report.configurations[0].model.name == "offline-research-starter-verification"
    assert RESEARCH_INSTRUCTIONS in report.configurations[0].system_prompt
    assert set(offline_research_web) == {source["url"] for source in SOURCES}
    downloaded = await client.get(
        f"/api/v1/projects/{project['id']}/reports/{flow.id}/{report.id}/download/json", headers=logged_in_headers
    )
    assert downloaded.status_code == 200
    assert SourcedReport.model_validate(downloaded.json()) == report


async def test_starter_catalog_preserves_project_types_and_rejects_unknown_starters(client, logged_in_headers):
    types = (await client.get("/api/v1/projects/types", headers=logged_in_headers)).json()
    harness = next(item for item in types if item["name"] == "agent-harness")
    assert harness["starters"][0]["name"] == "research"
    assert all(not item["starters"] for item in types if item["name"] != "agent-harness")
    response = await client.post("/api/v1/projects/starters/unknown", headers=logged_in_headers)
    assert response.status_code == 404


@pytest.mark.parametrize("failure_stage", ["permission", "second_project"])
async def test_starter_creation_enforces_permission_and_rolls_back_partial_compositions(
    client, logged_in_headers, active_user, monkeypatch, failure_stage
):
    from langflow.api.v1 import project_compositions, projects
    from langflow.services.database.models.flow.model import Flow
    from langflow.services.database.models.flow_version.model import FlowVersion

    async def resources():
        async with session_scope() as session:
            return {
                model.__name__: {
                    row.id for row in (await session.exec(select(model).where(model.user_id == active_user.id))).all()
                }
                for model in (Folder, Flow, FlowVersion)
            }

    before = await resources()
    calls = 0

    async def deny(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if failure_stage == "permission" or calls == 2:
            raise HTTPException(403, "Creation denied by the test policy.")

    if failure_stage == "permission":
        monkeypatch.setattr(projects, "ensure_project_permission", deny)
    else:
        monkeypatch.setattr(project_compositions, "enforce_pre_creation", deny)
    response = await client.post("/api/v1/projects/starters/research", headers=logged_in_headers)
    assert response.status_code == 403
    assert await resources() == before
