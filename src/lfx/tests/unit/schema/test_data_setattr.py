from lfx.schema.data import JSON
from pydantic import Field


class TestDataSetAttrPropertyDescriptor:
    def test_property_setter_intercepted(self):
        """A subclass @property with setter should be routed through by __setattr__."""

        class MyData(JSON):
            _backing: str = ""
            items: list[str] = Field(default_factory=list)

            @property
            def computed(self):
                return self._backing.upper()

            @computed.setter
            def computed(self, value):
                object.__setattr__(self, "_backing", str(value))

        d = MyData()
        d.computed = "hello"
        assert d.computed == "HELLO"
        # Should NOT end up in data dict since property handled it
        assert "computed" not in d.data

    def test_regular_field_still_works(self):
        class MyData(JSON):
            name: str = ""

        d = MyData()
        d.name = "test"
        assert d.name == "test"
        assert d.data["name"] == "test"

    def test_dynamic_attribute_still_works(self):
        d = JSON()
        d.some_key = "value"
        assert d.data["some_key"] == "value"

    def test_private_attribute_still_works(self):
        d = JSON()
        d._private = "secret"
        assert "_private" not in d.data

    def test_property_without_setter_not_intercepted(self):
        """Read-only properties should not intercept writes."""

        class MyData(JSON):
            @property
            def readonly(self):
                return "fixed"

        d = MyData()
        d.readonly = "attempt"
        # Should go to data dict since property has no setter
        assert d.data["readonly"] == "attempt"

    def test_non_property_descriptor_not_intercepted(self):
        """Non-property class attributes should not trigger the property path."""
        from typing import ClassVar

        class MyData(JSON):
            class_var: ClassVar[str] = "hello"

        d = MyData()
        d.class_var = "world"
        # Should go through normal path
        assert d.data["class_var"] == "world"
