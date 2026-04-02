"""Tests for InMemoryStateService."""

from unittest.mock import MagicMock, call

from langflow.services.state.service import InMemoryStateService


def _create_service():
    """Create an InMemoryStateService with a mock settings service."""
    mock_settings = MagicMock()
    return InMemoryStateService(settings_service=mock_settings)


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
        observer = MagicMock()
        service.subscribe("key1", observer)
        service.update_state("key1", "new_value", run_id="run1")
        observer.assert_called_once_with("key1", "new_value", append=False)

    def test_multiple_observers(self):
        service = _create_service()
        observer1 = MagicMock()
        observer2 = MagicMock()
        service.subscribe("key1", observer1)
        service.subscribe("key1", observer2)
        service.update_state("key1", "value", run_id="run1")
        observer1.assert_called_once_with("key1", "value", append=False)
        observer2.assert_called_once_with("key1", "value", append=False)

    def test_unsubscribe(self):
        service = _create_service()
        observer = MagicMock()
        service.subscribe("key1", observer)
        service.unsubscribe("key1", observer)
        service.update_state("key1", "value", run_id="run1")
        observer.assert_not_called()

    def test_subscribe_duplicate_ignored(self):
        service = _create_service()
        observer = MagicMock()
        service.subscribe("key1", observer)
        service.subscribe("key1", observer)  # Duplicate
        service.update_state("key1", "value", run_id="run1")
        # Should be called only once
        observer.assert_called_once()

    def test_unsubscribe_nonexistent(self):
        service = _create_service()
        observer = MagicMock()
        # Should not raise
        service.unsubscribe("key1", observer)

    def test_append_notifies_with_append_true(self):
        service = _create_service()
        observer = MagicMock()
        service.subscribe("key1", observer)
        service.append_state("key1", "appended", run_id="run1")
        observer.assert_called_once_with("key1", "appended", append=True)

    def test_notify_append_handles_observer_exception(self):
        service = _create_service()
        bad_observer = MagicMock(side_effect=Exception("observer error"))
        service.subscribe("key1", bad_observer)
        # Should not raise even when observer fails
        service.append_state("key1", "value", run_id="run1")

    def test_observers_for_different_keys(self):
        service = _create_service()
        observer1 = MagicMock()
        observer2 = MagicMock()
        service.subscribe("key1", observer1)
        service.subscribe("key2", observer2)
        service.update_state("key1", "v1", run_id="run1")
        observer1.assert_called_once()
        observer2.assert_not_called()
