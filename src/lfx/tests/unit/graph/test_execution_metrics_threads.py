"""Scope publication is synchronized without locking builds or metadata capture."""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from lfx.components.input_output import ChatInput, ChatOutput
from lfx.graph import Graph
from lfx.graph import metrics as module


def target():
    source = ChatInput(_id="source").set(input_value="hello", should_store_message=False)
    sink = ChatOutput(_id="sink").set(input_value=source.message_response, should_store_message=False)
    return Graph(source, sink)


def wait(event):
    assert event.wait(5), "thread synchronization timed out"


@pytest.mark.parametrize("same_scope", [False, True])
def test_concurrent_publication_has_exactly_one_owner(same_scope):
    graph = target()
    scope = graph.collect_execution_metrics() if same_scope else None
    constructors = threading.Barrier(2)
    loser_finished = threading.Event()
    real = module.ExecutionMetrics

    def construct(graph):
        constructors.wait(timeout=5)
        return real(graph)

    async def contender():
        current = scope if same_scope else graph.collect_execution_metrics()
        try:
            report = current.__enter__()
        except RuntimeError as exc:
            assert "already active" in str(exc)  # noqa: PT017 - either contender may win
            loser_finished.set()
            return "rejected"
        try:
            wait(loser_finished)
            assert graph._execution_metrics is report
            assert report.snapshot()["nodes"] == {}
        finally:
            current.__exit__(None, None, None)
        return "owner"

    with patch.object(module, "ExecutionMetrics", construct), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(asyncio.run, contender()) for _ in range(2)]
        assert sorted(f.result(timeout=10) for f in futures) == ["owner", "rejected"]
    assert graph._execution_metrics is None


def test_unrelated_graph_entry_does_not_wait_for_constructor():
    first, second = target(), target()
    constructing, other_done = threading.Event(), threading.Event()
    real = module.ExecutionMetrics

    def construct(graph):
        if graph is first:
            constructing.set()
            wait(other_done)
        return real(graph)

    async def enter(graph):
        with graph.collect_execution_metrics():
            pass

    def other():
        wait(constructing)
        try:
            asyncio.run(enter(second))
        finally:
            other_done.set()

    with patch.object(module, "ExecutionMetrics", construct), ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(asyncio.run, enter(first)), pool.submit(other)]
        for future in futures:
            future.result(timeout=10)


async def test_reentrant_constructor_cannot_overwrite_inner_scope():
    graph = target()
    inner = graph.collect_execution_metrics()
    real = module.ExecutionMetrics
    constructing = False
    inner_report = None

    def construct(graph):
        nonlocal constructing, inner_report
        if not constructing:
            constructing = True
            inner_report = inner.__enter__()
        return real(graph)

    with (
        patch.object(module, "ExecutionMetrics", construct),
        pytest.raises(RuntimeError, match="already active"),
        graph.collect_execution_metrics(),
    ):
        pass
    assert graph._execution_metrics is inner_report
    inner.__exit__(None, None, None)
    assert graph._execution_metrics is None


async def test_constructor_failure_leaves_scope_reusable():
    graph = target()
    scope = graph.collect_execution_metrics()
    failure = SystemExit("constructor")
    with patch.object(module, "ExecutionMetrics", side_effect=failure), pytest.raises(SystemExit) as caught:
        scope.__enter__()
    assert caught.value is failure
    assert graph._execution_metrics is None
    assert scope._recorder is None
    with scope:
        pass


@pytest.mark.parametrize("after_assignment", [False, True])
async def test_publication_failure_rolls_back_before_reraise(after_assignment):
    failure = KeyboardInterrupt("publication")

    class FailingGraph(SimpleNamespace):
        fail = True

        def __setattr__(self, name, value):
            if name == "_execution_metrics" and value is not None and self.fail:
                if after_assignment:
                    super().__setattr__(name, value)
                raise failure
            super().__setattr__(name, value)

    graph = FailingGraph(vertices=[], flow_id=None, flow_name=None)
    scope = module.collect_execution_metrics(graph)
    with pytest.raises(KeyboardInterrupt) as caught:
        scope.__enter__()
    assert caught.value is failure
    assert getattr(graph, "_execution_metrics", None) is None
    assert scope._recorder is None
    graph.fail = False
    with scope:
        pass


async def test_exit_cannot_clear_a_replaced_private_attachment():
    graph = target()
    scope = graph.collect_execution_metrics()
    recorder = scope.__enter__()
    replacement = object()
    # Private-field interference is not supported use; cleanup must still not
    # erase an attachment it does not own.
    graph._execution_metrics = replacement
    scope.__exit__(None, None, None)
    assert graph._execution_metrics is replacement
    assert not recorder._active
    graph._execution_metrics = None


async def test_entry_remains_rejected_until_finalization_finishes():
    graph = target()
    scope = graph.collect_execution_metrics()
    recorder = scope.__enter__()
    real_close = recorder._close

    def close(**kwargs):
        with pytest.raises(RuntimeError, match="already active"), graph.collect_execution_metrics():
            pass
        real_close(**kwargs)

    with patch.object(recorder, "_close", close):
        scope.__exit__(None, None, None)
    with graph.collect_execution_metrics():
        pass


def test_natural_concurrent_entries_do_not_overlap():
    graph = target()
    active = 0
    count_lock = threading.Lock()

    async def repeat():
        nonlocal active
        for _ in range(50):
            scope = graph.collect_execution_metrics()
            try:
                scope.__enter__()
            except RuntimeError as exc:
                assert "already active" in str(exc)  # noqa: PT017 - either contender may win
                continue
            try:
                with count_lock:
                    active += 1
                    assert active == 1
                await asyncio.sleep(0)
                with count_lock:
                    active -= 1
            finally:
                scope.__exit__(None, None, None)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(asyncio.run, repeat()) for _ in range(4)]
        for future in futures:
            future.result(timeout=10)
    assert active == 0
    assert graph._execution_metrics is None


@pytest.mark.parametrize("without_lock", [False, True])
def test_attachment_check_and_publication_are_atomic(monkeypatch, without_lock):
    """A competing owner cannot inspect a half-published attachment."""
    inside, release, contender_started = threading.Event(), threading.Event(), threading.Event()
    foreign_read = threading.Event()
    loser_finished = threading.Event()
    holder_id = None

    class PublicationGraph:
        vertices = ()
        flow_id = None
        flow_name = None
        attached = None

        @property
        def _execution_metrics(self):
            if inside.is_set() and not release.is_set() and threading.get_ident() != holder_id:
                foreign_read.set()
            return self.attached

        @_execution_metrics.setter
        def _execution_metrics(self, value):
            if value is not None and threading.get_ident() == holder_id:
                inside.set()
                wait(release)
            self.attached = value

    graph = PublicationGraph()
    if without_lock:
        monkeypatch.setattr(module, "_attachment_lock", nullcontext())

    async def enter(holder):
        nonlocal holder_id
        if holder:
            holder_id = threading.get_ident()
        else:
            contender_started.set()
        scope = module.collect_execution_metrics(graph)
        try:
            scope.__enter__()
        except RuntimeError as exc:
            assert "already active" in str(exc)  # noqa: PT017 - contender outcome
            loser_finished.set()
            return "rejected"
        try:
            if holder:
                wait(loser_finished)
            else:
                loser_finished.set()
        finally:
            scope.__exit__(None, None, None)
        return "owner"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(asyncio.run, enter(holder=True))
        try:
            wait(inside)
            second = pool.submit(asyncio.run, enter(holder=False))
            wait(contender_started)
            violated = foreign_read.wait(0.5)
        finally:
            release.set()
        outcomes = sorted([first.result(timeout=10), second.result(timeout=10)])
    assert outcomes == (["owner", "owner"] if without_lock else ["owner", "rejected"])
    assert violated is without_lock
    assert graph._execution_metrics is None
