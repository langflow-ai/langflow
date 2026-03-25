import time

from langflow.services.flow_events.service import FlowEventsService


def test_append_and_get_events():
    svc = FlowEventsService()
    svc.append("flow-1", "component_added", "Added OpenAI")
    svc.append("flow-1", "connection_added", "Connected to Chat Output")

    events, settled = svc.get_since("flow-1", 0.0)
    assert len(events) == 2
    assert events[0].type == "component_added"
    assert events[1].type == "connection_added"
    assert not settled


def test_get_since_filters_by_timestamp():
    svc = FlowEventsService()
    e1 = svc.append("flow-1", "component_added", "First")
    svc.append("flow-1", "component_added", "Second")

    events, _ = svc.get_since("flow-1", e1.timestamp)
    assert len(events) == 1
    assert events[0].summary == "Second"


def test_settled_on_flow_settled_event():
    svc = FlowEventsService()
    svc.append("flow-1", "component_added", "Added something")
    svc.append("flow-1", "flow_settled", "Done")

    events, settled = svc.get_since("flow-1", 0.0)
    assert settled is True
    assert any(e.type == "flow_settled" for e in events)


def test_settled_on_timeout():
    svc = FlowEventsService()
    svc.SETTLE_TIMEOUT = 0.1
    svc.append("flow-1", "component_added", "Added something")

    time.sleep(0.15)

    _, settled = svc.get_since("flow-1", 0.0)
    assert settled is True


def test_empty_flow_returns_settled():
    svc = FlowEventsService()
    events, settled = svc.get_since("nonexistent", 0.0)
    assert events == []
    assert settled is True


def test_ttl_cleanup():
    svc = FlowEventsService()
    svc.TTL_SECONDS = 0.1
    svc.append("flow-1", "component_added", "Old event")

    time.sleep(0.15)

    events, _ = svc.get_since("flow-1", 0.0)
    assert len(events) == 0


def test_different_flows_isolated():
    svc = FlowEventsService()
    svc.append("flow-1", "component_added", "Flow 1")
    svc.append("flow-2", "connection_added", "Flow 2")

    events_1, _ = svc.get_since("flow-1", 0.0)
    events_2, _ = svc.get_since("flow-2", 0.0)

    assert len(events_1) == 1
    assert events_1[0].summary == "Flow 1"
    assert len(events_2) == 1
    assert events_2[0].summary == "Flow 2"
