"""Tests for the component loading fix that filters out BASE_COMPONENTS_PATH from custom components.

- BASE_COMPONENTS_PATH is properly filtered out from custom components paths
- Lazy loading mode works correctly
- Custom components are loaded only from valid custom paths
- No regression in existing functionality
"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from langflow.interface.components import (
    component_cache,
    get_and_cache_all_types_dict,
)
from langflow.services.settings.base import BASE_COMPONENTS_PATH
from langflow.services.settings.service import SettingsService


class TestComponentLoadingFix:
    """Test suite for the component loading fix that filters BASE_COMPONENTS_PATH."""

    @pytest.fixture
    def mock_settings_service(self):
        """Create a mock settings service with configurable options."""
        settings_service = MagicMock(spec=SettingsService)
        settings_service.settings = MagicMock()
        settings_service.settings.lazy_load_components = False
        settings_service.settings.components_path = []
        return settings_service

    @pytest.fixture
    def mock_custom_paths(self):
        """Create mock custom component paths."""
        return ["/custom/path1", "/custom/path2"]

    @pytest.fixture
    def mock_langflow_components(self):
        """Create mock langflow components response."""
        return {
            "components": {
                "category1": {
                    "Component1": {"display_name": "Component1", "type": "category1"},
                    "Component2": {"display_name": "Component2", "type": "category1"},
                },
                "category2": {
                    "Component3": {"display_name": "Component3", "type": "category2"},
                },
            }
        }

    @pytest.fixture
    def mock_custom_components(self):
        """Create mock custom components response."""
        return {
            "custom_category": {
                "CustomComponent1": {"display_name": "CustomComponent1", "type": "custom_category"},
                "CustomComponent2": {"display_name": "CustomComponent2", "type": "custom_category"},
            }
        }

    @pytest.fixture(autouse=True)
    def clear_component_cache(self):
        """Clear component cache before each test."""
        component_cache.all_types_dict = None
        yield
        component_cache.all_types_dict = None

    @pytest.mark.asyncio
    async def test_base_components_path_filtering(
        self, mock_settings_service, mock_langflow_components, mock_custom_components
    ):
        """Test that BASE_COMPONENTS_PATH is properly filtered out from custom components paths."""
        # Setup: Include BASE_COMPONENTS_PATH in the components_path list
        mock_settings_service.settings.components_path = [BASE_COMPONENTS_PATH, "/custom/path1", "/custom/path2"]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict") as mock_aget_all_types_dict,
        ):
            # Mock aget_all_types_dict to return custom components
            mock_aget_all_types_dict.return_value = mock_custom_components

            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_all_types_dict was called with filtered paths (BASE_COMPONENTS_PATH excluded)
            mock_aget_all_types_dict.assert_called_once_with(["/custom/path1", "/custom/path2"])

            # Verify result contains both langflow and custom components
            assert "category1" in result
            assert "category2" in result
            assert "custom_category" in result
            assert "Component1" in result["category1"]
            assert "CustomComponent1" in result["custom_category"]

    @pytest.mark.asyncio
    async def test_only_base_components_path_in_list(self, mock_settings_service, mock_langflow_components):
        """Test behavior when components_path contains only BASE_COMPONENTS_PATH."""
        # Setup: Only BASE_COMPONENTS_PATH in the list
        mock_settings_service.settings.components_path = [BASE_COMPONENTS_PATH]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict") as mock_aget_all_types_dict,
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_all_types_dict was NOT called (no custom paths after filtering)
            mock_aget_all_types_dict.assert_not_called()

            # Verify result contains only langflow components
            assert "category1" in result
            assert "category2" in result
            assert "Component1" in result["category1"]
            assert "Component3" in result["category2"]

    @pytest.mark.asyncio
    async def test_empty_components_path(self, mock_settings_service, mock_langflow_components):
        """Test behavior when components_path is empty."""
        # Setup: Empty components_path
        mock_settings_service.settings.components_path = []
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict") as mock_aget_all_types_dict,
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_all_types_dict was NOT called
            mock_aget_all_types_dict.assert_not_called()

            # Verify result contains only langflow components
            assert "category1" in result
            assert "category2" in result
            assert "Component1" in result["category1"]

    @pytest.mark.asyncio
    async def test_none_components_path(self, mock_settings_service, mock_langflow_components):
        """Test behavior when components_path is None."""
        # Setup: None components_path
        mock_settings_service.settings.components_path = None
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict") as mock_aget_all_types_dict,
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_all_types_dict was NOT called
            mock_aget_all_types_dict.assert_not_called()

            # Verify result contains only langflow components
            assert "category1" in result
            assert "category2" in result

    @pytest.mark.asyncio
    async def test_lazy_loading_mode_with_base_path_filtering(self, mock_settings_service, mock_langflow_components):
        """Test that lazy loading mode uses aget_component_metadata with filtered paths."""
        # Setup: Enable lazy loading and include BASE_COMPONENTS_PATH
        mock_settings_service.settings.lazy_load_components = True
        mock_settings_service.settings.components_path = [BASE_COMPONENTS_PATH, "/custom/path1"]

        mock_metadata = {
            "custom_category": {
                "CustomComponent1": {"display_name": "CustomComponent1", "type": "custom_category"},
            }
        }

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch(
                "langflow.interface.components.aget_component_metadata", return_value=mock_metadata
            ) as mock_aget_metadata,
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_component_metadata was called with the full path (not filtered in lazy mode)
            mock_aget_metadata.assert_called_once_with([BASE_COMPONENTS_PATH, "/custom/path1"])

            # Verify result contains both langflow and custom components
            assert "category1" in result
            assert "custom_category" in result

    @pytest.mark.asyncio
    async def test_multiple_custom_paths_with_base_path(
        self, mock_settings_service, mock_langflow_components, mock_custom_components
    ):
        """Test filtering with multiple custom paths and BASE_COMPONENTS_PATH."""
        # Setup: Multiple paths including BASE_COMPONENTS_PATH
        custom_paths = ["/path1", BASE_COMPONENTS_PATH, "/path2", "/path3"]
        mock_settings_service.settings.components_path = custom_paths
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch(
                "langflow.interface.components.aget_all_types_dict", return_value=mock_custom_components
            ) as mock_aget_all_types_dict,
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that aget_all_types_dict was called with filtered paths
            expected_filtered_paths = ["/path1", "/path2", "/path3"]
            mock_aget_all_types_dict.assert_called_once_with(expected_filtered_paths)

            # Verify result structure
            assert isinstance(result, dict)
            assert "category1" in result  # From langflow components
            assert "custom_category" in result  # From custom components

    @pytest.mark.asyncio
    async def test_component_merging_logic(self, mock_settings_service, mock_langflow_components):
        """Test that langflow and custom components are properly merged."""
        # Setup
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        # Create overlapping component names to test merging behavior
        overlapping_custom_components = {
            "category1": {  # Same category as langflow
                "Component1": {"display_name": "CustomComponent1", "type": "category1"},  # Same name as langflow
                "Component4": {"display_name": "Component4", "type": "category1"},  # New component
            },
            "new_category": {
                "NewComponent": {"display_name": "NewComponent", "type": "new_category"},
            },
        }

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value=overlapping_custom_components),
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that custom components override langflow components with same name
            assert "category1" in result
            assert "category2" in result  # From langflow
            assert "new_category" in result  # From custom

            # Custom category should completely override langflow category
            assert result["category1"]["Component1"]["display_name"] == "CustomComponent1"

            # Only components from custom category should remain in category1
            assert "Component2" not in result["category1"]  # Langflow component is replaced by custom category
            assert "Component4" in result["category1"]  # New custom component

            # New custom component should be added
            assert result["category1"]["Component4"]["display_name"] == "Component4"

            # New category should be added
            assert result["new_category"]["NewComponent"]["display_name"] == "NewComponent"

    @pytest.mark.asyncio
    async def test_component_cache_behavior(self, mock_settings_service, mock_langflow_components):
        """Test that component cache is properly used and populated."""
        # Setup
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value={}),
        ):
            # First call - should populate cache
            result1 = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify cache is populated
            assert component_cache.all_types_dict is not None
            assert component_cache.all_types_dict == result1

            # Second call - should use cache
            result2 = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify same result returned from cache
            assert result1 == result2
            assert result1 is result2  # Same object reference

    @pytest.mark.asyncio
    async def test_logging_behavior(self, mock_settings_service, mock_langflow_components, mock_custom_components):
        """Test that appropriate logging messages are generated."""
        # Setup
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value=mock_custom_components),
            patch("langflow.interface.components.logger") as mock_logger,
        ):
            # Execute the function
            await get_and_cache_all_types_dict(mock_settings_service)

            # Verify debug logging calls
            mock_logger.debug.assert_any_call("Building components cache")

            # Verify total component count logging
            debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
            total_count_logs = [log for log in debug_calls if "Loaded" in log and "components" in log]
            assert len(total_count_logs) >= 1

    @pytest.mark.asyncio
    async def test_error_handling_in_custom_component_loading(self, mock_settings_service, mock_langflow_components):
        """Test error handling when custom component loading fails."""
        # Setup
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", side_effect=Exception("Custom loading failed")),
            pytest.raises(Exception, match="Custom loading failed"),
        ):
            # Execute the function - should raise exception when custom component loading fails
            await get_and_cache_all_types_dict(mock_settings_service)

    @pytest.mark.asyncio
    async def test_base_components_path_constant_value(self):
        """Test that BASE_COMPONENTS_PATH has expected value and behavior."""
        # Verify BASE_COMPONENTS_PATH is defined and has expected characteristics
        assert BASE_COMPONENTS_PATH is not None
        assert isinstance(BASE_COMPONENTS_PATH, str)
        assert len(BASE_COMPONENTS_PATH) > 0

        # Should be an absolute path containing "langflow" and "components"
        assert "langflow" in BASE_COMPONENTS_PATH.lower()
        assert "components" in BASE_COMPONENTS_PATH.lower()

    @pytest.mark.asyncio
    async def test_path_filtering_edge_cases(self, mock_settings_service, mock_langflow_components):
        """Test edge cases in path filtering logic."""
        # Setup
        mock_settings_service.settings.lazy_load_components = False

        # Test with duplicate BASE_COMPONENTS_PATH
        mock_settings_service.settings.components_path = [BASE_COMPONENTS_PATH, "/custom/path", BASE_COMPONENTS_PATH]

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value={}) as mock_aget_all_types_dict,
        ):
            # Clear cache for fresh test
            component_cache.all_types_dict = None

            # Execute the function
            await get_and_cache_all_types_dict(mock_settings_service)

            # Verify that both instances of BASE_COMPONENTS_PATH are filtered out
            mock_aget_all_types_dict.assert_called_once_with(["/custom/path"])

    @pytest.mark.asyncio
    async def test_component_count_calculation(self, mock_settings_service, mock_langflow_components):
        """Test that component count calculation works correctly."""
        # Setup with known component counts
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        # Mock custom components with known count
        mock_custom_components = {
            "custom_cat1": {
                "CustomComp1": {"display_name": "CustomComp1"},
                "CustomComp2": {"display_name": "CustomComp2"},
            },
            "custom_cat2": {
                "CustomComp3": {"display_name": "CustomComp3"},
            },
        }

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value=mock_custom_components),
        ):
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify result structure
            assert len(result) >= 2  # At least langflow categories + custom categories

            # Verify custom components are present
            assert "custom_cat1" in result
            assert "custom_cat2" in result
            assert "CustomComp1" in result["custom_cat1"]
            assert "CustomComp3" in result["custom_cat2"]

    @pytest.mark.asyncio
    async def test_async_concurrency_safety(
        self, mock_settings_service, mock_langflow_components, mock_custom_components
    ):
        """Test that concurrent calls to get_and_cache_all_types_dict are safe."""
        # Setup
        mock_settings_service.settings.components_path = ["/custom/path1"]
        mock_settings_service.settings.lazy_load_components = False

        with (
            patch("langflow.interface.components.import_langflow_components", return_value=mock_langflow_components),
            patch("langflow.interface.components.aget_all_types_dict", return_value=mock_custom_components),
        ):
            # Execute multiple concurrent calls
            tasks = [get_and_cache_all_types_dict(mock_settings_service) for _ in range(3)]
            results = await asyncio.gather(*tasks)

            # Verify all results are identical (cache working properly)
            first_result = results[0]
            for result in results[1:]:
                assert result == first_result
                # Results should be consistent, though reference may vary due to concurrency

    @pytest.mark.asyncio
    async def test_integration_with_real_base_components_path(self, mock_settings_service):
        """Integration test with real BASE_COMPONENTS_PATH to ensure filtering works."""
        # Setup with real BASE_COMPONENTS_PATH value
        mock_settings_service.settings.components_path = [BASE_COMPONENTS_PATH, "/custom/test"]
        mock_settings_service.settings.lazy_load_components = False

        # This test should work with real langflow components
        with patch("langflow.interface.components.aget_all_types_dict", return_value={}) as mock_aget_all_types_dict:
            # Execute the function
            result = await get_and_cache_all_types_dict(mock_settings_service)

            # Verify BASE_COMPONENTS_PATH was filtered out
            mock_aget_all_types_dict.assert_called_once_with(["/custom/test"])

            # Verify we got real langflow components
            assert isinstance(result, dict)
            assert len(result) > 0  # Should have langflow components
