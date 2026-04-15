"""Tests for InMemoryStateService."""

from langflow.services.state.service import InMemoryStateService


class _FakeSettings:
    """Minimal stand-in for SettingsService (only stored, never called)."""


def _create_service():
    """Create an InMemoryStateService with a fake settings service."""
    return InMemoryStateService(settings_service=_FakeSettings())


def _make_observer():
    """Return a callable observer that records every call it receives."""
    calls = []

    def observer(key, value, *, append=False):
        calls.append((key, value, append))

    return calls, observer


def _make_failing_observer():
    """Return an observer that raises an exception when called."""

    def observer(_key, _value, *, append=False):  # noqa: ARG001
        msg = "observer error"
        raise RuntimeError(msg)

    return observer


class TestStateServiceGetUpdateState:
    """Tests for get_state and update_state."""

    def test_get_state_empty(self):
        service = _create_service()
        result = service.get_state("key1", run_id="run1")
        assert result == ""

    def test_update_and_get_state(self):
        service = _create_service()
        service.update_state("key1", "value1", run_id="run1")
        result = service.get_state("key1", run_id="run1")
        assert result == "value1"

    def test_update_state_overwrites(self):
        service = _create_service()
        service.update_state("key1", "value1", run_id="run1")
        service.update_state("key1", "value2", run_id="run1")
        result = service.get_state("key1", run_id="run1")
        assert result == "value2"

    def test_separate_run_ids(self):
        service = _create_service()
        service.update_state("key1", "value1", run_id="run1")
        service.update_state("key1", "value2", run_id="run2")
        assert service.get_state("key1", run_id="run1") == "value1"
        assert service.get_state("key1", run_id="run2") == "value2"

    def test_separate_keys(self):
        service = _create_service()
        service.update_state("key1", "value1", run_id="run1")
        service.update_state("key2", "value2", run_id="run1")
        assert service.get_state("key1", run_id="run1") == "value1"
        assert service.get_state("key2", run_id="run1") == "value2"

    def test_get_state_nonexistent_run_id(self):
        service = _create_service()
        result = service.get_state("key1", run_id="nonexistent")
        assert result == ""

    def test_update_state_various_types(self):
        service = _create_service()
        service.update_state("int_key", 42, run_id="run1")
        service.update_state("list_key", [1, 2, 3], run_id="run1")
        service.update_state("dict_key", {"a": 1}, run_id="run1")
        assert service.get_state("int_key", run_id="run1") == 42
        assert service.get_state("list_key", run_id="run1") == [1, 2, 3]
        assert service.get_state("dict_key", run_id="run1") == {"a": 1}


class TestStateServiceAppendState:
    """Tests for append_state."""

    def test_append_state_creates_list(self):
        service = _create_service()
        service.append_state("key1", "value1", run_id="run1")
        result = service.get_state("key1", run_id="run1")
        assert result == ["value1"]

    def test_append_state_adds_to_list(self):
        service = _create_service()
        service.append_state("key1", "value1", run_id="run1")
        service.append_state("key1", "value2", run_id="run1")
        result = service.get_state("key1", run_id="run1")
        assert result == ["value1", "value2"]

    def test_append_converts_non_list_to_list(self):
        service = _create_service()
        service.update_state("key1", "single_value", run_id="run1")
        service.append_state("key1", "appended", run_id="run1")
        result = service.get_state("key1", run_id="run1")
        assert result == ["single_value", "appended"]

    def test_append_state_separate_run_ids(self):
        service = _create_service()
        service.append_state("key1", "v1", run_id="run1")
        service.append_state("key1", "v2", run_id="run2")
        assert service.get_state("key1", run_id="run1") == ["v1"]
        assert service.get_state("key1", run_id="run2") == ["v2"]


class TestStateServiceObservers:
    """Tests for subscribe/unsubscribe/notify."""

    def test_subscribe_and_notify(self):
        service = _create_service()
        calls, observer = _make_observer()
        service.subscribe("key1", observer)
        service.update_state("key1", "new_value", run_id="run1")
        assert len(calls) == 1
        assert calls[0] == ("key1", "new_value", False)

    def test_multiple_observers(self):
        service = _create_service()
        calls1, observer1 = _make_observer()
        calls2, observer2 = _make_observer()
        service.subscribe("key1", observer1)
        service.subscribe("key1", observer2)
        service.update_state("key1", "value", run_id="run1")
        assert len(calls1) == 1
        assert calls1[0] == ("key1", "value", False)
        assert len(calls2) == 1
        assert calls2[0] == ("key1", "value", False)

    def test_unsubscribe(self):
        service = _create_service()
        calls, observer = _make_observer()
        service.subscribe("key1", observer)
        service.unsubscribe("key1", observer)
        service.update_state("key1", "value", run_id="run1")
        assert len(calls) == 0

    def test_subscribe_duplicate_ignored(self):
        service = _create_service()
        calls, observer = _make_observer()
        service.subscribe("key1", observer)
        service.subscribe("key1", observer)  # Duplicate
        service.update_state("key1", "value", run_id="run1")
        # Should be called only once
        assert len(calls) == 1

    def test_unsubscribe_nonexistent(self):
        service = _create_service()
        _, observer = _make_observer()
        # Should not raise
        service.unsubscribe("key1", observer)

    def test_append_notifies_with_append_true(self):
        service = _create_service()
        calls, observer = _make_observer()
        service.subscribe("key1", observer)
        service.append_state("key1", "appended", run_id="run1")
        assert len(calls) == 1
        assert calls[0] == ("key1", "appended", True)

    def test_notify_append_handles_observer_exception(self):
        service = _create_service()
        bad_observer = _make_failing_observer()
        service.subscribe("key1", bad_observer)
        # Should not raise even when observer fails
        service.append_state("key1", "value", run_id="run1")

    def test_observers_for_different_keys(self):
        service = _create_service()
        calls1, observer1 = _make_observer()
        calls2, observer2 = _make_observer()
        service.subscribe("key1", observer1)
        service.subscribe("key2", observer2)
        service.update_state("key1", "v1", run_id="run1")
        assert len(calls1) == 1
        assert len(calls2) == 0
