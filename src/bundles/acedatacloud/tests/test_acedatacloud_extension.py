from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from lfx.custom.utils import create_component_template
from lfx.extension.loader import load_extension
from lfx.extension.manifest import load_manifest
from lfx.schema.data import Data
from lfx_acedatacloud.client import AceAPIError, normalize, post_json, scrub
from lfx_acedatacloud.components.acedatacloud.gpt_image import GPTImageGenerateComponent
from lfx_acedatacloud.components.acedatacloud.gpt_image_task import (
    GPTImageRetrieveTaskComponent,
)
from lfx_acedatacloud.components.base import _payload
from lfx_acedatacloud.provider import (
    API_BASE,
    ChatAceDataCloud,
    _chat_model_ids,
    _is_chat_model,
    load_catalog,
)
from lfx_acedatacloud.specs import SERVICES

ROOT = Path(__file__).resolve().parents[1] / "src" / "lfx_acedatacloud"


def test_manifest_loads_every_named_service_and_its_task_reader() -> None:
    result = load_extension(ROOT)
    assert not result.errors
    names = {component.class_name for component in result.components}
    assert len(names) == 32
    for slug, spec in SERVICES.items():
        related = [component for component in result.components if component.klass.service_name == slug]
        assert len(related) == (2 if spec.task_path else 1), slug
        assert all(component.bundle == "ace_data_cloud" for component in related)


def test_manifest_has_provider_and_bundle() -> None:
    manifest = load_manifest(ROOT).manifest
    assert manifest.providers[0].provider_id == "acedatacloud"
    assert manifest.bundles[0].name == "ace_data_cloud"


def test_ui_templates_keep_generation_and_retrieval_forms_separate() -> None:
    generated, _ = create_component_template(component_extractor=GPTImageGenerateComponent())
    retrieved, _ = create_component_template(component_extractor=GPTImageRetrieveTaskComponent())
    assert generated["display_name"] == "GPT Image Generate"
    assert retrieved["display_name"] == "GPT Image Retrieve Task"
    assert "prompt" in generated["field_order"]
    assert "task_id" not in generated["field_order"]
    assert "task_id" in retrieved["field_order"]
    assert "prompt" not in retrieved["field_order"]


def test_branded_chat_model_cannot_change_api_host() -> None:
    model = ChatAceDataCloud(model="gpt-4.1-mini", api_key="test-only", base_url="https://example.org/v1")
    assert str(model.openai_api_base).rstrip("/") == API_BASE
    assert any(item["name"] == "gpt-4.1-mini" for item in load_catalog())
    assert _is_chat_model({"id": "gpt-4.1-mini", "modalities": {"output": ["text"]}})
    assert not _is_chat_model({"id": "gpt-image-2", "modalities": {"output": ["image"]}})
    assert len(_chat_model_ids()) == 84


def test_protocol_special_cases() -> None:
    def sample(slug: str, **values: object) -> tuple[str, dict, dict]:
        return _payload(SERVICES[slug], SimpleNamespace(**values))

    path, body, headers = sample("fish_audio", text="Hello", model="s2-pro")
    assert path == "/fish/tts"
    assert headers["model"] == "s2-pro"
    assert "model" not in body
    path, body, _ = sample("seedance", prompt="a cube rotates")
    assert path == "/seedance/videos"
    assert body["content"] == [{"type": "text", "text": "a cube rotates"}]
    assert "prompt" not in body
    path, body, _ = sample("minimax_h3", prompt="a cube rotates")
    assert path == "/minimax/videos"
    assert isinstance(body["content"], list)
    path, body, _ = sample("wan", prompt="a cube rotates")
    assert path == "/wan/videos"
    assert body["model"] == "wan3.0-video"
    assert body["audio"] is False
    assert body["ratio"] == "16:9"
    path, body, _ = sample(
        "face_transform",
        action="swap",
        source_image_url="https://example.org/a.png",
        target_image_url="https://example.org/b.png",
    )
    assert path == "/face/swap"
    assert "action" not in body
    assert "image_url" not in body
    with pytest.raises(ValueError, match="Image size applies only"):
        sample("google_search", query="test", extra_parameters={"image_size": "large"})
    with pytest.raises(ValueError, match="Unsupported additional parameter"):
        sample(
            "gpt_image",
            prompt="test",
            extra_parameters={"url": "https://elsewhere.example"},
        )


def test_submit_once_and_retrieve_same_task_without_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, dict]] = []

    async def fake_post(path: str, key: str, body: dict, *, headers: dict | None = None) -> dict:
        assert key == "test-secret"
        assert headers in (None, {})
        calls.append((path, body))
        if path == "/openai/images/generations":
            return {"task_id": "task-1", "status": "pending"}
        return {
            "id": "task-1",
            "finished_at": "2026-10-09T00:00:00Z",
            "response": {
                "status": "succeeded",
                "data": {"image_url": "https://example.org/result.png"},
            },
        }

    monkeypatch.setattr("lfx_acedatacloud.components.base.post_json", fake_post)
    generator = GPTImageGenerateComponent()
    generator.api_key = "test-secret"
    generator.prompt = "A blue paper sphere"
    submitted = asyncio.run(generator.run())
    assert submitted.data["task_id"] == "task-1"
    assert submitted.data["status"] == "pending"
    query = GPTImageRetrieveTaskComponent()
    query.api_key = "test-secret"
    query.submitted_task = submitted
    query.wait_seconds = 0
    completed = asyncio.run(query.run())
    assert completed.data["status"] == "succeeded"
    assert completed.data["media_urls"] == ["https://example.org/result.png"]
    assert [path for path, _ in calls] == [
        "/openai/images/generations",
        "/openai/tasks",
    ]
    assert calls[-1][1] == {"action": "retrieve", "id": "task-1"}


def test_task_reader_rejects_cross_service_task_before_http() -> None:
    query = GPTImageRetrieveTaskComponent()
    query.api_key = "test-secret"
    query.submitted_task = Data(data={"service": "suno", "task_id": "task-1"})
    with pytest.raises(ValueError, match="different"):
        asyncio.run(query.run())


def test_pending_preview_is_not_a_completed_result() -> None:
    result = normalize(
        {
            "finished_at": None,
            "response": {"image_url": "https://example.org/preview.png"},
        },
        service="gpt_image",
        retrieved=True,
        requested_task_id="task-1",
    )
    assert result["status"] == "pending"
    assert not result["success"]
    assert result["media_urls"] == []
    failed = normalize(
        {
            "finished_at": "2026-10-09T00:00:00Z",
            "response": {"status": "failed", "error": {"message": "private"}},
        },
        service="gpt_image",
        retrieved=True,
        requested_task_id="task-1",
    )
    assert failed["status"] == "failed"
    assert "private" not in str(failed)


def test_result_scrubbing_removes_credentials_and_internal_routes() -> None:
    data = scrub(
        {
            "api_key": "secret",
            "supplier": "hidden",
            "data": [{"image_url": "https://example.org/a.png", "request_body": "secret"}],
        }
    )
    assert "secret" not in str(data)
    assert "hidden" not in str(data)
    assert data["data"][0]["image_url"] == "https://example.org/a.png"


def test_http_errors_never_include_token_or_service_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(403, json={"message": "test-secret should stay private"})
    )
    original_client = httpx.AsyncClient

    def make_client(**kwargs: object) -> httpx.AsyncClient:
        return original_client(transport=transport, **kwargs)

    monkeypatch.setattr("lfx_acedatacloud.client.httpx.AsyncClient", make_client)
    with pytest.raises(AceAPIError) as caught:
        asyncio.run(post_json("/serp/google", "test-secret", {"query": "test"}))
    assert "403" in str(caught.value)
    assert "test-secret" not in str(caught.value)
