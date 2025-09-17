from textwrap import dedent

from lfx.custom.validate import create_class


def test_importing_langflow_module_in_lfx():
    code = dedent("""from langflow.custom import   Component
class TestComponent(Component):
    def some_method(self):
        pass
    """)
    result = create_class(code, "TestComponent")
    assert result.__name__ == "TestComponent"
