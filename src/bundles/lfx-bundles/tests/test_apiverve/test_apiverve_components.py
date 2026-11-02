"""Unit tests for the APIVerve components with mocked HTTP calls.

Requests are intercepted at ``httpx.Client.get`` / ``httpx.Client.post``, so the tests
exercise the real URL building, header, parameter placement and error handling.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx
import pytest
from lfx.custom.custom_component.component import Component
from lfx_bundles.apiverve import base
from lfx_bundles.apiverve.find_apis import ApiverveFindApisComponent
from lfx_bundles.apiverve.run_api import ApiverveRunApiComponent

# Placeholder credential for the mocked API (not a real key).
API_KEY = "test-apiverve-api-key-placeholder"  # pragma: allowlist secret

CATALOG = {
    "apis": {
        "emailvalidator": {
            "title": "Email Validator",
            "category": "Validation",
            "description": "Validate an email address",
            "method": "GET",
            "path": "/v1/emailvalidator",
            "params": [{"name": "email", "type": "string", "required": True, "in": "query"}],
        },
        "vatrates": {
            "title": "VAT Rates",
            "category": "Finance",
            "description": "VAT rates by country",
            "method": "GET",
            "path": "/v1/vatrates",
            "params": [],
        },
        "gravatarlookup": {
            "title": "Gravatar Lookup",
            "category": "Social",
            "description": "Look up a Gravatar profile",
            "method": "GET",
            "path": "/v1/gravatarlookup",
            "params": [],
        },
        "texttopdf": {
            "title": "Text to PDF",
            "category": "Documents",
            "description": "Make a PDF",
            "method": "POST",
            "path": "/v1/texttopdf",
            "params": [
                {"name": "text", "type": "string", "required": True, "in": "body"},
                {"name": "title", "type": "string", "in": "query"},
            ],
        },
    }
}


def _response(status_code: int = 200, json_body: Any = None) -> httpx.Response:
    return httpx.Response(status_code, json=json_body, request=httpx.Request("GET", base.API_BASE))


def _fake_get(api_body: Any = None, status_code: int = 200):
    def fake_get(self, url, *args, **kwargs):  # noqa: ARG001
        if str(url).startswith(base.CATALOG_URL):
            return _response(json_body=CATALOG)
        return _response(status_code, api_body)

    return fake_get


@pytest.fixture(autouse=True)
def _reset_catalog_cache():
    base._catalog = None
    base._catalog_at = 0.0
    yield
    base._catalog = None


def _run_component(**overrides) -> ApiverveRunApiComponent:
    values = {"api_key": API_KEY, "api_id": "emailvalidator", "api_parameters": '{"email": "jane@example.com"}'}
    values.update(overrides)
    component = ApiverveRunApiComponent()
    component.set(**values)
    return component


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [ApiverveRunApiComponent, ApiverveFindApisComponent])
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
class TestApiverveRunApi:
    def test_metadata(self) -> None:
        component = ApiverveRunApiComponent()
        assert component.display_name == "APIVerve Run API"
        assert component.icon == "APIVerve"
        assert "docs.apiverve.com" in component.documentation

    def test_get_sends_key_header_to_fixed_host(self) -> None:
        with patch(
            "httpx.Client.get", autospec=True, side_effect=_fake_get({"status": "ok", "data": {"isValid": True}})
        ) as mock_get:
            result = _run_component().run_api()

        assert result.data == {"isValid": True}
        api_call = mock_get.call_args_list[-1]
        assert api_call.args[1] == "https://api.apiverve.com/v1/emailvalidator"
        assert api_call.kwargs["params"] == {"email": "jane@example.com"}
        assert api_call.kwargs["headers"]["x-api-key"] == API_KEY

    def test_post_places_query_and_body_per_catalog(self) -> None:
        with (
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get()),
            patch(
                "httpx.Client.post",
                autospec=True,
                return_value=_response(json_body={"status": "ok", "data": {"pdf": "x"}}),
            ) as mock_post,
        ):
            result = _run_component(api_id="texttopdf", api_parameters='{"text": "hi", "title": "T"}').run_api()

        assert result.data == {"pdf": "x"}
        kwargs = mock_post.call_args.kwargs
        assert mock_post.call_args.args[1] == "https://api.apiverve.com/v1/texttopdf"
        assert kwargs["params"] == {"title": "T"}
        assert kwargs["json"] == {"text": "hi"}

    def test_redirects_are_not_followed(self) -> None:
        seen: list[Any] = []
        real_init = httpx.Client.__init__

        def spy_init(self, *args, **kwargs):
            seen.append(kwargs.get("follow_redirects"))
            real_init(self, *args, **kwargs)

        with (
            patch.object(httpx.Client, "__init__", spy_init),
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get({"status": "ok", "data": {}})),
        ):
            _run_component().run_api()

        assert seen
        assert all(value is False for value in seen)

    def test_missing_required_parameter(self) -> None:
        with (
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get()),
            pytest.raises(ValueError, match="emailvalidator needs: email"),
        ):
            _run_component(api_parameters="{}").run_api()

    def test_unknown_api(self) -> None:
        with (
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get()),
            pytest.raises(ValueError, match='Unknown APIVerve API "nope"'),
        ):
            _run_component(api_id="nope").run_api()

    def test_invalid_json_parameters(self) -> None:
        with pytest.raises(ValueError, match="Parameters must be valid JSON"):
            _run_component(api_parameters="{not json").run_api()

    def test_non_object_parameters(self) -> None:
        with pytest.raises(TypeError, match="Parameters must be a JSON object"):
            _run_component(api_parameters="[1, 2]").run_api()

    def test_bad_key_message(self) -> None:
        with (
            patch(
                "httpx.Client.get",
                autospec=True,
                side_effect=_fake_get({"status": "error", "error": "Unauthorized"}, 401),
            ),
            pytest.raises(ValueError, match="APIVerve rejected the API key"),
        ):
            _run_component().run_api()

    def test_errors_never_echo_the_key(self) -> None:
        body = {"status": "error", "error": f"bad key {API_KEY}"}
        with (
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get(body, 400)),
            pytest.raises(ValueError, match=r"APIVerve returned HTTP 400") as excinfo,
        ):
            _run_component().run_api()

        assert API_KEY not in str(excinfo.value)
        assert "[redacted]" in str(excinfo.value)

    def test_missing_key(self) -> None:
        with (
            patch("httpx.Client.get", autospec=True, side_effect=_fake_get()),
            pytest.raises(ValueError, match="API key is required"),
        ):
            _run_component(api_key="").run_api()


@pytest.mark.unit
class TestApiverveFindApis:
    def test_word_start_ranking_without_a_key(self) -> None:
        component = ApiverveFindApisComponent()
        component.set(query="vat")
        with patch("httpx.Client.get", autospec=True, side_effect=_fake_get()) as mock_get:
            rows = component.find_apis()

        assert [row.data["api"] for row in rows] == ["vatrates"]
        assert all("x-api-key" not in (c.kwargs.get("headers") or {}) for c in mock_get.call_args_list)

    def test_returns_parameters_for_run_api(self) -> None:
        component = ApiverveFindApisComponent()
        component.set(query="email validator", max_results=1)
        with patch("httpx.Client.get", autospec=True, side_effect=_fake_get()):
            rows = component.find_apis()

        assert rows[0].data["api"] == "emailvalidator"
        assert rows[0].data["parameters"][0]["name"] == "email"
        assert rows[0].data["parameters"][0]["required"] is True

    def test_dataframe_output(self) -> None:
        component = ApiverveFindApisComponent()
        component.set(query="pdf")
        with patch("httpx.Client.get", autospec=True, side_effect=_fake_get()):
            frame = component.find_apis_dataframe()

        assert list(frame["api"]) == ["texttopdf"]

    def test_catalog_is_cached(self) -> None:
        with patch("httpx.Client.get", autospec=True, side_effect=_fake_get()) as mock_get:
            base.search("vat")
            base.search("pdf")

        assert sum(str(c.args[1]).startswith(base.CATALOG_URL) for c in mock_get.call_args_list) == 1

    def test_malformed_catalog_is_rejected(self) -> None:
        with (
            patch("httpx.Client.get", autospec=True, return_value=_response(json_body={"apis": []})),
            pytest.raises(ValueError, match="catalog could not be loaded"),
        ):
            base.search("vat")

        assert base._catalog is None

    def test_failed_refresh_serves_stale_catalog_and_backs_off(self) -> None:
        with patch("httpx.Client.get", autospec=True, side_effect=_fake_get()):
            base.search("vat")
        base._catalog_at -= base.CATALOG_TTL_SECONDS + 1

        with patch("httpx.Client.get", autospec=True, side_effect=httpx.ConnectError("down")) as mock_get:
            assert [row["api"] for row in base.search("vat")] == ["vatrates"]
            base.search("pdf")

        assert mock_get.call_count == 1
