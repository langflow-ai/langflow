import httpx
import pytest
from lfx.components.bilig.workpaper_formula_readback import (
    BiligWorkPaperFormulaReadbackComponent,
    call_bilig_forecast,
    compact_proof,
)


class FakeResponse:
    def __init__(self, body, error: Exception | None = None):
        self.body = body
        self.error = error

    def json(self):
        return self.body

    def raise_for_status(self):
        if self.error is not None:
            raise self.error


class FakeClient:
    def __init__(
        self,
        *,
        captured: dict,
        response: FakeResponse,
        timeout: int,
        headers: dict,
        post_error: Exception | None = None,
    ):
        captured["timeout"] = timeout
        captured["headers"] = headers
        self.captured = captured
        self.response = response
        self.post_error = post_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def post(self, url: str, json: dict):
        if self.post_error is not None:
            raise self.post_error
        self.captured["url"] = url
        self.captured["json"] = json
        return self.response


def test_call_bilig_forecast_posts_expected_payload(monkeypatch):
    captured = {}

    def fake_client(*, timeout, headers):
        return FakeClient(
            captured=captured,
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {
                    "verified": True,
                    "editedCell": "Inputs!B3",
                    "before": {"expectedArr": 60000, "targetGap": -34000},
                    "after": {"expectedArr": 96000, "targetGap": 5600},
                    "checks": {
                        "formulasPersisted": True,
                        "restoredMatchesAfter": True,
                        "computedOutputChanged": True,
                    },
                }
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)

    result = call_bilig_forecast(
        base_url="https://bilig.example",
        sheet_name="Inputs",
        address="B3",
        value=0.4,
        timeout=7,
    )

    assert captured == {
        "url": "https://bilig.example/api/workpaper/n8n/forecast",
        "headers": {
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": "langflow-bilig-workpaper/0.1.0",
        },
        "json": {"sheetName": "Inputs", "address": "B3", "value": 0.4},
        "timeout": 7,
    }
    assert result["verified"] is True


def test_call_bilig_forecast_rejects_non_object_json(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse(["not", "an", "object"]),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)

    with pytest.raises(TypeError, match="Expected JSON object response, received list"):
        call_bilig_forecast(
            base_url="https://bilig.example",
            sheet_name="Inputs",
            address="B3",
            value=0.4,
            timeout=7,
        )


def test_call_bilig_forecast_propagates_http_errors(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {"verified": True},
                error=httpx.HTTPStatusError(
                    "upstream unavailable",
                    request=httpx.Request("POST", "https://bilig.example/api/workpaper/n8n/forecast"),
                    response=httpx.Response(503),
                ),
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)

    with pytest.raises(httpx.HTTPStatusError, match="upstream unavailable"):
        call_bilig_forecast(
            base_url="https://bilig.example",
            sheet_name="Inputs",
            address="B3",
            value=0.4,
            timeout=7,
        )


def test_call_bilig_forecast_rejects_non_http_base_url():
    with pytest.raises(ValueError, match="base_url must start with http:// or https://"):
        call_bilig_forecast(
            base_url="ftp://bilig.example",
            sheet_name="Inputs",
            address="B3",
            value=0.4,
            timeout=7,
        )


def test_call_bilig_forecast_rejects_unverified_response_with_safe_message(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {
                    "verified": False,
                    "workpaper_id": "proof-123",
                    "secret": "do-not-leak",
                }
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)

    with pytest.raises(
        ValueError,
        match=r"Unverified WorkPaper response \(verified=False\) for workpaper_id=proof-123",
    ) as error:
        call_bilig_forecast(
            base_url="https://bilig.example",
            sheet_name="Inputs",
            address="B3",
            value=0.4,
            timeout=7,
        )

    assert str(error.value) == "Unverified WorkPaper response (verified=False) for workpaper_id=proof-123"
    assert "do-not-leak" not in str(error.value)


def test_component_returns_error_when_http_request_fails(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {},
                error=httpx.ConnectError("connection refused"),
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)
    component = BiligWorkPaperFormulaReadbackComponent()
    component.base_url = "https://bilig.example"
    component.sheet_name = "Inputs"
    component.address = "B3"
    component.value = 0.4
    component.timeout = 7

    result = component.verify_formula_readback()

    assert result.data == {"error": "Bilig WorkPaper formula readback failed: connection refused"}
    assert component.status == result.data["error"]


def test_component_returns_error_when_request_times_out(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse({}),
            post_error=TimeoutError("request timed out"),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)
    component = BiligWorkPaperFormulaReadbackComponent()
    component.base_url = "https://bilig.example"
    component.sheet_name = "Inputs"
    component.address = "B3"
    component.value = 0.4
    component.timeout = 7

    result = component.verify_formula_readback()

    assert result.data == {"error": "Bilig WorkPaper formula readback failed: request timed out"}
    assert component.status == result.data["error"]


def test_component_returns_error_when_response_is_unverified(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse({"verified": False, "workpaper_id": "proof-123"}),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)
    component = BiligWorkPaperFormulaReadbackComponent()
    component.base_url = "https://bilig.example"
    component.sheet_name = "Inputs"
    component.address = "B3"
    component.value = 0.4
    component.timeout = 7

    result = component.verify_formula_readback()

    assert result.data == {
        "error": "Bilig WorkPaper formula readback failed: "
        "Unverified WorkPaper response (verified=False) for workpaper_id=proof-123"
    }
    assert component.status == result.data["error"]


def test_component_returns_compact_formula_readback_proof(monkeypatch):
    def fake_client(*, timeout, headers):
        return FakeClient(
            captured={},
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {
                    "verified": True,
                    "editedCell": "Inputs!B3",
                    "before": {"expectedArr": 60000, "targetGap": -34000},
                    "after": {"expectedArr": 96000, "targetGap": 5600},
                    "checks": {
                        "formulasPersisted": True,
                        "restoredMatchesAfter": True,
                        "computedOutputChanged": True,
                    },
                }
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)
    component = BiligWorkPaperFormulaReadbackComponent()
    component.base_url = "https://bilig.example"
    component.sheet_name = "Inputs"
    component.address = "b3"
    component.value = 0.4
    component.timeout = 7

    result = component.verify_formula_readback()

    assert result.data == {
        "verified": True,
        "editedCell": "Inputs!B3",
        "before": {"expectedArr": 60000, "targetGap": -34000},
        "after": {"expectedArr": 96000, "targetGap": 5600},
        "checks": {
            "formulasPersisted": True,
            "restoredMatchesAfter": True,
            "computedOutputChanged": True,
        },
        "source": "Bilig WorkPaper",
        "github": "https://github.com/proompteng/bilig",
    }
    assert component.status == result.data


def test_component_uses_defaults_and_normalizes_address(monkeypatch):
    captured = {}

    def fake_client(*, timeout, headers):
        return FakeClient(
            captured=captured,
            timeout=timeout,
            headers=headers,
            response=FakeResponse(
                {
                    "verified": True,
                    "editedCell": "Inputs!B3",
                    "checks": {"formulasPersisted": True},
                }
            ),
        )

    monkeypatch.setattr("lfx.components.bilig.workpaper_formula_readback.httpx.Client", fake_client)
    component = BiligWorkPaperFormulaReadbackComponent()
    component.base_url = ""
    component.sheet_name = ""
    component.address = "b3"
    component.value = 0.4
    component.timeout = 0

    result = component.verify_formula_readback()

    assert captured["url"] == "https://bilig.proompteng.ai/api/workpaper/n8n/forecast"
    assert captured["json"] == {"sheetName": "Inputs", "address": "B3", "value": 0.4}
    assert captured["timeout"] == 30
    assert result.data["verified"] is True


def test_compact_proof_handles_missing_or_invalid_nested_fields():
    result = compact_proof(
        {
            "verified": True,
            "editedCell": "Inputs!B3",
            "before": "missing",
            "after": {"expectedArr": 96000},
            "checks": {"formulasPersisted": "true", "restoredMatchesAfter": True},
        }
    )

    assert result == {
        "verified": True,
        "editedCell": "Inputs!B3",
        "before": {"expectedArr": None, "targetGap": None},
        "after": {"expectedArr": 96000, "targetGap": None},
        "checks": {
            "formulasPersisted": False,
            "restoredMatchesAfter": True,
            "computedOutputChanged": False,
        },
        "source": "Bilig WorkPaper",
        "github": "https://github.com/proompteng/bilig",
    }
