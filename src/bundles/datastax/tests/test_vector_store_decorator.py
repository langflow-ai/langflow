from lfx_datastax import AstraDBVectorStoreComponent


class TestVectorStoreDecorator:
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

    def test_decorator_applied(self):
        component = AstraDBVectorStoreComponent()
        assert hasattr(component, "decorated")
        assert component.decorated
