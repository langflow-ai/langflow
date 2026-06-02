from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.components.jungle_grid.artifact_download_url import JungleGridCreateArtifactDownloadURLComponent
from lfx.components.jungle_grid.cancel_job import JungleGridCancelJobComponent
from lfx.components.jungle_grid.estimate_job import JungleGridEstimateJobComponent
from lfx.components.jungle_grid.get_job_logs import JungleGridGetJobLogsComponent
from lfx.components.jungle_grid.get_job_runtime import JungleGridGetJobRuntimeComponent
from lfx.components.jungle_grid.get_job_status import JungleGridGetJobStatusComponent
from lfx.components.jungle_grid.list_job_artifacts import JungleGridListJobArtifactsComponent
from lfx.components.jungle_grid.submit_job import JungleGridSubmitJobComponent

from tests.base import ComponentTestBaseWithoutClient

SECRET = "jg_test_secret_value"
SIGNED_URL = "https://api.junglegrid.dev/signed/test-token"


def _response(status_code: int = 200, payload: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.junglegrid.dev/test")
    return httpx.Response(status_code, json=payload or {"ok": True}, request=request)


def _default_kwargs() -> dict[str, Any]:
    return {
        "api_key": SECRET,
        "api_base_url": "https://api.junglegrid.dev",
        "name": "langflow-test",
        "image": "ghcr.io/junglegrid/hello-world:latest",
        "workload_type": "batch",
        "model_size_gb": 1,
        "command": "echo",
        "args": '["hello"]',
        "optimize_for": "cost",
        "job_id": "job_test",
        "artifact_id": "artifact_test",
        "reason": "test cancellation",
        "stream": "all",
    }


class JungleGridComponentTestBase(ComponentTestBaseWithoutClient):
    expected_method: str
    expected_path: str

    @pytest.fixture
    def default_kwargs(self) -> dict[str, Any]:
        return _default_kwargs()

    @pytest.fixture
    def file_names_mapping(self):
        return []

    async def test_latest_version(self, component_class, default_kwargs) -> None:
        await self._run_component(component_class, default_kwargs)

    def _kwargs_for(self, component_class, default_kwargs: dict[str, Any]) -> dict[str, Any]:
        input_names = {input_.name for input_ in component_class.inputs}
        return {key: value for key, value in default_kwargs.items() if key in input_names}

    async def _run_component(
        self,
        component_class,
        default_kwargs,
        payload: dict[str, Any] | None = None,
        expected_url: str | None = None,
    ):
        component = component_class(**self._kwargs_for(component_class, default_kwargs))
        method = getattr(component, component.outputs[0].method)
        mocked = AsyncMock(return_value=_response(payload=payload or {"id": "ok"}))
        with patch("httpx.AsyncClient.request", mocked):
            result = await method()
        assert result.data == (payload or {"id": "ok"})
        assert mocked.call_count == 1
        request_method = mocked.call_args.args[0]
        request_url = mocked.call_args.args[1]
        assert request_method == self.expected_method
        expected_base_url = default_kwargs.get("api_base_url", "https://api.junglegrid.dev").rstrip("/")
        assert request_url == (expected_url or f"{expected_base_url}{self.expected_path}")
        headers = mocked.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {SECRET}"
        assert SECRET not in str(result.data)
        return mocked

    def test_frontend_node_metadata(self, component_class, default_kwargs) -> None:
        component = component_class(**self._kwargs_for(component_class, default_kwargs))
        node = component.to_frontend_node()["data"]["node"]
        assert node["icon"] == "JungleGrid"
        assert node["display_name"] == component_class.display_name
        assert node["outputs"][0]["name"] == "data"
        assert "api_key" in node["template"]
        assert "api_base_url" in node["template"]

    async def test_configurable_alternate_base_url(self, component_class, default_kwargs) -> None:
        default_kwargs["api_base_url"] = "https://example.test"
        mocked = await self._run_component(component_class, default_kwargs)
        assert mocked.call_args.args[1] == f"https://example.test{self.expected_path}"

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 409, 429, 500])
    async def test_http_errors_are_sanitized(self, component_class, default_kwargs, status_code: int) -> None:
        component = component_class(**self._kwargs_for(component_class, default_kwargs))
        method = getattr(component, component.outputs[0].method)
        mocked = AsyncMock(return_value=_response(status_code, {"error": SECRET, "url": SIGNED_URL}))
        with patch("httpx.AsyncClient.request", mocked), pytest.raises(ValueError) as exc_info:
            await method()
        error_text = str(exc_info.value)
        assert f"Jungle Grid API error {status_code}" in error_text
        assert SECRET not in error_text
        assert SIGNED_URL not in error_text

    async def test_timeout_error_is_sanitized(self, component_class, default_kwargs) -> None:
        component = component_class(**self._kwargs_for(component_class, default_kwargs))
        method = getattr(component, component.outputs[0].method)
        with patch("httpx.AsyncClient.request", AsyncMock(side_effect=httpx.TimeoutException("timeout"))):
            with pytest.raises(ValueError) as exc_info:
                await method()
        assert "timed out" in str(exc_info.value)
        assert SECRET not in str(exc_info.value)

    async def test_network_error_is_sanitized(self, component_class, default_kwargs) -> None:
        component = component_class(**self._kwargs_for(component_class, default_kwargs))
        method = getattr(component, component.outputs[0].method)
        request = httpx.Request("GET", f"https://api.junglegrid.dev/?token={SECRET}")
        error = httpx.RequestError(f"network {SECRET}", request=request)
        with patch("httpx.AsyncClient.request", AsyncMock(side_effect=error)):
            with pytest.raises(ValueError) as exc_info:
                await method()
        assert SECRET not in str(exc_info.value)


class TestJungleGridEstimateJobComponent(JungleGridComponentTestBase):
    expected_method = "POST"
    expected_path = "/v1/jobs/estimate"

    @pytest.fixture
    def component_class(self):
        return JungleGridEstimateJobComponent

    async def test_required_workload_inputs(self, component_class, default_kwargs) -> None:
        default_kwargs["image"] = ""
        component = component_class(**default_kwargs)
        with pytest.raises(ValueError, match="Image is required"):
            await component.estimate_job()


class TestJungleGridSubmitJobComponent(JungleGridComponentTestBase):
    expected_method = "POST"
    expected_path = "/v1/jobs"

    @pytest.fixture
    def component_class(self):
        return JungleGridSubmitJobComponent

    async def test_submit_uses_one_request_and_callback_fields(self, component_class, default_kwargs) -> None:
        default_kwargs["callback_url"] = "https://example.test/callback"
        default_kwargs["callback_auth_token"] = "callback-secret"
        default_kwargs["callback_metadata"] = '{"source":"langflow"}'
        mocked = await self._run_component(component_class, default_kwargs)
        body = mocked.call_args.kwargs["json"]
        assert body["callback_url"] == "https://example.test/callback"
        assert body["callback_auth_token"] == "callback-secret"
        assert body["callback_metadata"] == {"source": "langflow"}
        assert mocked.call_count == 1


class TestJungleGridGetJobStatusComponent(JungleGridComponentTestBase):
    expected_method = "GET"
    expected_path = "/v1/jobs/job_test"

    @pytest.fixture
    def component_class(self):
        return JungleGridGetJobStatusComponent

    async def test_job_id_is_url_encoded(self, component_class, default_kwargs) -> None:
        default_kwargs["job_id"] = "job/with space"
        mocked = await self._run_component(
            component_class,
            default_kwargs,
            expected_url="https://api.junglegrid.dev/v1/jobs/job%2Fwith%20space",
        )
        assert mocked.call_args.args[1] == "https://api.junglegrid.dev/v1/jobs/job%2Fwith%20space"


class TestJungleGridGetJobRuntimeComponent(JungleGridComponentTestBase):
    expected_method = "GET"
    expected_path = "/v1/jobs/job_test/runtime"

    @pytest.fixture
    def component_class(self):
        return JungleGridGetJobRuntimeComponent


class TestJungleGridGetJobLogsComponent(JungleGridComponentTestBase):
    expected_method = "GET"
    expected_path = "/v1/jobs/job_test/logs"

    @pytest.fixture
    def component_class(self):
        return JungleGridGetJobLogsComponent

    async def test_log_query_options(self, component_class, default_kwargs) -> None:
        default_kwargs.update({"tail": 10, "limit": 20, "cursor": "cursor_test", "stream": "stderr"})
        mocked = await self._run_component(component_class, default_kwargs)
        assert mocked.call_args.kwargs["params"] == {
            "tail": 10,
            "limit": 20,
            "cursor": "cursor_test",
            "stream": "stderr",
        }


class TestJungleGridCancelJobComponent(JungleGridComponentTestBase):
    expected_method = "POST"
    expected_path = "/v1/jobs/job_test/cancel"

    @pytest.fixture
    def component_class(self):
        return JungleGridCancelJobComponent

    async def test_cancel_uses_one_request(self, component_class, default_kwargs) -> None:
        mocked = await self._run_component(component_class, default_kwargs)
        assert mocked.call_count == 1
        assert mocked.call_args.kwargs["json"] == {"reason": "test cancellation"}


class TestJungleGridListJobArtifactsComponent(JungleGridComponentTestBase):
    expected_method = "GET"
    expected_path = "/v1/jobs/job_test/artifacts"

    @pytest.fixture
    def component_class(self):
        return JungleGridListJobArtifactsComponent


class TestJungleGridCreateArtifactDownloadURLComponent(JungleGridComponentTestBase):
    expected_method = "POST"
    expected_path = "/v1/jobs/job_test/artifacts/artifact_test/download"

    @pytest.fixture
    def component_class(self):
        return JungleGridCreateArtifactDownloadURLComponent

    async def test_signed_url_is_returned_but_not_logged(self, component_class, default_kwargs) -> None:
        component = component_class(**default_kwargs)
        component.log = AsyncMock()
        mocked = AsyncMock(return_value=_response(payload={"download_url": SIGNED_URL, "expires_at": "2030-01-01"}))
        with patch("httpx.AsyncClient.request", mocked):
            result = await component.create_artifact_download_url()
        assert result.data["download_url"] == SIGNED_URL
        assert component.log.call_count == 0

    async def test_artifact_id_is_url_encoded(self, component_class, default_kwargs) -> None:
        default_kwargs["artifact_id"] = "artifact/with space"
        mocked = await self._run_component(
            component_class,
            default_kwargs,
            expected_url="https://api.junglegrid.dev/v1/jobs/job_test/artifacts/artifact%2Fwith%20space/download",
        )
        assert (
            mocked.call_args.args[1]
            == "https://api.junglegrid.dev/v1/jobs/job_test/artifacts/artifact%2Fwith%20space/download"
        )


@pytest.mark.api_key_required
@pytest.mark.skipif(not os.getenv("JUNGLE_GRID_API_KEY"), reason="JUNGLE_GRID_API_KEY is not set")
class TestJungleGridLiveSmoke:
    async def test_estimate_read_only_smoke(self) -> None:
        component = JungleGridEstimateJobComponent(
            api_key=os.environ["JUNGLE_GRID_API_KEY"],
            api_base_url="https://api.junglegrid.dev",
            name="langflow-smoke-estimate",
            image=os.getenv("JUNGLE_GRID_SMOKE_IMAGE", "ghcr.io/junglegrid/hello-world:latest"),
            workload_type=os.getenv("JUNGLE_GRID_SMOKE_WORKLOAD_TYPE", "batch"),
            model_size_gb=float(os.getenv("JUNGLE_GRID_SMOKE_MODEL_SIZE_GB", "1")),
            command=os.getenv("JUNGLE_GRID_SMOKE_COMMAND", "echo"),
            args='["langflow-smoke"]',
        )
        result = await component.estimate_job()
        assert isinstance(result.data, dict)
