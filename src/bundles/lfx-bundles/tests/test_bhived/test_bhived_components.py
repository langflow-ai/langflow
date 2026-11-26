"""Unit tests for the bhived components with mocked HTTP calls.

Requests are intercepted by respx at the transport level, so the tests exercise
the real ``bhived`` SDK: endpoints, headers, payloads, retries and error mapping.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest
import respx
from lfx.custom.custom_component.component import Component
from lfx_bundles.bhived.bhived_common import DOCUMENTATION_URL
from lfx_bundles.bhived.bhived_search import BhivedSearchComponent
from lfx_bundles.bhived.bhived_write import BhivedWriteComponent

if TYPE_CHECKING:
    from pathlib import Path

API_URL = "https://mcp.bhived.ai"
# Placeholder credentials for the mocked API (not real keys).
API_KEY = "test-bhived-api-key-placeholder"  # pragma: allowlist secret
SERVER_KEY = "server-bhived-api-key-placeholder"  # pragma: allowlist secret

QUERY_RESPONSE = {
    "query_id": "q-123",
    "team_recommendations": [],
    "public_recommendations": [
        {
            "id": "m-1",
            "title": "Pin httpx below 1.0 with respx 0.21",
            "text": "respx 0.21 breaks with httpx 1.0 betas. Pin httpx<1 until respx ships support.",
            "type": "instruction",
            "status": "active",
            "score": 0.83,
        },
        {
            "id": "m-skill",
            "title": "pytest helper skill",
            "text": "A skill bundle",
            "type": "note",
            "score": 0.5,
            "has_skill": True,
            "skill_meta": {"name": "pytest-helper", "description": "Runs and triages pytest suites."},
        },
    ],
    "public_warnings": [
        {
            "id": "w-1",
            "title": "Do NOT patch httpx.Client.send",
            "text": "Patching send skips transport hooks and hides timeout bugs.",
            "confidence": 0.72,
        }
    ],
    "public_failed_approaches": [{"id": "f-1", "title": "Monkeypatching sockets", "reason": "Flaky on Windows."}],
}

WRITE_RESPONSE = {
    "memory_id": "new-1",
    "action_performed": "created",
    "query_id_linked": "q-123",
}


@pytest.fixture(autouse=True)
def operator_environment(monkeypatch, tmp_path: Path):
    """Put a different key in the environment and in ~/.bhived so tests prove neither is read."""
    # A key in the server's environment or home directory must never be used.
    monkeypatch.setenv("BHIVED_API_KEY", SERVER_KEY)
    monkeypatch.setenv("BHIVED_API_URL", "https://operator-proxy.example")
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".bhived").mkdir()
    (tmp_path / ".bhived" / "config.json").write_text(json.dumps({"apiKey": SERVER_KEY}), encoding="utf-8")


def _search(**values) -> BhivedSearchComponent:
    """Build a search component with the test key and a query, then apply the overrides."""
    component = BhivedSearchComponent()
    component.set(**{"api_key": API_KEY, "query": "respx httpx 1.0 TypeError", **values})
    return component


def _write(**values) -> BhivedWriteComponent:
    """Build a write component with the test key and a valid instruction, then apply the overrides."""
    component = BhivedWriteComponent()
    component.set(
        **{
            "api_key": API_KEY,
            "lesson_type": "instruction",
            "text": "Pin httpx<1 with respx 0.21.",
            "title": "respx 0.21 needs httpx<1",
            **values,
        }
    )
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [BhivedSearchComponent, BhivedWriteComponent])
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    """No input name may collide with an attribute of the Component base class."""
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [BhivedSearchComponent, BhivedWriteComponent])
def test_metadata(component_class: type[Component]) -> None:
    """Both components use the bhived icon, link the docs page and require an API key."""
    component = component_class()
    assert component.icon == "Bhived"
    assert component.documentation == DOCUMENTATION_URL
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is True


@pytest.mark.unit
def test_write_description_warns_about_public_lessons() -> None:
    """The write description warns that lessons are public and must not contain secrets."""
    assert "the lesson is public" in BhivedWriteComponent.description
    assert "never include secrets" in BhivedWriteComponent.description


@pytest.mark.unit
class TestBhivedSearch:
    """Tests for the bhived Search component."""

    @respx.mock
    async def test_search_returns_lessons_warnings_and_failed_approaches(self) -> None:
        """A search sends the key and returns lessons, warnings and failed approaches."""
        route = respx.post(f"{API_URL}/v2/query").mock(return_value=httpx.Response(200, json=QUERY_RESPONSE))

        rows = await _search(context="python 3.12").search()

        request = route.calls.last.request
        assert request.headers["X-API-Key"] == API_KEY
        assert request.headers["User-Agent"].endswith(" langflow")
        assert json.loads(request.content) == {
            "query": "respx httpx 1.0 TypeError",
            "context": "python 3.12",
            "top_k": 5,
            "include_episodes": True,
            "include_warnings": True,
            "include_disputed": True,
        }
        assert [(row.data["kind"], row.data["id"]) for row in rows] == [
            ("lesson", "m-1"),
            ("warning", "w-1"),
            ("failed_approach", "f-1"),
        ]
        assert rows[0].text == QUERY_RESPONSE["public_recommendations"][0]["text"]
        assert rows[0].data["tier"] == "public"
        assert rows[1].data["score"] == 0.72
        assert rows[2].text == "Flaky on Windows."
        assert {row.data["query_id"] for row in rows} == {"q-123"}

    @respx.mock
    async def test_scope_and_max_results_are_sent(self) -> None:
        """A non-default scope and the result limit are sent in the request body."""
        route = respx.post(f"{API_URL}/v2/query").mock(return_value=httpx.Response(200, json=QUERY_RESPONSE))

        await _search(scope="team_only", max_results=500).search()

        body = json.loads(route.calls.last.request.content)
        assert body["scope"] == "team_only"
        assert body["top_k"] == 100

    @respx.mock
    async def test_default_scope_is_left_to_the_server(self) -> None:
        """The default scope is omitted so the server applies its own default."""
        route = respx.post(f"{API_URL}/v2/query").mock(return_value=httpx.Response(200, json=QUERY_RESPONSE))

        await _search(scope="team_plus_global").search()

        assert "scope" not in json.loads(route.calls.last.request.content)

    async def test_empty_query_makes_no_request(self) -> None:
        """A blank query returns an error without calling the API."""
        with respx.mock(assert_all_called=False) as router:
            rows = await _search(query="   ").search()

        assert not router.calls
        assert rows[0].data["error"] == "Enter a query."

    async def test_missing_key_never_falls_back_to_the_server_key(self) -> None:
        """Without a key the component errors instead of using a key from the server."""
        with respx.mock(assert_all_called=False) as router:
            rows = await _search(api_key="").search()

        assert not router.calls
        assert rows[0].data["error"] == "Enter a bhived API key."

    @respx.mock
    async def test_rejected_key_is_returned_as_an_error(self) -> None:
        """A 403 response becomes an error row that does not contain the key."""
        respx.post(f"{API_URL}/v2/query").mock(return_value=httpx.Response(403, json={"detail": "invalid_api_key"}))

        rows = await _search().search()

        assert "bhived API error (403)" in rows[0].data["error"]
        assert API_KEY not in rows[0].data["error"]

    @respx.mock
    async def test_echoed_key_is_masked(self) -> None:
        """A key echoed back in an error message is masked before it is shown."""
        respx.post(f"{API_URL}/v2/query").mock(
            return_value=httpx.Response(400, json={"detail": f"bad request for {API_KEY}"})
        )

        rows = await _search().search()

        assert API_KEY not in rows[0].data["error"]
        assert "***" in rows[0].data["error"]

    @respx.mock
    async def test_dataframe_output_has_one_row_per_result(self) -> None:
        """The DataFrame output has one row per lesson, warning and failed approach."""
        respx.post(f"{API_URL}/v2/query").mock(return_value=httpx.Response(200, json=QUERY_RESPONSE))

        frame = await _search().search_lessons()

        assert list(frame["kind"]) == ["lesson", "warning", "failed_approach"]
        assert list(frame["title"]) == [
            "Pin httpx below 1.0 with respx 0.21",
            "Do NOT patch httpx.Client.send",
            "Monkeypatching sockets",
        ]


@pytest.mark.unit
class TestBhivedWrite:
    """Tests for the bhived Write Lesson component."""

    @pytest.mark.parametrize("lesson_type", ["instruction", "mistake", "update"])
    @respx.mock
    async def test_write_links_the_query_and_reports_the_lesson(self, lesson_type: str) -> None:
        """Each lesson type is written with the query link, and the saved lesson is reported."""
        route = respx.post(f"{API_URL}/v1/memories").mock(return_value=httpx.Response(200, json=WRITE_RESPONSE))

        result = await _write(lesson_type=lesson_type, query_id="q-123").write_lesson()

        request = route.calls.last.request
        assert request.headers["X-API-Key"] == API_KEY
        assert request.headers["Idempotency-Key"]
        assert json.loads(request.content) == {
            "text": "Pin httpx<1 with respx 0.21.",
            "title": "respx 0.21 needs httpx<1",
            "type": lesson_type,
            "action": "new",
            "query_id": "q-123",
        }
        assert result.data == {
            "text": f"Saved {lesson_type} new-1 (created).",
            "saved": True,
            "lesson_type": lesson_type,
            "bhived_id": "new-1",
            "action": "created",
            "query_id_linked": "q-123",
        }

    @respx.mock
    async def test_write_without_query_id_sends_no_link(self) -> None:
        """A blank query ID is not sent, so the lesson is written without a link."""
        route = respx.post(f"{API_URL}/v1/memories").mock(
            return_value=httpx.Response(200, json={**WRITE_RESPONSE, "query_id_linked": None})
        )

        await _write(query_id="  ").write_lesson()

        assert "query_id" not in json.loads(route.calls.last.request.content)

    @respx.mock
    async def test_near_duplicate_is_reported_as_not_saved(self) -> None:
        """A 409 duplicate response is reported as not saved, with the existing lesson's ID."""
        respx.post(f"{API_URL}/v1/memories").mock(
            return_value=httpx.Response(
                409,
                json={"detail": {"error": "duplicate_memory", "duplicate_of": "m-old", "jaccard_similarity": 0.91}},
            )
        )

        result = await _write(lesson_type="mistake").write_lesson()

        assert result.data == {
            "text": "Not saved: bhived already has a near-identical lesson.",
            "saved": False,
            "lesson_type": "mistake",
            "duplicate_of": "m-old",
            "similarity": 0.91,
        }

    @respx.mock
    async def test_rejected_write_is_returned_as_an_error(self) -> None:
        """A rejected write becomes an error result."""
        respx.post(f"{API_URL}/v1/memories").mock(
            return_value=httpx.Response(422, json={"detail": "text is empty after cleanup"})
        )

        result = await _write().write_lesson()

        assert "bhived API error (422)" in result.data["error"]

    @pytest.mark.parametrize(
        ("values", "error"),
        [
            ({"lesson_type": "note"}, "Lesson type must be one of: instruction, mistake, update."),
            ({"text": "  "}, "Enter the lesson text and a title."),
            ({"title": "x" * 101}, "The title must be at most 100 characters."),
            ({"api_key": ""}, "Enter a bhived API key."),
        ],
    )
    async def test_invalid_input_makes_no_request(self, values: dict, error: str) -> None:
        """Invalid input returns an error without calling the API."""
        with respx.mock(assert_all_called=False) as router:
            result = await _write(**values).write_lesson()

        assert not router.calls
        assert result.data["error"] == error
