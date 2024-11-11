from typing import Any

import pytest

from tests.constants import SUPPORTED_VERSIONS
from tests.integration.utils import build_component_instance_for_tests

# Sentinel value to mark undefined test cases
DID_NOT_EXIST = object()


class ComponentTestBase:
    component_class = None
    DEFAULT_KWARGS: dict[str, Any] = {}
    FILE_NAMES_MAPPING: dict[str, object | str] = {}

    def test_all_versions_have_a_file_name_defined(self):
        for version in SUPPORTED_VERSIONS:
            assert version in self.FILE_NAMES_MAPPING
            assert self.FILE_NAMES_MAPPING[version] is not None

    def test_component_versions(self):
        """Test if the component works across different versions."""
        for version, file_name in self.FILE_NAMES_MAPPING.items():
            if file_name is DID_NOT_EXIST:
                continue

            instance = build_component_instance_for_tests(version, file_name=file_name, **self.DEFAULT_KWARGS)
            result = instance()
            assert result is not None, f"{self.component_class.__name__} failed to execute in version {version}"


@pytest.mark.usefixtures("client")
class ComponentTestBaseWithClient:
    pass


class ComponentTestBaseWithoutClient:
    pass
