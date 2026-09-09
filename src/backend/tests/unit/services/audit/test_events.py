"""Event names are a public contract: released names never change."""

import pytest
from langflow.services.audit import events

# Frozen on purpose. Changing a name here means changing it for every operator
# whose pipeline filters on it, so this list is the review gate for that.
RELEASED = {
    "langflow.audit.flow.created",
    "langflow.audit.flow.updated",
    "langflow.audit.flow.deleted",
    "langflow.audit.flow.restored",
    "langflow.audit.flow.save.denied",
    "langflow.audit.flow.permission.denied",
    "langflow.audit.flow.run.succeeded",
    "langflow.audit.flow.run.failed",
}


def test_no_released_event_name_has_changed():
    assert events.PUBLISHED_EVENTS == RELEASED


def test_every_name_is_prefixed_so_pipelines_can_filter_on_it():
    assert all(name.startswith("langflow.audit.") for name in events.PUBLISHED_EVENTS)


@pytest.mark.parametrize("event", sorted(RELEASED))
def test_the_third_segment_is_the_resource_type(event):
    assert events.resource_type_of(event) == event.split(".")[2]


def test_a_malformed_name_is_rejected_rather_than_silently_misparsed():
    with pytest.raises(ValueError, match="malformed audit event name"):
        events.resource_type_of("flow.updated")
