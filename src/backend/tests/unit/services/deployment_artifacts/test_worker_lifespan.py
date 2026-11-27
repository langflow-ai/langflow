"""A ``langflow worker`` runs what an extension registered for it, and stops before it claims if that fails."""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from langflow.services.deployment_artifacts import activation


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    monkeypatch.setattr(activation, "_worker_lifespans", [])
    monkeypatch.setattr(activation, "_extensions_loaded", True)


async def test_the_registered_lifespans_wrap_the_worker_in_order():
    events: list[str] = []

    def lifespan(name):
        @asynccontextmanager
        async def run():
            events.append(f"start {name}")
            try:
                yield
            finally:
                events.append(f"stop {name}")

        return run

    activation.register_worker_lifespan(lifespan("a"))
    activation.register_worker_lifespan(lifespan("b"))
    async with activation.worker_lifespan():
        events.append("serving")
    assert events == ["start a", "start b", "serving", "stop b", "stop a"]


async def test_registering_the_same_lifespan_twice_runs_it_once():
    started = []

    @asynccontextmanager
    async def run():
        started.append(1)
        yield

    activation.register_worker_lifespan(run)
    activation.register_worker_lifespan(run)
    async with activation.worker_lifespan():
        pass
    assert started == [1]


async def test_a_lifespan_that_fails_stops_the_worker_and_closes_the_ones_already_open():
    closed = []

    @asynccontextmanager
    async def good():
        try:
            yield
        finally:
            closed.append("good")

    @asynccontextmanager
    async def bad():
        msg = "cannot hydrate"
        raise RuntimeError(msg)
        yield

    activation.register_worker_lifespan(good)
    activation.register_worker_lifespan(bad)
    with pytest.raises(RuntimeError, match="cannot hydrate"):
        async with activation.worker_lifespan():
            pytest.fail("the worker must not start")
    assert closed == ["good"]


async def test_the_extensions_load_before_the_lifespans_run(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(activation, "load_activation_extensions", lambda: order.append("load"))

    @asynccontextmanager
    async def run():
        order.append("lifespan")
        yield

    activation.register_worker_lifespan(run)
    async with activation.worker_lifespan():
        pass
    assert order == ["load", "lifespan"]
