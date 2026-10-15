"""Regression tests for ``CustomComponent.get_full_path`` without a storage service.

``get_storage_service`` returns ``None`` in a standalone ``lfx`` run (only ``langflow``
registers a ``StorageServiceFactory``), and unlike the S3 helpers in
``lfx.base.data.storage_utils`` this path is *not* gated on ``storage_type`` -- it runs under
the default ``storage_type="local"``. There is no storage root to build against, so the key is
already the path the caller should see, exactly as ``ParameterHandler._resolve_storage_key``
decided for the vertex parameter boundary.

It used to dereference the missing service and raise ``AttributeError``, which both call
sites (``BaseFileComponent._validate_and_resolve_paths`` and ``FileComponent``'s tool-mode
branch) caught and retried as a plain local path -- landing on the same value, via an
exception broad enough to hide any genuine ``AttributeError`` raised underneath it.
"""

from unittest.mock import Mock, patch

import pytest
from lfx.custom.custom_component.custom_component import CustomComponent
from lfx.utils.file_path_security import StorageNamespaceError

MODULE = "lfx.custom.custom_component.custom_component"


def _component(*, user_id: str | None = "user-1", flow_id: str | None = "flow-1") -> CustomComponent:
    """A component bound to a graph, which is what supplies the storage scopes."""
    component = CustomComponent()
    graph = Mock()
    graph.user_id = user_id
    graph.flow_id = flow_id
    graph.source_flow_id = None
    vertex = Mock()
    vertex.graph = graph
    component._vertex = vertex
    return component


class TestWithoutStorageService:
    def test_returns_the_storage_key_instead_of_raising_attributeerror(self):
        with patch(f"{MODULE}.get_storage_service", return_value=None):
            assert _component().get_full_path("user-1/report.csv") == "user-1/report.csv"

    def test_does_not_raise_attributeerror(self):
        """Pinned separately: the callers catch ``AttributeError``, so a regression is silent."""
        with patch(f"{MODULE}.get_storage_service", return_value=None):
            try:
                _component().get_full_path("flow-1/report.csv")
            except AttributeError as exc:  # pragma: no cover - only runs on regression
                pytest.fail(f"get_full_path raised AttributeError: {exc}")

    def test_still_rejects_a_file_name_carrying_path_separators(self):
        """``validate_storage_key`` accepts exactly ``"<namespace>/<file_name>"``."""
        with (
            patch(f"{MODULE}.get_storage_service", return_value=None),
            pytest.raises(StorageNamespaceError),
        ):
            _component().get_full_path("user-1/sub/report.csv")

    def test_still_denies_a_namespace_outside_the_graph_scopes(self):
        """Skipping *resolution* must never skip *containment*."""
        with (
            patch(f"{MODULE}.get_storage_service", return_value=None),
            pytest.raises(StorageNamespaceError),
        ):
            _component().get_full_path("someone-else/report.csv")

    def test_still_rejects_a_malformed_key(self):
        with (
            patch(f"{MODULE}.get_storage_service", return_value=None),
            pytest.raises(StorageNamespaceError),
        ):
            _component().get_full_path("no-namespace.csv")


class TestWithStorageService:
    """The langflow path is unchanged: the service still owns resolution."""

    def test_resolves_through_build_full_path(self):
        storage = Mock()
        storage.build_full_path.return_value = "/data/user-1/report.csv"
        with patch(f"{MODULE}.get_storage_service", return_value=storage):
            assert _component().get_full_path("user-1/report.csv") == "/data/user-1/report.csv"
        storage.build_full_path.assert_called_once_with("user-1", "report.csv")

    def test_denies_out_of_scope_namespace_before_touching_the_service(self):
        storage = Mock()
        with (
            patch(f"{MODULE}.get_storage_service", return_value=storage),
            pytest.raises(StorageNamespaceError),
        ):
            _component().get_full_path("someone-else/report.csv")
        storage.build_full_path.assert_not_called()
