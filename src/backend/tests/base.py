from tests.constants import SUPPORTED_VERSIONS

# Sentinel value to mark undefined test cases
DID_NOT_EXIST = object()


class ComponentTestBase:
    FILE_NAMES_MAPPING: dict[str, object | str] = {}

    def test_all_versions_have_a_file_name_defined(self):
        for version in SUPPORTED_VERSIONS:
            assert version in self.FILE_NAMES_MAPPING
            assert self.FILE_NAMES_MAPPING[version] is not None
