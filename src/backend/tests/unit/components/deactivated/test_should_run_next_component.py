import pytest
from langflow.components.deactivated.should_run_next import ShouldRunNextComponent
from tests.base import ComponentTestBaseWithClient


@pytest.mark.usefixtures("client")
class TestShouldRunNextComponent(ComponentTestBaseWithClient):
    @pytest.fixture
    def component_class(self):
        return ShouldRunNextComponent

    @pytest.fixture
    def default_kwargs(self):
        return {"question": "Is this a test?", "context": "This is a context.", "retries": 3}

    @pytest.fixture
    def file_names_mapping(self):
        return [
            {"version": "1.0.0", "module": "should_run_next", "file_name": "ShouldRunNext"},
        ]

    async def test_build_should_run_next(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        result = await component.build(llm=Mock(), **default_kwargs)
        assert result == default_kwargs["context"], "The context should be returned as is."

    async def test_should_run_next_condition_yes(self, component_class, default_kwargs):
        mock_llm = Mock()
        mock_llm.invoke.return_value = "yes"
        component = component_class(**default_kwargs)
        result = await component.build(llm=mock_llm, **default_kwargs)
        assert component.status == "Should Run Next: True", (
            "The status should indicate that the next component should run."
        )

    async def test_should_run_next_condition_no(self, component_class, default_kwargs):
        mock_llm = Mock()
        mock_llm.invoke.return_value = "no"
        component = component_class(**default_kwargs)
        result = await component.build(llm=mock_llm, **default_kwargs)
        assert component.status == "Should Run Next: False", (
            "The status should indicate that the next component should not run."
        )
        assert component.stop_called, "The stop method should be called when the condition is false."
