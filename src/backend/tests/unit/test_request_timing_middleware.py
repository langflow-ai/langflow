import langflow.middleware as middleware_module
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langflow.middleware import RequestTimingMiddleware, RequestTimingRegistry


def test_request_timing_registry_aggregates_by_route() -> None:
    registry = RequestTimingRegistry()

    for duration_ms, status_code in [(10.0, 200), (20.0, 200), (100.0, 500)]:
        registry.record(
            method="GET",
            route="/items/{item_id}",
            status_code=status_code,
            duration_ms=duration_ms,
            slow_threshold_ms=50.0,
        )

    route = registry.snapshot()["routes"][0]
    assert route == {
        "method": "GET",
        "route": "/items/{item_id}",
        "count": 3,
        "avg_ms": 43.33,
        "min_ms": 10.0,
        "max_ms": 100.0,
        "p50_ms": 20.0,
        "p95_ms": 100.0,
        "slow_count": 1,
        "error_count": 1,
    }


def test_request_timing_middleware_is_transparent_when_disabled(monkeypatch) -> None:
    class Settings:
        request_timing_enabled = False

    class SettingsService:
        settings = Settings()

    monkeypatch.setattr("langflow.middleware.get_settings_service", lambda: SettingsService())

    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_request_timing_middleware_records_route_template(monkeypatch) -> None:
    class Settings:
        request_timing_enabled = True
        request_timing_slow_threshold_ms = 0

    class SettingsService:
        settings = Settings()

    registry = RequestTimingRegistry()
    monkeypatch.setattr(middleware_module, "get_settings_service", lambda: SettingsService())
    monkeypatch.setattr(middleware_module, "request_timing_registry", registry)

    app = FastAPI()
    app.add_middleware(RequestTimingMiddleware)

    @app.get("/items/{item_id}")
    async def get_item(item_id: int) -> dict[str, int]:
        return {"item_id": item_id}

    response = TestClient(app).get("/items/42")

    assert response.status_code == 200
    route = registry.snapshot()["routes"][0]
    assert route["method"] == "GET"
    assert route["route"] == "/items/{item_id}"
    assert route["count"] == 1
    assert route["slow_count"] == 1
