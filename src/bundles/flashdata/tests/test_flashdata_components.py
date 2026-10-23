"""Exercise real Langflow component and Agent tool paths without network access."""

import copy
import importlib.util
import json
import socket
from pathlib import Path

import httpx
import lfx_flashdata as integration
import pytest
from lfx.extension import load_extension, validate_extension
from lfx_flashdata import _base
from lfx_flashdata._client import Client, FlashDataError
from pydantic import SecretStr

CAPABILITIES = json.loads(Path(__file__).with_name("capabilities.json").read_text())
REALTIME = [item for item in CAPABILITIES if item["source"] != "youtube_download"]
CLASSES = [getattr(integration, name) for name in integration.__all__]


def component_class(source):
    return next(cls for cls in CLASSES if cls.source == source)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        pytest.fail("Unexpected outbound connection")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


@pytest.fixture
def mock_api(monkeypatch):
    requests = []
    handler = None

    def set_handler(callback):
        nonlocal handler
        handler = callback
        return requests

    def transport(request):
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(_base, "Client", lambda key: Client(key, transport=httpx.MockTransport(transport)))
    return set_handler


@pytest.mark.parametrize("capability", REALTIME, ids=lambda item: item["source"])
@pytest.mark.parametrize("as_tool", [False, True])
async def test_source_contract_through_component_and_agent_tool(capability, as_tool, mock_api):
    response = copy.deepcopy(capability["outputExample"])
    response["future_provider_field"] = {"preserved": True}
    requests = mock_api(lambda _: httpx.Response(200, json=response))
    cls = component_class(capability["source"])
    values = copy.deepcopy(capability["sample"])
    primary = values.pop(cls.primary)
    kwargs = {"api_key": SecretStr("mock-private-key")}
    if any(field.name == "parameters" for field in cls.inputs):
        kwargs["parameters"] = json.dumps(values)
    if as_tool:
        component = cls(**kwargs)
        tools = await component.to_toolkit()
        assert len(tools) == 1
        assert tools[0].name == "flashdata_" + capability["source"]
        assert set(tools[0].args_schema.model_json_schema()["properties"]) == {cls.primary}
        result = await tools[0].ainvoke({cls.primary: primary})
        assert "future_provider_field" in str(result)
    else:
        component = cls(**kwargs, **{cls.primary: primary})
        result = await getattr(component, component.outputs[0].method)()
        assert {key: result.data[key] for key in response} == response
    assert len(requests) == 1
    expected = cls.input_model.model_validate(capability["sample"]).model_dump(exclude_none=True, by_alias=True)
    assert json.loads(requests[0].content) == {
        "source": capability["source"],
        cls.primary: expected.pop(cls.primary),
        "params": expected,
    }
    assert requests[0].headers["X-API-Key"] == "mock-private-key"


def test_extension_loads_all_components():
    package = Path(integration.__file__).parent
    validated = validate_extension(package)
    assert validated.ok, validated.errors
    loaded = load_extension(package, distribution="lfx-flashdata")
    assert loaded.ok, loaded.errors
    assert {item.class_name for item in loaded.components} == set(integration.__all__)


@pytest.mark.parametrize("cls", CLASSES, ids=lambda cls: cls.__name__)
async def test_tool_schema_keeps_credentials_and_submit_authorization_out(cls):
    component = cls(api_key=SecretStr("mock-private-key"))
    tools = await component.to_toolkit()
    assert len(tools) == 1
    properties = tools[0].args_schema.model_json_schema()["properties"]
    assert set(properties) == {cls.primary}
    assert "mock-private-key" not in str(properties)
    secret_fields = [field for field in cls.inputs if field.name in ("api_key", "storage_json")]
    assert all(field.password and not field.track_in_telemetry for field in secret_fields)


@pytest.mark.parametrize(
    "parameters",
    ['{"num":true}', '{"num":101}', '{"source":"youtube_download"}', '{"query":"replace"}', "[]", "bad JSON"],
)
async def test_invalid_parameters_never_send(parameters, mock_api):
    requests = mock_api(lambda _: pytest.fail("Unexpected request"))
    component = integration.FlashDataGoogleSearchComponent(api_key="test-key", query="ocean", parameters=parameters)
    with pytest.raises(FlashDataError):
        await component.execute()
    assert not requests


async def test_omitted_google_options_and_caption_defaults(mock_api):
    requests = mock_api(lambda _: httpx.Response(200, json={"results": []}))
    await integration.FlashDataGoogleSearchComponent(api_key="test-key", query="ocean").execute()
    await integration.FlashDataYouTubeCaptionsComponent(api_key="test-key", video_id="dQw4w9WgXcQ").execute()
    await integration.FlashDataYouTubeTranscriptComponent(api_key="test-key", video_id="dQw4w9WgXcQ").execute()
    assert json.loads(requests[0].content)["params"] == {}
    assert json.loads(requests[1].content)["params"]["auto"] is False
    assert json.loads(requests[2].content)["params"]["auto"] is True


async def test_missing_key_prevents_request(mock_api):
    requests = mock_api(lambda _: pytest.fail("Unexpected request"))
    with pytest.raises(FlashDataError, match="API Key"):
        await integration.FlashDataGoogleSearchComponent(query="ocean").execute()
    assert not requests


@pytest.mark.parametrize("status", [401, 402, 403, 429, 500])
async def test_http_errors_are_redacted_and_not_retried(status, mock_api):
    requests = mock_api(lambda _: httpx.Response(status, json={"error": "private-response"}))
    with pytest.raises(FlashDataError) as caught:
        await integration.FlashDataGoogleSearchComponent(api_key="test-key", query="ocean").execute()
    assert str(status) in str(caught.value)
    assert "private-response" not in str(caught.value)
    assert len(requests) == 1


async def test_timeout_reports_unknown_billing_without_retry(mock_api):
    def handler(request):
        msg = "private-response"
        raise httpx.ReadTimeout(msg, request=request)

    requests = mock_api(handler)
    with pytest.raises(FlashDataError, match="already have been accepted"):
        await integration.FlashDataGoogleSearchComponent(api_key="test-key", query="ocean").execute()
    assert len(requests) == 1


async def test_download_requires_operator_authorization(mock_api):
    requests = mock_api(lambda _: pytest.fail("Unexpected request"))
    with pytest.raises(FlashDataError, match="Allow Paid Submission"):
        await integration.FlashDataYouTubeDownloadSubmitComponent(video_id="dQw4w9WgXcQ").execute()
    assert not requests


async def test_download_submits_once_and_redacts_storage(mock_api):
    storage = {
        "storage_type": "s3",
        "storage_url": "customer-owned-bucket",
        "access_key": "private-access",
        "secret_key": "private-secret",
    }
    requests = mock_api(
        lambda _: httpx.Response(
            200,
            json={"id": "job_saved", "status": "pending", "source": "youtube_download", "params": {"storage": storage}},
        )
    )
    component = integration.FlashDataYouTubeDownloadSubmitComponent(
        api_key="test-key",
        storage_json=SecretStr(json.dumps(storage)),
        allow_submit=True,
        parameters='{"download_type":"audio","output_format":"m4a"}',
    )
    tool = (await component.to_toolkit())[0]
    result = await tool.ainvoke({"video_id": "dQw4w9WgXcQ"})
    assert "job_saved" in str(result)
    assert "private-" not in str(result)
    assert len(requests) == 1
    assert requests[0].url.path == "/v1/queries"
    assert json.loads(requests[0].content)["params"]["storage"] == storage


@pytest.mark.parametrize(("source", "job_id"), [("google_search", "job_saved"), ("youtube_download", "job_other")])
async def test_job_reader_rejects_wrong_source_or_receipt(source, job_id, mock_api):
    requests = mock_api(
        lambda _: httpx.Response(200, json={"job": {"source": source, "id": job_id, "status": "completed"}})
    )
    with pytest.raises(FlashDataError):
        await integration.FlashDataYouTubeDownloadStatusComponent(api_key="test-key", job_id="job_saved").execute()
    assert len(requests) == 1


@pytest.mark.parametrize("trusted", [True, False])
@pytest.mark.parametrize("signed_query", ["", "?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=mock-signature"])
async def test_result_follows_only_trusted_storage_without_api_key(trusted, signed_query, mock_api):
    def handler(request):
        if request.url.path == "/v2/jobs/job_saved":
            return httpx.Response(
                200,
                json={
                    "job": {
                        "id": "job_saved",
                        "source": "youtube_download",
                        "status": "completed",
                        "params": {"secret_key": "private-storage"},
                    }
                },
            )
        if request.url.path == "/v2/api-access":
            return httpx.Response(200, json={"result_origin": "https://results.example.com"})
        if request.url.path.endswith("/results"):
            host = "results.example.com" if trusted else "other.example.com"
            return httpx.Response(302, headers={"location": f"https://{host}/job.json{signed_query}"})
        assert "X-API-Key" not in request.headers
        assert str(request.url) == f"https://results.example.com/job.json{signed_query}"
        return httpx.Response(200, json={"files": [{"url": "s3://customer-owned-bucket/video.mp4"}]})

    requests = mock_api(handler)
    component = integration.FlashDataYouTubeDownloadResultComponent(api_key="test-key", job_id="job_saved")
    if trusted:
        result = await component.execute()
        assert "private-storage" not in str(result)
        assert "files" in result.data["output"]
    else:
        with pytest.raises(FlashDataError, match="trusted FlashData storage"):
            await component.execute()
    assert len(requests) == (4 if trusted else 3)
    assert all(request.method == "GET" for request in requests)


async def test_pending_job_only_reads_once(mock_api):
    requests = mock_api(
        lambda _: httpx.Response(
            200, json={"job": {"id": "job_saved", "source": "youtube_download", "status": "processing"}}
        )
    )
    result = await integration.FlashDataYouTubeDownloadResultComponent(api_key="test-key", job_id="job_saved").execute()
    assert result.data["job"]["status"] == "processing"
    assert "output" not in result.data
    assert len(requests) == 1


@pytest.mark.parametrize("capability", REALTIME, ids=lambda item: item["source"])
async def test_connected_graph_reaches_parser_once(capability, mock_api):
    from lfx.components.processing.parser import ParserComponent
    from lfx.graph import Graph

    response = capability["outputExample"]
    requests = mock_api(lambda _: httpx.Response(200, json=response))
    cls = component_class(capability["source"])
    values = dict(capability["sample"])
    primary = values.pop(cls.primary)
    kwargs = {"api_key": "FLASHDATA_API_KEY", cls.primary: primary}
    if any(field.name == "parameters" for field in cls.inputs):
        kwargs["parameters"] = json.dumps(values)
    component = cls(**kwargs)
    parser = ParserComponent(mode="Parser", pattern="{text}")
    parser.set(input_data=getattr(component, component.outputs[0].method))
    graph = Graph(component, parser)
    graph.context.update({"request_variables": {"FLASHDATA_API_KEY": SecretStr("test-key")}, "no_env_fallback": True})
    results = [result async for result in graph.async_start()]
    builds = [item for item in results if hasattr(item, "result_dict")]
    assert len(builds) == 2
    assert len(requests) == 1
    assert json.loads(builds[-1].result_dict.artifacts["parsed_text"]["raw"]) == response


@pytest.mark.parametrize("capability", CAPABILITIES, ids=lambda item: item["source"])
async def test_documented_source_example_executes_without_model(capability, monkeypatch, mock_api):
    source = capability["source"]
    if source == "youtube_download":
        response = {"job": {"id": "job_saved", "source": source, "status": "processing"}}
    else:
        response = capability["outputExample"]
    requests = mock_api(lambda _: httpx.Response(200, json=response))
    monkeypatch.setenv("FLASHDATA_API_KEY", "test-key")
    monkeypatch.setenv("FLASHDATA_DOWNLOAD_JOB_ID", "job_saved")
    path = Path(__file__).parents[1] / "examples" / f"{source}.py"
    spec = importlib.util.spec_from_file_location(f"flashdata_example_{source}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    graph = module.get_graph()
    results = [item async for item in graph.async_start() if hasattr(item, "result_dict")]
    assert len(results) == 2
    assert json.loads(results[-1].result_dict.artifacts["parsed_text"]["raw"]) == response
    assert len(requests) == 1
    assert requests[0].method == ("GET" if source == "youtube_download" else "POST")
