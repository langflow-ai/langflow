"""Full graph text is shared only while its response/checkpoint consumers live."""

from __future__ import annotations

import asyncio
import gc
import hashlib
import threading
import time
import weakref
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langflow.services.flow_multiplayer import checkpoint, reads, writes
from langflow.services.flow_multiplayer.cache import FlowCache, FlowEntry
from langflow.services.flow_multiplayer.serialization_response import (
    SerializationResponseMiddleware,
    hold_for_response,
)
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.responses import Response
from starlette.routing import Route


class Text(str):
    __slots__ = ("__weakref__",)


class Snapshot:
    def __init__(self, state, value):
        self.state = state
        self.value = value

    def to_json(self):
        self.state.started[self.value].set()
        if not self.state.gates[self.value].wait(5):
            message = "serialization test gate timed out"
            raise RuntimeError(message)
        if self.state.fail:
            message = "serialization failed"
            raise ValueError(message)
        text = Text('{"payload":"' + "x" * self.state.size + '","value":' + str(self.value) + "}")
        self.state.outputs.append(weakref.ref(text))
        self.state.finished[self.value].set()
        return text


class State:
    def __init__(self, *, blocked=False, size=128):
        self.value = 0
        self.calls = 0
        self.size = size
        self.fail = False
        self.outputs = []
        self.gates = [threading.Event(), threading.Event()]
        self.started = [threading.Event(), threading.Event()]
        self.finished = [threading.Event(), threading.Event()]
        if not blocked:
            for gate in self.gates:
                gate.set()

    def snapshot(self):
        self.calls += 1
        return Snapshot(self, self.value)

    def replay(self, _operations):
        self.value = 1

    def keep(self):
        self.value = 1


def entry_for(state=None):
    return FlowEntry(uuid4(), state or State(), 0)


async def event(event):
    assert await asyncio.to_thread(event.wait, 5)


async def settle(predicate):
    async with asyncio.timeout(5):
        while not predicate():  # noqa: ASYNC110 -- observe real worker callbacks without production test hooks
            await asyncio.sleep(0.001)
    await asyncio.sleep(0)
    gc.collect()


async def test_completed_text_is_shared_until_last_consumer_then_released():
    entry = entry_for()
    first = await entry.serialized()
    reference = weakref.ref(first.text)
    second = await entry.serialized()
    assert second.text is first.text
    assert first.owns_serialization
    assert not second.owns_serialization
    assert entry.state.calls == 1
    first.close()
    assert reference() is not None
    second.close()
    await settle(lambda: entry._serialization is None)
    assert reference() is None
    third = await entry.serialized()
    assert entry.state.calls == 2
    third.close()


async def test_concurrent_waiters_share_one_real_worker():
    state = State(blocked=True)
    entry = entry_for(state)
    first = asyncio.create_task(entry.serialized())
    await event(state.started[0])
    second = asyncio.create_task(entry.serialized())
    await settle(lambda: entry._serialization.users == 2)
    state.gates[0].set()
    one, two = await asyncio.gather(first, second)
    assert state.calls == 1
    assert one.text is two.text
    one.close()
    two.close()
    assert entry._serialization is None


async def test_cancelled_sole_waiter_does_not_cancel_or_retain_worker_result():
    state = State(blocked=True)
    entry = entry_for(state)
    waiter = asyncio.create_task(entry.serialized())
    await event(state.started[0])
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert entry._serialization.users == 0
    state.gates[0].set()
    await event(state.finished[0])
    await settle(lambda: entry._serialization is None)
    assert state.outputs[0]() is None


async def test_cancelled_one_waiter_preserves_other_consumer():
    state = State(blocked=True)
    entry = entry_for(state)
    first = asyncio.create_task(entry.serialized())
    await event(state.started[0])
    second = asyncio.create_task(entry.serialized())
    await settle(lambda: entry._serialization.users == 2)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    state.gates[0].set()
    lease = await second
    assert state.calls == 1
    assert lease.revision == 0
    lease.close()
    assert entry._serialization is None


async def test_old_completion_cannot_clear_new_revision_task():
    state = State(blocked=True)
    entry = entry_for(state)
    old_waiter = asyncio.create_task(entry.serialized())
    await event(state.started[0])
    await entry.replay([], 1)
    new_waiter = asyncio.create_task(entry.serialized())
    await event(state.started[1])
    current = entry._serialization
    state.gates[0].set()
    old = await old_waiter
    assert old.revision == 0
    assert entry._serialization is current
    assert not current.task.done()
    state.gates[1].set()
    new = await new_waiter
    assert new.revision == 1
    old.close()
    assert entry._serialization is current
    new.close()
    assert entry._serialization is None


async def test_revision_move_before_capture_retries_without_a_stale_snapshot():
    entry = entry_for()
    await entry.use.acquire()
    waiter = asyncio.create_task(entry.serialized())
    await settle(lambda: entry._serialization is not None)
    entry.state.value = entry.revision = 1
    entry.invalidate_serialized()
    entry.use.release()
    lease = await waiter
    assert lease.revision == 1
    assert entry.state.calls == 1
    lease.close()


async def test_keep_detaches_old_text_without_destroying_old_consumers():
    entry = entry_for()
    old = await entry.serialized()
    old_text = weakref.ref(old.text)
    await writes._keep(entry, 1)
    assert entry._serialization is None
    new = await entry.serialized()
    assert old.revision == 0
    assert new.revision == 1
    assert old.text is not new.text
    old.close()
    await settle(lambda: old_text() is None)
    assert entry._serialization is not None
    new.close()


async def test_evicted_entry_text_lives_only_until_active_consumer_finishes():
    entries = FlowCache()
    entry = entry_for()
    entries.put(entry)
    lease = await entry.serialized()
    reference = weakref.ref(lease.text)
    entries.evict(entry.flow_id)
    assert entries.get(entry.flow_id) is None
    del entry
    assert reference() is not None
    lease.close()
    await settle(lambda: reference() is None)


@pytest.mark.parametrize("checkpoint_first", [False, True])
async def test_reads_and_checkpoints_share_finished_text_and_count_cpu_owner(checkpoint_first):
    entry = entry_for()
    if checkpoint_first:
        context = entry.text_and_hash()
        values = await context.__aenter__()
        reader = await entry.serialized()
    else:
        reader = await entry.serialized()
        context = entry.text_and_hash()
        values = await context.__aenter__()
    revision, text, _cpu, owned, digest, _hash_cpu = values
    assert revision == reader.revision == 0
    assert text is reader.text
    assert digest == hashlib.sha256(text.encode()).hexdigest()
    assert owned is checkpoint_first
    assert entry.state.calls == 1
    await context.__aexit__(None, None, None)
    assert entry._serialization is not None
    reader.close()
    assert entry._serialization is None


@pytest.mark.parametrize("outcome", ["success", "failure", "cancel"])
async def test_checkpoint_holds_lease_through_database_store(monkeypatch, outcome):
    entry = entry_for()
    store_entered, allow_store = asyncio.Event(), asyncio.Event()
    checkpoint.reset_for_tests()

    class Session:
        async def commit(self):
            return None

    @asynccontextmanager
    async def session_scope():
        yield Session()

    async def head(*_args, **_kwargs):
        return 0

    async def at_head(*_args, **_kwargs):
        return entry

    async def write(*_args, **_kwargs):
        store_entered.set()
        await allow_store.wait()
        if outcome == "failure":
            message = "store failed"
            raise ValueError(message)
        return True

    async def insert(*_args, **_kwargs):
        return True

    monkeypatch.setattr(checkpoint, "session_scope", session_scope)
    monkeypatch.setattr(checkpoint, "entry_at_head", at_head)
    monkeypatch.setattr(checkpoint.oplog, "read_head", head)
    monkeypatch.setattr(checkpoint.oplog, "checkpoint_flow", write)
    monkeypatch.setattr(checkpoint.oplog, "insert_checkpoint_row", insert)
    monkeypatch.setattr(checkpoint.config, "uses_cache", lambda: True)
    monkeypatch.setattr(checkpoint.config, "write_mode", lambda: "wal")
    checkpoint.CACHE.put(entry)
    try:
        pending = asyncio.create_task(checkpoint._write_checkpoint(entry.flow_id, 0, time.time(), time.perf_counter()))
        await asyncio.wait_for(store_entered.wait(), 5)
        reader = await entry.serialized()
        assert entry.state.calls == 1
        reader.close()
        assert entry._serialization is not None
        if outcome == "cancel":
            pending.cancel()
            with pytest.raises(asyncio.CancelledError):
                await pending
        else:
            allow_store.set()
            if outcome == "failure":
                with pytest.raises(ValueError, match="store failed"):
                    await pending
            else:
                assert await pending == 0
        assert entry._serialization is None
    finally:
        checkpoint.CACHE.evict(entry.flow_id)


def scope(path="/graph"):
    return {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"accept-encoding", b"gzip")],
        "scheme": "http",
        "root_path": "",
        "server": ("test", 80),
        "client": ("test", 1),
        "http_version": "1.1",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
    }


async def receive():
    await asyncio.Event().wait()


async def passthrough(request, call_next):
    return await call_next(request)


@pytest.mark.parametrize("actual_main", [False, True])
async def test_outer_scope_keeps_completed_text_through_gzip_and_basehttp_send(actual_main):
    entry = entry_for(State(size=256_000))
    inner_finished = asyncio.Event()
    sending = [asyncio.Event(), asyncio.Event()]
    finish_send = [asyncio.Event(), asyncio.Event()]

    class Observed(Response):
        async def __call__(self, scope, receive, send):
            try:
                await super().__call__(scope, receive, send)
            finally:
                inner_finished.set()

    async def graph(_request):
        lease = await entry.serialized()
        assert hold_for_response(lease)
        return Observed(lease.text.encode(), media_type="application/json")

    if actual_main:
        from langflow.main import create_app

        app = create_app()
        app.router.routes.insert(0, Route("/graph", graph))
        assert app.user_middleware[0].cls is SerializationResponseMiddleware
    else:
        app = Starlette(routes=[Route("/graph", graph)])
        app.add_middleware(GZipMiddleware, minimum_size=1, compresslevel=6)
        app.add_middleware(BaseHTTPMiddleware, dispatch=passthrough)
        app.add_middleware(BaseHTTPMiddleware, dispatch=passthrough)
        app.add_middleware(SerializationResponseMiddleware)

    def sender(index):
        async def send(message):
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                sending[index].set()
                await finish_send[index].wait()

        return send

    first = asyncio.create_task(app(scope(), receive, sender(0)))
    await asyncio.wait_for(sending[0].wait(), 5)
    if not actual_main:
        # BaseHTTPMiddleware ends the inner response before the outer send ends. The actual app's
        # middleware is plain ASGI, so its inner response ends with the send.
        await asyncio.wait_for(inner_finished.wait(), 5)
    reference = entry.state.outputs[0]
    second = asyncio.create_task(app(scope(), receive, sender(1)))
    await asyncio.wait_for(sending[1].wait(), 5)
    assert entry.state.calls == 1
    assert entry._serialization.users == 2
    finish_send[0].set()
    await first
    assert reference() is not None
    assert entry._serialization.users == 1
    finish_send[1].set()
    await second
    await settle(lambda: reference() is None)
    assert entry._serialization is None


@pytest.mark.parametrize("failure", ["cancel", "send-error"])
async def test_outer_scope_releases_on_cancel_or_failed_send(failure):
    entry = entry_for()
    sending = asyncio.Event()

    async def graph(_request):
        lease = await entry.serialized()
        assert hold_for_response(lease)
        return Response(lease.text.encode())

    app = SerializationResponseMiddleware(Starlette(routes=[Route("/graph", graph)]))

    async def send(message):
        if message["type"] == "http.response.body":
            sending.set()
            if failure == "send-error":
                message = "client disconnected"
                raise OSError(message)
            await asyncio.Event().wait()

    pending = asyncio.create_task(app(scope(), receive, send))
    await asyncio.wait_for(sending.wait(), 5)
    if failure == "cancel":
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    else:
        with pytest.raises(OSError, match="client disconnected"):
            await pending
    await settle(lambda: entry._serialization is None)
    assert entry.state.outputs[0]() is None


async def test_router_only_response_fallback_holds_and_releases_lease():
    entry = entry_for()
    lease = await entry.serialized()
    graph = reads.CurrentGraph(lease.revision, lease.text, lease)
    response = graph.response(graph.text.encode())
    assert graph.lease is None
    entered, finish = asyncio.Event(), asyncio.Event()

    async def send(message):
        if message["type"] == "http.response.body":
            entered.set()
            await finish.wait()

    pending = asyncio.create_task(response(scope(), receive, send))
    await asyncio.wait_for(entered.wait(), 5)
    assert entry._serialization is not None
    finish.set()
    await pending
    assert entry._serialization is None


async def test_late_registration_does_not_attach_to_a_finished_request():
    entry = entry_for()
    inherited = []

    async def inner(_scope, _receive, _send):
        async def late():
            await barrier.wait()
            lease = await entry.serialized()
            try:
                with pytest.raises(RuntimeError, match="scope has already ended"):
                    hold_for_response(lease)
                inherited.append(True)
            finally:
                lease.close()

        tasks.append(asyncio.create_task(late()))

    barrier = asyncio.Event()
    tasks = []
    await SerializationResponseMiddleware(inner)(scope(), receive, lambda _message: None)
    barrier.set()
    await asyncio.gather(*tasks)
    assert inherited == [True]
    assert entry._serialization is None


async def test_cancelled_sole_waiter_retrieves_serialization_errors():
    state = State(blocked=True)
    state.fail = True
    entry = entry_for(state)
    loop = asyncio.get_running_loop()
    previous = loop.get_exception_handler()
    unhandled = []
    loop.set_exception_handler(lambda _loop, context: unhandled.append(context))
    try:
        pending = asyncio.create_task(entry.serialized())
        await event(state.started[0])
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
        state.gates[0].set()
        await settle(lambda: entry._serialization is None)
        assert unhandled == []
    finally:
        loop.set_exception_handler(previous)


@pytest.mark.parametrize("fail_build", [False, True])
async def test_non_owner_response_redacts_without_losing_its_lease(monkeypatch, fail_build):
    from langflow.api.v2 import flows

    entry = entry_for()
    user = SimpleNamespace(id=uuid4())

    @asynccontextmanager
    async def session_scope():
        yield object()

    async def header(*_args):
        return SimpleNamespace(user_id=uuid4())

    async def join(*_args):
        lease = await entry.serialized()
        return reads.CurrentGraph(lease.revision, lease.text, lease)

    def redact(_text):
        if fail_build:
            message = "redaction failed"
            raise ValueError(message)
        return '{"redacted":true}'

    monkeypatch.setattr(flows, "session_scope", session_scope)
    monkeypatch.setattr(flows, "multiplayer_available", lambda _session: True)
    monkeypatch.setattr(flows, "load_flow_header", header)
    monkeypatch.setattr(flows.reads, "join_graph", join)
    monkeypatch.setattr(flows, "_strip_secrets", redact)
    if fail_build:
        with pytest.raises(ValueError, match="redaction failed"):
            await flows.join_flow(entry.flow_id, user)
        assert entry._serialization is None
    else:
        response = await flows.join_flow(entry.flow_id, user)
        assert response.body == b'{"revision":0,"data":{"redacted":true}}'
        assert entry._serialization is not None

        async def send(_message):
            return None

        await response(scope(), receive, send)
        assert entry._serialization is None


def test_actual_app_registers_release_scope_outside_gzip():
    from langflow.main import create_app

    app = create_app()
    assert app.user_middleware[0].cls is SerializationResponseMiddleware
    assert any(middleware.cls is GZipMiddleware for middleware in app.user_middleware)
    # Every request middleware is plain ASGI: none ends a response before its send ends.
    assert not any(middleware.cls is BaseHTTPMiddleware for middleware in app.user_middleware)
