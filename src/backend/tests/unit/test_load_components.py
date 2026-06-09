# ruff: noqa: T201
import asyncio

import pytest
from lfx.constants import BASE_COMPONENTS_PATH
from lfx.interface.components import aget_all_types_dict, import_langflow_components


class TestComponentLoading:
    """Test suite for component loading methods."""

    @pytest.fixture
    def base_components_path(self):
        """Fixture to provide BASE_COMPONENTS_PATH as a list."""
        return [BASE_COMPONENTS_PATH] if BASE_COMPONENTS_PATH else []

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_import_langflow_components_basic(self):
        """Test basic functionality of import_langflow_components."""
        result = await import_langflow_components()

        assert isinstance(result, dict), "Result should be a dictionary"
        assert "components" in result, "Result should have 'components' key"
        assert isinstance(result["components"], dict), "Components should be a dictionary"

        total_components = sum(len(comps) for comps in result["components"].values())
        print(f"Loaded {total_components} components")

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_aget_all_types_dict_basic(self, base_components_path):
        """Test basic functionality of aget_all_types_dict."""
        result = await aget_all_types_dict(base_components_path)

        assert isinstance(result, dict), "Result should be a dictionary"

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_component_template_structure(self):
        """Test that component templates have expected structure."""
        langflow_result = await import_langflow_components()

        for category, components in langflow_result["components"].items():
            assert isinstance(components, dict), f"Category {category} should contain dict of components"

            for comp_name, comp_template in components.items():
                assert isinstance(comp_template, dict), f"Component {comp_name} should be a dict"

                if comp_template:
                    expected_fields = {"display_name", "type", "template"}
                    present_fields = set(comp_template.keys())

                    common_fields = expected_fields.intersection(present_fields)
                    if len(common_fields) == 0 and comp_template:
                        print(f"Warning: Component {comp_name} missing expected fields. Has: {list(present_fields)}")

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_concurrent_loading(self, base_components_path):
        """Test concurrent execution of both loading methods."""
        tasks = [
            import_langflow_components(),
            aget_all_types_dict(base_components_path),
            import_langflow_components(),
        ]

        results = await asyncio.gather(*tasks)

        langflow_result1, all_types_result, langflow_result2 = results

        assert isinstance(langflow_result1, dict)
        assert isinstance(langflow_result2, dict)
        assert isinstance(all_types_result, dict)

        assert "components" in langflow_result1
        assert "components" in langflow_result2

        categories1 = set(langflow_result1["components"].keys())
        categories2 = set(langflow_result2["components"].keys())

        for category in categories1.intersection(categories2):
            comps1 = set(langflow_result1["components"][category].keys())
            comps2 = set(langflow_result2["components"][category].keys())
            if comps1 != comps2:
                missing_in_2 = comps1 - comps2
                missing_in_1 = comps2 - comps1
                print(
                    f"Component differences in {category}: "
                    f"missing in result2: {missing_in_2}, missing in result1: {missing_in_1}"
                )

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in both loading methods."""
        result = await aget_all_types_dict([])
        assert isinstance(result, dict), "Should return empty dict for empty paths"

        result = await aget_all_types_dict(["/nonexistent/path"])
        assert isinstance(result, dict), "Should return empty dict for non-existent paths"
        assert len(result) == 0, "Should return empty dict for non-existent paths"

        with pytest.raises(Exception) as exc_info:  # noqa: PT011
            await aget_all_types_dict([""])
        assert "path" in str(exc_info.value).lower(), f"Path-related error expected, got: {exc_info.value}"

        result = await import_langflow_components()
        assert isinstance(result, dict)
        assert "components" in result

    @pytest.mark.benchmark
    async def test_component_loading_performance(self):
        """Test the performance of component loading."""
        await import_langflow_components()

    @pytest.mark.no_blockbuster
    @pytest.mark.asyncio
    async def test_process_single_module_exception_handling(self):
        """Test that _process_single_module catches all exceptions during module import and component building.

        This ensures that if a component fails to import or build (e.g., due to network errors,
        missing dependencies, or initialization failures), it doesn't crash Langflow startup.
        """
        from unittest.mock import patch

        from lfx.interface.components import _process_single_module

        exception_cases = [
            (ImportError("Missing dependency: some_package"), "ImportError"),
            (AttributeError("Module has no attribute 'something'"), "AttributeError"),
            (ConnectionError("503 Service Unavailable"), "ConnectionError"),
            (TimeoutError("Request timed out"), "TimeoutError"),
            (RuntimeError("Component initialization failed"), "RuntimeError"),
            (ValueError("Invalid configuration"), "ValueError"),
            (Exception("Unexpected error during import"), "Exception"),
        ]

        for exception, name in exception_cases:
            with patch("importlib.import_module", side_effect=exception):
                result = _process_single_module("lfx.components.test_module")
                assert result is None, f"Should return None when {name} occurs"

        from urllib3.exceptions import MaxRetryError

        with patch("importlib.import_module", side_effect=MaxRetryError(None, "", reason="Connection timeout")):
            result = _process_single_module("lfx.components.test_module")
            assert result is None, "Should return None when MaxRetryError occurs"
