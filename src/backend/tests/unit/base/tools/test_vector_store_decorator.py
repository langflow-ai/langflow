from typing import Any

import pytest

from lfx.components.vectorstores import AstraDBVectorStoreComponent
from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestVectorStoreDecorator(ComponentTestBaseWithoutClient):
    """Unit tests for the AstraDBVectorStoreComponent decorator.

    This test class inherits from ComponentTestBaseWithoutClient and includes
    the following tests and fixtures:

    Fixtures:
        - component_class: Returns the AstraDBVectorStoreComponent class to be tested.
        - file_names_mapping: Returns an empty list representing the file names mapping for different versions.
    Tests:
        - test_decorator_applied: Verifies that the AstraDBVectorStoreComponent has the 'decorated' attribute and that
        it is set to True.
    """

    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return AstraDBVectorStoreComponent

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    def test_decorator_applied(self, component_class: type[Any]):
        component: AstraDBVectorStoreComponent = component_class()
        assert hasattr(component, "decorated")
        assert component.decorated
