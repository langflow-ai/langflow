"""Unit tests for the WebRouter components with ``web_router.WebRouter`` replaced by a fake.

The fake records how the router was built and called and returns real
``web_router`` response models, so the tests exercise the components' option
passing, output shape and error handling without any network call.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from lfx.custom.custom_component.component import Component

web_router = pytest.importorskip("web_router")

from lfx_bundles.webrouter.webrouter_extract import MAX_URLS, WebRouterExtractComponent  # noqa: E402
from lfx_bundles.webrouter.webrouter_search import MAX_RESULTS_LIMIT, WebRouterSearchComponent  # noqa: E402
from web_router import (  # noqa: E402
    ExtractedDocument,
    ExtractFailure,
    ExtractResponse,
    SearchResponse,
    SearchResult,
)

if TYPE_CHECKING:
    from typing_extensions import Self

# Placeholder credential for the fake router (not a real key).
API_KEY = "test-webrouter-provider-key-placeholder"  # pragma: allowlist secret

SEARCH_RESPONSE = SearchResponse(
    provider="nimble",
    query="langflow agents",
    results=[
        SearchResult(
            url="https://www.langflow.org/",
            title="Langflow",
            description="Langflow is a low-code tool for building AI agents.",
        ),
        SearchResult(url="https://example.com/", title="Only content", description="", content="Page text."),
    ],
)
EXTRACT_RESPONSE = ExtractResponse(
    provider="tavily",
    documents=[ExtractedDocument(url="https://www.langflow.org/", title="Langflow", content="# Langflow")],
    failures=[ExtractFailure(url="https://example.com/missing", error="404 Not Found")],
)


class FakeRouter:
    """Stands in for ``web_router.WebRouter``; records each instance in ``instances``."""

    instances: list[FakeRouter] = []
    raises: Exception | None = None

    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs = kwargs
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.closed = False
        FakeRouter.instances.append(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        self.closed = True

    def _call(self, method: str, response: Any, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((method, args, kwargs))
        if FakeRouter.raises is not None:
            raise FakeRouter.raises
        return response

    def search(self, *args: Any, **kwargs: Any) -> SearchResponse:
        return self._call("search", SEARCH_RESPONSE, *args, **kwargs)

    def extract(self, *args: Any, **kwargs: Any) -> ExtractResponse:
        return self._call("extract", EXTRACT_RESPONSE, *args, **kwargs)


@pytest.fixture(autouse=True)
def fake_router():
    FakeRouter.instances = []
    FakeRouter.raises = None
    with patch.object(web_router, "WebRouter", FakeRouter):
        yield FakeRouter


def _search(**values) -> WebRouterSearchComponent:
    component = WebRouterSearchComponent()
    component.set(**{"query": "langflow agents", **values})
    return component


def _extract(**values) -> WebRouterExtractComponent:
    component = WebRouterExtractComponent()
    component.set(**{"urls": "https://www.langflow.org/", **values})
    return component


def _only_call(fake: type[FakeRouter]) -> tuple[str, tuple[Any, ...], dict[str, Any]]:
    (router,) = fake.instances
    (call,) = router.calls
    assert router.closed
    return call


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [WebRouterSearchComponent, WebRouterExtractComponent])
def test_input_names_do_not_shadow_component_attributes(component_class: type[Component]) -> None:
    shadowed = [inp.name for inp in component_class.inputs if hasattr(Component, inp.name)]
    assert not shadowed, f"{component_class.__name__} inputs shadow Component attributes: {shadowed}"


@pytest.mark.unit
@pytest.mark.parametrize("component_class", [WebRouterSearchComponent, WebRouterExtractComponent])
def test_metadata(component_class: type[Component]) -> None:
    component = component_class()
    assert component.icon == "WebRouter"
    assert "docs.webrouter.net" in component.documentation
    api_key = next(inp for inp in component_class.inputs if inp.name == "api_key")
    assert api_key.required is False


@pytest.mark.unit
class TestWebRouterSearch:
    def test_keyless_search_lets_webrouter_pick(self, fake_router) -> None:
        data = _search().search()

        method, args, kwargs = _only_call(fake_router)
        assert (method, args) == ("search", ("langflow agents",))
        assert kwargs == {"provider": None, "max_results": 5, "include_domains": None, "timeout": 30.0}
        assert fake_router.instances[0].init_kwargs == {"provider_config": None}
        assert [d.data["url"] for d in data] == ["https://www.langflow.org/", "https://example.com/"]
        assert data[0].data["provider"] == "nimble"
        assert data[0].text == "Langflow is a low-code tool for building AI agents."
        assert data[1].text == "Page text."

    def test_dataframe_has_one_row_per_result(self) -> None:
        frame = _search().search_dataframe()

        assert list(frame["title"]) == ["Langflow", "Only content"]
        assert {"title", "url", "snippet", "provider"} <= set(frame.columns)

    @pytest.mark.parametrize(("value", "expected"), [(0, 1), (-3, 1), (7, 7), (500, MAX_RESULTS_LIMIT)])
    def test_max_results_is_clamped(self, fake_router, value: int, expected: int) -> None:
        _search(max_results=value).search()

        assert _only_call(fake_router)[2]["max_results"] == expected

    def test_include_domains_and_timeout_are_passed(self, fake_router) -> None:
        _search(include_domains="docs.python.org, peps.python.org\nwiki.python.org", timeout=12).search()

        kwargs = _only_call(fake_router)[2]
        assert kwargs["include_domains"] == ["docs.python.org", "peps.python.org", "wiki.python.org"]
        assert kwargs["timeout"] == 12.0

    def test_named_provider_with_key_goes_through_provider_config(self, fake_router) -> None:
        _search(provider=" Tavily ", api_key=API_KEY).search()

        assert _only_call(fake_router)[2]["provider"] == "tavily"
        assert fake_router.instances[0].init_kwargs == {"provider_config": {"tavily": {"api_key": API_KEY}}}

    def test_named_provider_without_key_uses_environment(self, fake_router) -> None:
        _search(provider="exa").search()

        assert _only_call(fake_router)[2]["provider"] == "exa"
        assert fake_router.instances[0].init_kwargs == {"provider_config": None}

    def test_key_without_provider_is_refused_before_any_call(self, fake_router) -> None:
        data = _search(api_key=API_KEY).search()

        assert fake_router.instances == []
        assert "Set Provider" in data[0].data["error"]
        assert API_KEY not in data[0].text

    def test_empty_query_makes_no_call(self, fake_router) -> None:
        data = _search(query="   ").search()

        assert fake_router.instances == []
        assert data[0].data["error"] == "Enter a search query."

    def test_webrouter_error_is_returned_with_the_key_redacted(self, fake_router) -> None:
        fake_router.raises = web_router.WebRouterError(f"provider rejected key {API_KEY}")

        data = _search(provider="tavily", api_key=API_KEY).search()

        assert data[0].data["error"].startswith("WebRouter call failed:")
        assert API_KEY not in data[0].data["error"]
        assert "***" in data[0].data["error"]
        assert fake_router.instances[0].closed

    def test_missing_package_explains_how_to_install(self, fake_router) -> None:
        with patch.dict(sys.modules, {"web_router": None}):
            data = _search().search()

        assert "lfx-bundles[webrouter]" in data[0].data["error"]
        assert fake_router.instances == []


@pytest.mark.unit
class TestWebRouterExtract:
    def test_extract_returns_documents_and_failures(self, fake_router) -> None:
        data = _extract(urls="https://www.langflow.org/\nhttps://example.com/missing").extract()

        method, args, kwargs = _only_call(fake_router)
        assert (method, args) == ("extract", (["https://www.langflow.org/", "https://example.com/missing"],))
        assert kwargs == {"provider": None, "format": "markdown", "timeout": 30.0}
        assert data[0].text == "# Langflow"
        assert data[0].data["provider"] == "tavily"
        assert data[1].data["url"] == "https://example.com/missing"
        assert data[1].data["error"] == "404 Not Found"
        assert "content" not in data[1].data

    def test_dataframe_has_one_row_per_url(self) -> None:
        frame = _extract().extract_dataframe()

        assert list(frame["url"]) == ["https://www.langflow.org/", "https://example.com/missing"]

    def test_named_provider_with_key_goes_through_provider_config(self, fake_router) -> None:
        _extract(provider="firecrawl", api_key=API_KEY, timeout=45).extract()

        kwargs = _only_call(fake_router)[2]
        assert kwargs["provider"] == "firecrawl"
        assert kwargs["timeout"] == 45.0
        assert fake_router.instances[0].init_kwargs == {"provider_config": {"firecrawl": {"api_key": API_KEY}}}

    @pytest.mark.parametrize(
        "urls",
        ["", "   ", "file:///etc/passwd", "ftp://example.com/file", "example.com", "http://[::1"],
    )
    def test_invalid_input_makes_no_call(self, fake_router, urls: str) -> None:
        data = _extract(urls=urls).extract()

        assert fake_router.instances == []
        assert "error" in data[0].data

    def test_too_many_urls_makes_no_call(self, fake_router) -> None:
        urls = ",".join(f"https://example.com/{i}" for i in range(MAX_URLS + 1))

        data = _extract(urls=urls).extract()

        assert fake_router.instances == []
        assert f"at most {MAX_URLS}" in data[0].data["error"]

    def test_webrouter_error_is_returned(self, fake_router) -> None:
        fake_router.raises = web_router.WebRouterError("every provider failed")

        data = _extract().extract()

        assert data[0].data["error"] == "WebRouter call failed: every provider failed"
