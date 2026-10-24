"""Contract tests: real components and Data types, mocked HTTP only."""

import asyncio
import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import lfx_fastaf
import pytest
from lfx.schema.data import Data
from lfx.schema.dataframe import DataFrame
from lfx_fastaf import FastAFScreenshotComponent, FastAFSearchComponent
from lfx_fastaf._base import FastAFError, boolean_option, data_rows, integer_option
from pydantic import SecretStr

STREAM_TARGET = "lfx_fastaf._base.httpx.stream"
STORAGE_TARGET = "lfx_fastaf.components.fastaf.screenshot.get_storage_service"
DUMMY_KEY = "offline-credential"  # pragma: allowlist secret
CONTINUATION = "test-page"
PNG = b"\x89PNG\r\n\x1a\n" + b"offline-image"
CASES = [
    (
        "FastAFScrapeComponent",
        "scrape",
        {"url": "https://example.com", "format": "markdown"},
        {"url": "https://example.com", "formats": "markdown"},
        "Page content",
    ),
    (
        "FastAFSearchComponent",
        "serp",
        {"query": "coffee"},
        {"query": "coffee", "advance_search": False},
        {"organic_results": [{"title": "Result", "snippet": "Text"}]},
    ),
    (
        "FastAFExtractComponent",
        "scrape",
        {"url": "https://example.com", "rules": {"title": "page title"}},
        {"url": "https://example.com", "ai_extract_rules": '{"title":"page title"}'},
        {"title": "Example"},
    ),
    (
        "FastAFScreenshotComponent",
        "screenshot",
        {"url": "https://example.com"},
        {
            "url": "https://example.com",
            "format": "png",
            "quality": 80,
            "fullPage": False,
            "wait_until": "domcontentloaded",
        },
        PNG,
    ),
    (
        "FastAFAmazonComponent",
        "amazon",
        {"query": "coffee"},
        {"resource": "search", "query": "coffee", "domain": "com"},
        {"results": [{"title": "Product"}]},
    ),
    (
        "FastAFMapsComponent",
        "maps",
        {"query": "coffee", "coordinates": "@41.9,12.5,13z"},
        {"query": "coffee", "ll": "@41.9,12.5,13z"},
        {"search_results": [{"title": "Cafe"}]},
    ),
    (
        "FastAFLinkedInComponent",
        "linkedin",
        {"profile_id": "public-profile"},
        {"id": "public-profile", "type": "profile"},
        [{"headline": "Public profile"}],
    ),
    (
        "FastAFYouTubeComponent",
        "youtube",
        {"video_id": "jNQXAC9IVRw"},
        {"resource": "transcript", "v": "jNQXAC9IVRw"},
        {"transcripts": [{"text": "Caption", "start": 0}]},
    ),
    (
        "FastAFNewsComponent",
        "news",
        {"query": "coffee"},
        {"query": "coffee"},
        {"news_results": [{"title": "Headline"}]},
    ),
    (
        "FastAFJobsComponent",
        "jobs",
        {"query": "developer"},
        {"query": "developer"},
        {"jobs_results": [{"title": "Role"}]},
    ),
]


def component(name, **props):
    return getattr(lfx_fastaf, name)(fastaf_api_key=DUMMY_KEY, **props)


@contextmanager
def response_context(response):
    yield response


def mocked_stream(payload, status=200, headers=None):
    headers = {"x-fastaf-credits-used": "5", "x-fastaf-credits-remaining": "95", **(headers or {})}
    if isinstance(payload, bytes):
        response = httpx.Response(status, content=payload, headers={"content-type": "image/png", **headers})
    elif isinstance(payload, str):
        response = httpx.Response(status, text=payload, headers=headers)
    else:
        response = httpx.Response(status, json=payload, headers=headers)
    return MagicMock(side_effect=lambda *_args, **_kwargs: response_context(response))


def storage_mock():
    storage = MagicMock()
    storage.save_file = AsyncMock()
    storage.resolve_component_path.side_effect = lambda path: f"memory://{path}"
    return storage


def invoke(c):
    method = getattr(c, c.outputs[0].method)
    return asyncio.run(method()) if isinstance(c, FastAFScreenshotComponent) else method()


@pytest.mark.parametrize(("name", "endpoint", "props", "expected", "payload"), CASES)
def test_real_component_output_and_request(name, endpoint, props, expected, payload):
    c = component(name, **props)
    stream = mocked_stream(payload)
    storage = storage_mock()
    with patch(STREAM_TARGET, stream), patch(STORAGE_TARGET, return_value=storage):
        output = invoke(c)
    assert isinstance(output, Data if name == "FastAFScreenshotComponent" else DataFrame)
    assert stream.call_count == 1
    assert stream.call_args.args == ("POST", f"https://api.fastaf.co/v1/{endpoint}")
    kwargs = stream.call_args.kwargs
    assert kwargs["json"] == expected
    assert kwargs["headers"]["Authorization"] == f"Bearer {DUMMY_KEY}"
    assert kwargs["verify"] is True
    assert kwargs["follow_redirects"] is False
    assert kwargs["trust_env"] is False
    assert kwargs["timeout"] == 120
    assert DUMMY_KEY not in json.dumps(kwargs["json"])
    assert DUMMY_KEY not in str(output)
    assert c.last_request == {"http_status": 200, "credits_used": 5, "credits_remaining": 95}
    if name == "FastAFScreenshotComponent":
        assert output.data["bytes"] == len(PNG)
        assert output.data["content_type"] == "image/png"
        assert output.data["file_path"].startswith("memory://")
        assert "base64" not in output.data
        storage.save_file.assert_awaited_once()
        namespace, filename, content = storage.save_file.call_args.args
        assert namespace
        assert filename.startswith("fastaf-")
        assert filename.endswith(".png")
        assert content == PNG
    else:
        assert len(output) > 0


@pytest.mark.parametrize("name", lfx_fastaf.__all__)
def test_secret_input_and_unique_tool(name):
    cls = getattr(lfx_fastaf, name)
    key = next(item for item in cls.inputs if item.name == "fastaf_api_key")
    assert key.password
    assert key.required
    assert key.track_in_telemetry is False
    c = cls(fastaf_api_key=DUMMY_KEY)
    tools = asyncio.run(c.to_toolkit())
    assert [tool.name for tool in tools] == [cls.outputs[0].method]
    assert tools[0].name.startswith("fastaf_")


def test_exactly_ten_unique_actions():
    assert len(lfx_fastaf.__all__) == 10
    assert len({getattr(lfx_fastaf, name).outputs[0].method for name in lfx_fastaf.__all__}) == 10


def test_secretstr_wrapped_key_and_tool_invocation():
    c = FastAFSearchComponent(fastaf_api_key=SecretStr(DUMMY_KEY))
    tools = asyncio.run(c.to_toolkit())
    stream = mocked_stream({"organic_results": [{"title": "Expected result"}]})
    with patch(STREAM_TARGET, stream):
        output = asyncio.run(tools[0].ainvoke({"query": "langflow"}))
    assert stream.call_args.kwargs["headers"]["Authorization"] == f"Bearer {DUMMY_KEY}"
    assert stream.call_args.kwargs["json"]["query"] == "langflow"
    assert "Expected result" in str(output)


@pytest.mark.parametrize("status", [301, 400, 401, 402, 403, 429, 500, 502, 503, 504])
def test_http_errors_are_safe_and_never_retry_or_redirect(status):
    c = component("FastAFSearchComponent", query="coffee")
    stream = mocked_stream({"error": f"Authorization: Bearer {DUMMY_KEY}"}, status)
    with patch(STREAM_TARGET, stream):
        result = c.fetch_content()
    assert len(result) == 1
    assert f"HTTP {status}" in result[0].data["error"]
    assert DUMMY_KEY not in str(result)
    assert result[0].data["http_status"] == status
    assert stream.call_count == 1


@pytest.mark.parametrize("error_type", [httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError])
def test_transport_errors_do_not_expose_credentials(error_type):
    c = component("FastAFSearchComponent", query="coffee")
    with patch(STREAM_TARGET, side_effect=error_type(f"Bearer {DUMMY_KEY}")) as stream:
        rows = c.fetch_content()
    assert "could not be reached" in rows[0].data["error"]
    assert DUMMY_KEY not in str(rows)
    stream.assert_called_once()


@pytest.mark.parametrize("key", [None, "", " ", "contains space"])
def test_missing_invalid_key_never_makes_request(key):
    c = FastAFSearchComponent(fastaf_api_key=key, query="coffee")
    with patch(STREAM_TARGET) as stream:
        rows = c.fetch_content()
    stream.assert_not_called()
    assert "API key is required" in rows[0].data["error"]


@pytest.mark.parametrize(
    ("name", "props"),
    [
        ("FastAFScrapeComponent", {"url": "file:///etc/passwd"}),
        ("FastAFScrapeComponent", {"url": "https://user:password@example.com"}),
        ("FastAFScrapeComponent", {"url": "https://example.com", "dynamic": "true", "challenge_mode": "true"}),
        ("FastAFScrapeComponent", {"url": "https://example.com", "wait": "35001"}),
        ("FastAFSearchComponent", {"query": "coffee", "results": "101"}),
        ("FastAFSearchComponent", {"query": "coffee", "page": "-1"}),
        ("FastAFSearchComponent", {"query": ""}),
        ("FastAFExtractComponent", {"url": "https://example.com"}),
        ("FastAFMapsComponent", {}),
        ("FastAFMapsComponent", {"query": "coffee", "location": "Rome", "coordinates": "@41.9,12.5,13z"}),
        ("FastAFMapsComponent", {"query": "coffee", "page": "1"}),
        ("FastAFAmazonComponent", {"resource": "product"}),
        ("FastAFAmazonComponent", {"resource": "search"}),
        ("FastAFAmazonComponent", {"resource": "reviews"}),
        ("FastAFLinkedInComponent", {}),
        ("FastAFYouTubeComponent", {}),
        ("FastAFYouTubeComponent", {"resource": "search"}),
    ],
)
def test_invalid_inputs_never_spend_credits(name, props):
    c = component(name, **props)
    with patch(STREAM_TARGET) as stream:
        rows = c.fetch_content()
    stream.assert_not_called()
    assert "error" in rows[0].data


def test_false_zero_and_all_scrape_options_preserved():
    c = component(
        "FastAFScrapeComponent",
        url="https://example.com",
        dynamic="false",
        premium="false",
        proxy_country="us",
        wait="0",
        challenge_mode="false",
        session_number="session-1",
    )
    assert c.request_body() == {
        "url": "https://example.com",
        "dynamic": False,
        "premium": False,
        "country": "us",
        "wait": 0,
        "challenge_mode": False,
        "formats": "html",
        "session_number": "session-1",
    }


def test_search_optional_parameter_mapping():
    c = component(
        "FastAFSearchComponent",
        query="coffee",
        results="3",
        page="0",
        country="fr",
        language="fr",
        advanced_search=True,
        mobile="false",
        location="Paris, France",
    )
    body = c.request_body()
    assert body == {
        "query": "coffee",
        "results": 3,
        "page": 0,
        "country": "fr",
        "language": "fr",
        "advance_search": True,
        "mob_search": False,
        "location": "Paris, France",
    }


@pytest.mark.parametrize("resource", ["product", "offers", "bestsellers"])
def test_amazon_resource_gating(resource):
    c = component(
        "FastAFAmazonComponent",
        resource=resource,
        asin="B000000000",
        query="ignored",
        page="1",
        language="en",
        postal_code="10001",
        category_id="kitchen/289668",
        full_list="false",
    )
    body = c.request_body()
    assert "query" not in body
    if resource == "offers":
        assert "language" not in body
    if resource == "bestsellers":
        assert "asin" not in body
        assert "postal_code" not in body
        assert body["full_list"] is False
        assert body["category_id"] == "kitchen/289668"
    else:
        assert "page" not in body
        assert "category_id" not in body
        assert "full_list" not in body


def test_youtube_search_gates_transcript_params():
    c = component(
        "FastAFYouTubeComponent", resource="search", query="coffee", video_id="ignored", search_token=CONTINUATION
    )
    body = c.request_body()
    assert "v" not in body
    assert body["search_query"] == "coffee"
    assert body["sp"] == CONTINUATION


def test_news_jobs_and_maps_optional_params():
    news = component("FastAFNewsComponent", query="coffee", time_filter="qdr:d").request_body()
    jobs = component(
        "FastAFJobsComponent", query="developer", next_page_token=CONTINUATION, filters="employment_type:FULLTIME"
    )
    maps = component("FastAFMapsComponent", place_id="place", coordinates="@41.9,12.5,13z", page="20")
    assert news["tbs"] == "qdr:d"
    assert jobs.request_body()["next_page_token"] == CONTINUATION
    assert jobs.request_body()["chips"] == "employment_type:FULLTIME"
    assert maps.request_body()["place_id"] == "place"
    assert maps.request_body()["page"] == 20


def test_flattening_array_selection_and_empty_results():
    rows = data_rows({"results": [{"a": {"value": 1}, "items": [1, 2]}, {"b": True}]}, ("results",))
    assert [row.data for row in rows] == [
        {"a_value": 1, "items": "[1,2]", "b": None},
        {"a_value": None, "items": None, "b": True},
    ]
    assert data_rows({"results": []}, ("results",)) == []
    assert data_rows("text")[0].data == {"content": "text"}
    assert data_rows({"envelope": {"value": True}}, ("absent",))[0].data == {"envelope_value": True}


def test_response_size_limit():
    c = component("FastAFSearchComponent", query="coffee")
    with patch(STREAM_TARGET, mocked_stream("too much data")), patch("lfx_fastaf._base.MAX_RESPONSE_BYTES", 4):
        rows = c.fetch_content()
    assert "size/time limit" in rows[0].data["error"]


def test_response_deadline():
    c = component("FastAFSearchComponent", query="coffee")
    with patch(STREAM_TARGET, mocked_stream("data")), patch("lfx_fastaf._base.monotonic", side_effect=[0, 121]):
        rows = c.fetch_content()
    assert "size/time limit" in rows[0].data["error"]


def test_unknown_credit_headers_stay_unknown():
    c = component("FastAFSearchComponent", query="coffee")
    with patch(
        STREAM_TARGET, mocked_stream({}, headers={"x-fastaf-credits-used": "bad", "x-fastaf-credits-remaining": ""})
    ):
        c.fetch_content()
    assert c.last_request["credits_used"] is None
    assert c.last_request["credits_remaining"] is None


@pytest.mark.parametrize(
    ("value", "expected"), [(None, None), ("Default", None), ("true", True), ("false", False), (False, False)]
)
def test_optional_booleans(value, expected):
    assert boolean_option(value) is expected


@pytest.mark.parametrize("value", ["1.5", "abc", True])
def test_optional_integer_rejects_invalid_values(value):
    with pytest.raises(FastAFError):
        integer_option(value, "Number")


def test_screenshot_false_zero_and_dimension_strings():
    c = component("FastAFScreenshotComponent", url="https://example.com", width="1280", height="720", quality=0)
    body = c.request_body()
    assert body["width"] == "1280"
    assert body["height"] == "720"
    assert body["quality"] == 0
    assert body["fullPage"] is False


@pytest.mark.parametrize(
    ("payload", "content_type", "image_format"),
    [
        (PNG, "image/png", "png"),
        (b"\xff\xd8\xfftest", "image/jpeg", "jpg"),
        (b"RIFFxxxxWEBPtest", "image/webp", "webp"),
    ],
)
def test_screenshot_formats(payload, content_type, image_format):
    c = component("FastAFScreenshotComponent", url="https://example.com", format=image_format)
    with (
        patch(STREAM_TARGET, mocked_stream(payload, headers={"content-type": content_type})),
        patch(STORAGE_TARGET, return_value=storage_mock()),
    ):
        result = invoke(c)
    assert result.data["content_type"] == content_type


def test_screenshot_rejects_non_image_and_does_not_save():
    c = component("FastAFScreenshotComponent", url="https://example.com")
    storage = storage_mock()
    with patch(STREAM_TARGET, mocked_stream({"error": "not an image"})), patch(STORAGE_TARGET, return_value=storage):
        result = invoke(c)
    assert "unexpected screenshot" in result.data["error"]
    storage.save_file.assert_not_called()


def test_screenshot_storage_error_never_leaks_data_or_retries():
    c = component("FastAFScreenshotComponent", url="https://example.com")
    storage = storage_mock()
    storage.save_file.side_effect = OSError(f"Bearer {DUMMY_KEY}")
    stream = mocked_stream(PNG)
    with patch(STREAM_TARGET, stream), patch(STORAGE_TARGET, return_value=storage):
        result = invoke(c)
    assert "storage failed" in result.data["error"]
    assert DUMMY_KEY not in str(result)
    stream.assert_called_once()
