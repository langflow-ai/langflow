"""Unit tests for the shared GenMagic helpers (errors, catalog, video polling) with mocked HTTP calls."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest
from lfx_bundles.genmagic import genmagic_common as common
from lfx_bundles.genmagic.genmagic_common import GenMagicAPIError, GenMagicVideoTimeoutError

from .conftest import API_KEY, api_url, response


@pytest.mark.unit
def test_client_header_names_langflow() -> None:
    assert common.client_header().startswith("langflow/")


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected"),
    [("", None), ("  ", None), (None, None), ("auto", None), ("AUTO", None), (" vendor/model ", "vendor/model")],
)
def test_chosen_model_omits_auto(value, expected) -> None:
    assert common.chosen_model(value) == expected


@pytest.mark.unit
class TestCallApi:
    def test_sends_bearer_key_and_client_header(self) -> None:
        with patch("httpx.Client.request", return_value=response(json_body={})) as request:
            common.call_api("GET", "/usage", api_key=f"  {API_KEY}  ")

        method, url = request.call_args.args
        assert (method, url) == ("GET", api_url("/usage"))
        headers = request.call_args.kwargs["headers"]
        assert headers["Authorization"] == f"Bearer {API_KEY}"
        assert headers["X-GenMagic-Client"] == common.client_header()

    @pytest.mark.parametrize("key", [None, "", "   "])
    def test_missing_key_makes_no_request(self, key) -> None:
        with patch("httpx.Client.request") as request, pytest.raises(GenMagicAPIError, match="get-api-key"):
            common.call_api("GET", "/usage", api_key=key)

        request.assert_not_called()

    def test_invalid_key_error_points_to_key_page(self) -> None:
        body = {"error": {"message": "invalid", "type": "authentication_error", "code": "invalid_api_key"}}
        with (
            patch("httpx.Client.request", return_value=response(401, json_body=body)),
            pytest.raises(GenMagicAPIError) as caught,
        ):
            common.call_api("GET", "/usage", api_key=API_KEY)

        assert caught.value.status == 401
        assert caught.value.code == "invalid_api_key"
        assert "rejected the API key (401)" in str(caught.value)
        assert "https://genmagic.co/get-api-key" in str(caught.value)

    def test_insufficient_balance_error_points_to_pricing(self) -> None:
        body = {"error": {"message": "Balance would go negative", "code": "insufficient_quota"}}
        with (
            patch("httpx.Client.request", return_value=response(402, json_body=body)),
            pytest.raises(GenMagicAPIError) as caught,
        ):
            common.call_api("POST", "/videos", api_key=API_KEY, json={})

        assert "balance is too low for this request (402)" in str(caught.value)
        assert "Balance would go negative" in str(caught.value)
        assert "https://genmagic.co/pricing" in str(caught.value)

    def test_unverified_email_error_is_explained(self) -> None:
        body = {"error": {"message": "Verify your email", "code": "email_verification_required"}}
        with (
            patch("httpx.Client.request", return_value=response(403, json_body=body)),
            pytest.raises(GenMagicAPIError, match="is not verified"),
        ):
            common.call_api("POST", "/videos", api_key=API_KEY, json={})

    def test_rate_limit_is_transient(self) -> None:
        with (
            patch("httpx.Client.request", return_value=response(429, json_body={"error": {"message": "slow down"}})),
            pytest.raises(GenMagicAPIError) as caught,
        ):
            common.call_api("GET", "/usage", api_key=API_KEY)

        assert caught.value.transient
        assert "rate limit" in str(caught.value)

    @pytest.mark.parametrize("message", [f"bad key {API_KEY}", "x" * 290 + API_KEY], ids=["whole", "cut-at-limit"])
    def test_key_is_redacted_from_error_detail(self, message: str) -> None:
        # The second message puts the key across the 300-character cap on the echoed detail.
        body = {"error": {"message": message}}
        with (
            patch("httpx.Client.request", return_value=response(500, json_body=body)),
            pytest.raises(GenMagicAPIError) as caught,
        ):
            common.call_api("GET", "/usage", api_key=API_KEY)

        assert "gm_live" not in str(caught.value)

    def test_non_json_error_uses_the_response_text(self) -> None:
        with (
            patch("httpx.Client.request", return_value=response(502, text="<html>bad   gateway</html>")),
            pytest.raises(GenMagicAPIError, match="502") as caught,
        ):
            common.call_api("GET", "/usage", api_key=API_KEY)

        assert "bad gateway" in str(caught.value)

    def test_timeout_and_network_errors_are_reported(self) -> None:
        with (
            patch("httpx.Client.request", side_effect=httpx.ReadTimeout("slow")),
            pytest.raises(GenMagicAPIError, match=r"did not answer within 2\.5 seconds") as caught,
        ):
            common.call_api("GET", "/usage", api_key=API_KEY, timeout=2.5)
        assert caught.value.transient

        with (
            patch("httpx.Client.request", side_effect=httpx.ConnectError("refused")),
            pytest.raises(GenMagicAPIError, match="Could not reach GenMagic: ConnectError"),
        ):
            common.call_api("GET", "/usage", api_key=API_KEY)

    def test_non_object_json_is_rejected(self) -> None:
        with pytest.raises(GenMagicAPIError, match="unexpected response shape"):
            common.response_json(response(json_body=[1, 2]))
        with pytest.raises(GenMagicAPIError, match="not JSON"):
            common.response_json(response(text="nope"))

    def test_metering_reads_cost_headers(self) -> None:
        reply = response(json_body={}, headers={"X-Cost-Cents": "4.5", "X-Credits-Remaining": "x"})
        assert common.metering(reply) == {"cost_cents": 4.5}


@pytest.mark.unit
class TestCatalog:
    MODELS = {
        "data": [
            {"id": "old/model", "name": "Old", "created": 100},
            {"id": "new/model", "name": "New", "created": 300},
            {"id": "mid/b", "name": "B", "created": 200},
            {"id": "mid/a", "name": "A", "created": 200},
            {"name": "no id"},
            "not a model",
        ]
    }

    def test_list_models_is_public_and_newest_first(self) -> None:
        with patch("httpx.Client.request", return_value=response(json_body=self.MODELS)) as request:
            models = common.list_models("image")

        assert [m["id"] for m in models] == ["new/model", "mid/a", "mid/b", "old/model"]
        assert request.call_args.args == ("GET", api_url("/models"))
        assert request.call_args.kwargs["params"] == {"category": "image"}
        assert "Authorization" not in request.call_args.kwargs["headers"]

    def test_refresh_puts_auto_first(self) -> None:
        build_config = {"model_name": {"options": [], "value": "auto"}}
        with patch("httpx.Client.request", return_value=response(json_body=self.MODELS)):
            common.refresh_model_dropdown(build_config, "model_name", "image", include_auto=True)

        assert build_config["model_name"]["options"] == ["auto", "new/model", "mid/a", "mid/b", "old/model"]
        assert build_config["model_name"]["value"] == "auto"

    def test_refresh_keeps_the_dropdown_when_genmagic_is_unreachable(self) -> None:
        build_config = {"model_name": {"options": ["kept"], "value": "kept"}}
        with patch("httpx.Client.request", side_effect=httpx.ConnectError("offline")):
            common.refresh_model_dropdown(build_config, "model_name", "text", include_auto=False)

        assert build_config["model_name"]["options"] == ["kept"]


@pytest.mark.unit
class TestWaitForVideo:
    @staticmethod
    def _poll(job: dict, **kwargs):
        return common.wait_for_video(job, api_key=API_KEY, timeout=60, poll_interval=5, **kwargs)

    def test_returns_without_polling_when_already_finished(self) -> None:
        with patch("httpx.Client.request") as request:
            job, costs = self._poll({"id": "vid_1", "status": "completed", "url": "https://x/v.mp4"})

        request.assert_not_called()
        assert job["url"] == "https://x/v.mp4"
        assert costs == {}

    def test_polls_until_completed_and_reads_the_cost(self, no_sleep) -> None:
        replies = [
            response(json_body={"id": "vid_1", "status": "processing"}),
            response(
                json_body={"id": "vid_1", "status": "completed", "url": "https://x/v.mp4", "cost_cents": 12},
                headers={"X-Cost-Cents": "12", "X-Credits-Remaining": "88"},
            ),
        ]
        with patch("httpx.Client.request", side_effect=replies) as request:
            job, costs = self._poll({"id": "vid_1", "status": "queued"})

        assert job["status"] == "completed"
        assert costs == {"cost_cents": 12.0, "balance_cents": 88.0}
        assert request.call_count == 2
        assert request.call_args.args == ("GET", api_url("/videos/vid_1"))
        assert no_sleep.call_count == 2

    def test_job_id_is_quoted_in_the_path(self) -> None:
        with (
            patch("httpx.Client.request", return_value=response(json_body={"status": "completed"})) as request,
            patch("time.sleep"),
        ):
            self._poll({"id": "a/b c", "status": "queued"})

        assert request.call_args.args[1] == api_url("/videos/a%2Fb%20c")

    def test_timeout_names_the_job_and_carries_the_last_state(self) -> None:
        now = iter([0.0, 0.0, 61.0])
        replies = [response(json_body={"id": "vid_1", "status": "processing", "model": "m"})]
        with patch("httpx.Client.request", side_effect=replies), pytest.raises(GenMagicVideoTimeoutError) as caught:
            self._poll({"id": "vid_1", "status": "queued"}, sleep=lambda _: None, clock=lambda: next(now))

        assert "vid_1" in str(caught.value)
        assert "GenMagic Video Status" in str(caught.value)
        assert caught.value.job["status"] == "processing"

    def test_sleep_never_runs_past_the_deadline(self) -> None:
        waits: list[float] = []
        now = iter([0.0, 0.0, 58.0, 61.0])
        replies = [response(json_body={"id": "vid_1", "status": "processing"})] * 2
        with patch("httpx.Client.request", side_effect=replies), pytest.raises(GenMagicVideoTimeoutError):
            self._poll({"id": "vid_1", "status": "queued"}, sleep=waits.append, clock=lambda: next(now))

        assert waits == [5, 2.0]

    def test_transient_poll_errors_are_tolerated(self, no_sleep) -> None:
        replies = [
            response(503, json_body={"error": {"message": "overloaded"}}),
            response(429, json_body={"error": {"message": "slow down"}}),
            response(json_body={"id": "vid_1", "status": "completed", "url": "https://x/v.mp4"}),
        ]
        with patch("httpx.Client.request", side_effect=replies):
            job, _ = self._poll({"id": "vid_1", "status": "queued"})

        assert job["status"] == "completed"
        assert no_sleep.call_count == 3

    def test_too_many_failed_polls_give_up_and_name_the_job(self, no_sleep) -> None:
        replies = [response(503, json_body={"error": {"message": "down"}})] * common.MAX_POLL_FAILURES
        with patch("httpx.Client.request", side_effect=replies), pytest.raises(GenMagicAPIError) as caught:
            self._poll({"id": "vid_1", "status": "queued"})

        assert "vid_1" in str(caught.value)
        assert no_sleep.call_count == common.MAX_POLL_FAILURES

    @pytest.mark.parametrize("status", [401, 402, 404])
    def test_errors_that_retrying_cannot_fix_are_raised_at_once(self, status, no_sleep) -> None:
        with (
            patch("httpx.Client.request", return_value=response(status, json_body={"error": {"message": "no"}})),
            pytest.raises(GenMagicAPIError) as caught,
        ):
            self._poll({"id": "vid_1", "status": "queued"})

        assert caught.value.status == status
        assert "vid_1" in str(caught.value)
        assert no_sleep.call_count == 1

    def test_job_without_an_id_is_an_error(self) -> None:
        with pytest.raises(GenMagicAPIError, match="did not return a video job ID"):
            self._poll({"status": "queued"})
