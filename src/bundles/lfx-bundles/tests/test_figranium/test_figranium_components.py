"""Unit tests for the Figranium components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.get`` / ``httpx.Client.post``, which is
where Langflow's SSRF-protected helpers hand off to httpx, so the tests exercise
the real URL validation, header, body, and error handling of the client.
"""

from __future__ import annotations

import re
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.figranium.base import DEFAULT_TIMEOUT_SECONDS, FigraniumAPIClient, extract_items, normalize_base_url
from lfx_bundles.figranium.execute_task import FigraniumExecuteTaskComponent
from lfx_bundles.figranium.list_executions import FigraniumListExecutionsComponent
from lfx_bundles.figranium.list_tasks import FigraniumListTasksComponent

# A local install is the common self-hosted shape and is loopback-exempt from SSRF checks.
BASE_URL = "http://localhost:11345"
# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-figranium-api-key-placeholder"  # pragma: allowlist secret
METADATA_URL = "http://169.254.169.254/latest/meta-data"


def _response(status_code: int = 200, *, json_body: Any = None, text: str | None = None, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", BASE_URL)
    if text is not None:
        return httpx.Response(status_code, text=text, request=request, **kwargs)
    return httpx.Response(status_code, json=json_body, request=request, **kwargs)


def _execute_component(**overrides) -> FigraniumExecuteTaskComponent:
    values = {
        "base_url": BASE_URL,
        "api_key": API_KEY,
        "task_id": "task_123",
        "task_variables": '{"query": "Langflow"}',
    }
    values.update(overrides)
    component = FigraniumExecuteTaskComponent()
    component.set(**values)
    return component


@pytest.mark.unit
@pytest.mark.parametrize(
    "component_class",
    [FigraniumExecuteTaskComponent, FigraniumListTasksComponent, FigraniumListExecutionsComponent],
)
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    """An input named like a ``Component`` attribute is silently shadowed.

    ``self.<name>`` then resolves to the base-class member instead of the user's
    value -- ``variables`` is one such name (``CustomComponent.variables``).
    """
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
class TestFigraniumExecuteTask:
    def test_metadata(self) -> None:
        component = FigraniumExecuteTaskComponent()
        assert component.display_name == "Execute Figranium Task"
        assert component.icon == "Figranium"
        assert "docs.figranium.dev" in component.documentation

    def test_posts_variables_with_api_key_header(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={"status": "ok", "data": [1]})) as mock_post:
            result = _execute_component(timeout=45).execute_task()

        assert result.data == {"status": "ok", "data": [1]}
        mock_post.assert_called_once()
        kwargs = mock_post.call_args.kwargs
        assert kwargs["url"] == f"{BASE_URL}/api/tasks/task_123/api"
        assert kwargs["headers"]["x-api-key"] == API_KEY
        assert kwargs["json"] == {"variables": {"query": "Langflow"}}
        assert kwargs["timeout"] == 45.0

    def test_default_timeout_when_unset(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={})) as mock_post:
            _execute_component(timeout=None).execute_task()

        assert mock_post.call_args.kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS

    def test_task_id_is_url_encoded(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={})) as mock_post:
            _execute_component(task_id=" my task/../x ").execute_task()

        assert mock_post.call_args.kwargs["url"] == f"{BASE_URL}/api/tasks/my%20task%2F..%2Fx/api"

    def test_trailing_slash_on_base_url_is_dropped(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={})) as mock_post:
            _execute_component(base_url=f"{BASE_URL}/").execute_task()

        assert mock_post.call_args.kwargs["url"] == f"{BASE_URL}/api/tasks/task_123/api"

    def test_non_object_result_is_boxed(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body=["a", "b"])):
            result = _execute_component().execute_task()

        assert result.data == {"result": ["a", "b"]}

    def test_empty_body_yields_empty_data(self) -> None:
        with patch("httpx.Client.post", return_value=_response(text="")):
            result = _execute_component().execute_task()

        assert result.data == {}

    def test_dict_variables_are_sent_as_is(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={})) as mock_post:
            _execute_component(task_variables={"count": 2}).execute_task()

        assert mock_post.call_args.kwargs["json"] == {"variables": {"count": 2}}

    def test_blank_variables_send_empty_object(self) -> None:
        with patch("httpx.Client.post", return_value=_response(json_body={})) as mock_post:
            _execute_component(task_variables="").execute_task()

        assert mock_post.call_args.kwargs["json"] == {"variables": {}}

    @pytest.mark.parametrize("value", ["", None, "{}", {}])
    def test_parse_variables_treats_blank_as_empty_object(self, value) -> None:
        assert FigraniumExecuteTaskComponent._parse_variables(value) == {}

    def test_invalid_json_variables_raise_before_request(self) -> None:
        with patch("httpx.Client.post") as mock_post, pytest.raises(ValueError, match="valid JSON"):
            _execute_component(task_variables="{not json").execute_task()

        mock_post.assert_not_called()

    def test_non_object_json_variables_raise_before_request(self) -> None:
        with patch("httpx.Client.post") as mock_post, pytest.raises(TypeError, match="JSON object"):
            _execute_component(task_variables="[1, 2]").execute_task()

        mock_post.assert_not_called()

    def test_blank_task_id_raises_before_request(self) -> None:
        with patch("httpx.Client.post") as mock_post, pytest.raises(ValueError, match="task ID is required"):
            _execute_component(task_id="  ").execute_task()

        mock_post.assert_not_called()

    def test_zero_timeout_is_rejected(self) -> None:
        with patch("httpx.Client.post") as mock_post, pytest.raises(ValueError, match="positive number"):
            _execute_component(timeout=0).execute_task()

        mock_post.assert_not_called()

    def test_timeout_maps_to_actionable_error(self) -> None:
        with (
            patch("httpx.Client.post", side_effect=httpx.ReadTimeout("slow")),
            pytest.raises(ValueError, match="did not respond within 45 seconds"),
        ):
            _execute_component(timeout=45).execute_task()

    def test_connection_error_names_the_instance(self) -> None:
        with (
            patch("httpx.Client.post", side_effect=httpx.ConnectError("refused")),
            pytest.raises(ValueError, match=f"Could not reach Figranium at {BASE_URL}"),
        ):
            _execute_component().execute_task()

    def test_http_error_surfaces_figranium_message(self) -> None:
        body = {"error": "TASK_NOT_FOUND", "message": "Task task_123 does not exist"}
        with (
            patch("httpx.Client.post", return_value=_response(404, json_body=body)),
            pytest.raises(ValueError, match="HTTP 404: Task task_123 does not exist"),
        ):
            _execute_component().execute_task()

    def test_http_error_detail_is_bounded(self) -> None:
        with (
            patch("httpx.Client.post", return_value=_response(500, text="<html>" + "x" * 5000)),
            pytest.raises(ValueError, match="HTTP 500") as excinfo,
        ):
            _execute_component().execute_task()

        assert len(str(excinfo.value)) < 700

    def test_redirect_response_gives_a_hint(self) -> None:
        redirect = _response(301, text="", headers={"location": "https://figranium.example.com/"})
        with (
            patch("httpx.Client.post", return_value=redirect),
            pytest.raises(ValueError, match=re.escape("redirected to https://figranium.example.com/")),
        ):
            _execute_component().execute_task()

    def test_non_json_success_body_raises(self) -> None:
        with (
            patch("httpx.Client.post", return_value=_response(text="<html>login</html>")),
            pytest.raises(ValueError, match="non-JSON response"),
        ):
            _execute_component().execute_task()

    def test_ssrf_guard_blocks_metadata_url_before_request(self, monkeypatch) -> None:
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_VALIDATION_ENABLED", "true")
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)

        with patch("httpx.Client.post") as mock_post, pytest.raises(ValueError, match="SSRF Protection"):
            _execute_component(base_url=METADATA_URL).execute_task()

        mock_post.assert_not_called()


@pytest.mark.unit
class TestFigraniumListComponents:
    @pytest.mark.parametrize(
        "payload",
        [
            {"tasks": [{"id": "t1", "name": "One"}, "junk", {"id": "t2", "name": "Two"}]},
            [{"id": "t1", "name": "One"}, "junk", {"id": "t2", "name": "Two"}],
        ],
        ids=["wrapped", "bare-list"],
    )
    def test_list_tasks_reads_wrapped_or_bare_lists(self, payload) -> None:
        component = FigraniumListTasksComponent()
        component.set(base_url=BASE_URL, api_key=API_KEY)

        with patch("httpx.Client.get", return_value=_response(json_body=payload)) as mock_get:
            result = component.list_tasks()

        assert [item.data for item in result] == [{"id": "t1", "name": "One"}, {"id": "t2", "name": "Two"}]
        kwargs = mock_get.call_args.kwargs
        assert kwargs["url"] == f"{BASE_URL}/api/tasks/list"
        assert kwargs["headers"]["x-api-key"] == API_KEY
        assert kwargs["timeout"] == DEFAULT_TIMEOUT_SECONDS

    def test_list_executions_reads_wrapped_list(self) -> None:
        component = FigraniumListExecutionsComponent()
        component.set(base_url=BASE_URL, api_key=API_KEY)
        payload = {"executions": [{"id": "e1", "status": "completed", "taskId": "t1"}]}

        with patch("httpx.Client.get", return_value=_response(json_body=payload)) as mock_get:
            result = component.list_executions()

        assert [item.data for item in result] == payload["executions"]
        assert mock_get.call_args.kwargs["url"] == f"{BASE_URL}/api/executions/list"

    @pytest.mark.parametrize("payload", [{}, {"tasks": None}, {"tasks": "nope"}, "text", None])
    def test_list_tasks_tolerates_unexpected_shapes(self, payload) -> None:
        component = FigraniumListTasksComponent()
        component.set(base_url=BASE_URL, api_key=API_KEY)

        with patch("httpx.Client.get", return_value=_response(json_body=payload)):
            assert component.list_tasks() == []

    def test_metadata(self) -> None:
        for component_class in (FigraniumListTasksComponent, FigraniumListExecutionsComponent):
            component = component_class()
            assert component.icon == "Figranium"
            assert {inp.name for inp in component.inputs} == {"base_url", "api_key"}


@pytest.mark.unit
class TestFigraniumAPIClient:
    @pytest.mark.parametrize(
        ("base_url", "api_key", "match"),
        [
            ("", API_KEY, "URL is required"),
            ("   ", API_KEY, "URL is required"),
            ("figranium.example.com", API_KEY, "absolute http"),
            ("ftp://figranium.example.com", API_KEY, "absolute http"),
            (BASE_URL, "", "API key is required"),
            (BASE_URL, None, "API key is required"),
        ],
    )
    def test_configuration_is_validated_before_any_request(self, base_url, api_key, match) -> None:
        with patch("httpx.Client.get") as mock_get, pytest.raises(ValueError, match=match):
            FigraniumAPIClient(base_url, api_key).get("/api/tasks/list")

        mock_get.assert_not_called()

    def test_secret_str_api_key_is_unwrapped(self) -> None:
        from pydantic import SecretStr

        client = FigraniumAPIClient(BASE_URL, SecretStr(API_KEY))

        assert client.api_key == API_KEY

    def test_normalize_base_url_strips_whitespace_and_slashes(self) -> None:
        assert normalize_base_url("  https://figranium.example.com//  ") == "https://figranium.example.com"

    def test_extract_items_keeps_only_dict_entries(self) -> None:
        assert extract_items({"tasks": [{"a": 1}, 2, None]}, "tasks") == [{"a": 1}]
        assert extract_items([{"a": 1}, "x"], "tasks") == [{"a": 1}]
        assert extract_items({"other": [{"a": 1}]}, "tasks") == []
        assert extract_items("nope", "tasks") == []
