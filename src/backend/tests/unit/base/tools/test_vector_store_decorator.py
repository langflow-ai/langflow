from typing import Any

import pytest
from langflow.components.vectorstores import AstraDBVectorStoreComponent

from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping


class TestVectorStoreDecorator(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self) -> type[Any]:
        """Return the component class to test."""
        return AstraDBVectorStoreComponent

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        """Return the file names mapping for different versions."""
        return []

    def test_decorator_applied(self, component_class):
        component: AstraDBVectorStoreComponent = component_class()
        assert hasattr(component, "decorated")
        assert component.decorated
