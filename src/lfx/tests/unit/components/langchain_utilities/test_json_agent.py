import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from lfx.components.langchain_utilities.json_agent import JsonAgentComponent


class TestJsonAgentComponent:
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return JsonAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "llm": MagicMock(),
            "path": "/tmp/test.json",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []

    @pytest.fixture
    def mock_langchain_community(self):
        """Mock langchain_community module to avoid requiring it as a dependency."""
        mock_json_spec = MagicMock()
        mock_json_spec.from_file = MagicMock()
        mock_json_tool = MagicMock()
        mock_json_tool.JsonSpec = mock_json_spec
        mock_json_toolkit = MagicMock()
        mock_json_toolkit.JsonToolkit = MagicMock()
        mock_agent_toolkits = MagicMock()
        mock_agent_toolkits.json = MagicMock()
        mock_agent_toolkits.json.toolkit = mock_json_toolkit
        mock_agent_toolkits.create_json_agent = MagicMock()
        mock_langchain_community = MagicMock()
        mock_langchain_community.agent_toolkits = mock_agent_toolkits
        mock_langchain_community.tools = MagicMock()
        mock_langchain_community.tools.json = MagicMock()
        mock_langchain_community.tools.json.tool = mock_json_tool

        with patch.dict(
            sys.modules,
            {
                "langchain_community": mock_langchain_community,
                "langchain_community.agent_toolkits": mock_agent_toolkits,
                "langchain_community.agent_toolkits.json": mock_agent_toolkits.json,
                "langchain_community.agent_toolkits.json.toolkit": mock_json_toolkit,
                "langchain_community.tools": mock_langchain_community.tools,
                "langchain_community.tools.json": mock_langchain_community.tools.json,
                "langchain_community.tools.json.tool": mock_json_tool,
            },
        ):
            yield {
                "JsonSpec": mock_json_spec,
                "JsonToolkit": mock_json_toolkit.JsonToolkit,
                "create_json_agent": mock_agent_toolkits.create_json_agent,
            }

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.path == "/tmp/test.json"

    def test_get_local_path_with_local_json_file(self, component_class):
        """Test _get_local_path returns Path for local JSON files."""
        component = component_class()

        # Create real JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"key": "value"}')
            json_file = f.name

        try:
            component.set_attributes({"llm": MagicMock(), "path": json_file})

            # Mock settings to indicate local storage
            with patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                local_path = component._get_local_path()
                assert isinstance(local_path, Path)
                assert str(local_path) == json_file
                assert not hasattr(component, "_temp_file_path")
        finally:
            Path(json_file).unlink()

    def test_get_local_path_with_s3_json_file(self, component_class):
        """Test _get_local_path downloads S3 JSON files to temp."""
        component = component_class()
        s3_path = "flow_456/config.json"
        component.set_attributes({"llm": MagicMock(), "path": s3_path})

        json_content = b'{"key": "value", "number": 42}'

        # Mock S3 storage and read - real temp file creation
        with (
            patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings,
            patch(
                "lfx.components.langchain_utilities.json_agent.read_file_bytes", new_callable=AsyncMock
            ) as mock_read_bytes,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = json_content

            # Real temp file creation
            local_path = component._get_local_path()

            # Verify real temp file was created
            assert isinstance(local_path, Path)
            import tempfile

            temp_dir = tempfile.gettempdir()
            assert str(local_path).startswith(temp_dir)
            assert str(local_path).endswith(".json")
            assert local_path.exists()
            assert local_path.read_bytes() == json_content
            assert hasattr(component, "_temp_file_path")

            # Cleanup
            component._cleanup_temp_file()
            assert not local_path.exists()

    def test_get_local_path_with_s3_yaml_file(self, component_class):
        """Test _get_local_path downloads S3 YAML files to temp with correct suffix."""
        component = component_class()
        s3_path = "flow_456/config.yml"
        component.set_attributes({"llm": MagicMock(), "path": s3_path})

        yaml_content = b"key: value\nnumber: 42"

        with (
            patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings,
            patch(
                "lfx.components.langchain_utilities.json_agent.read_file_bytes", new_callable=AsyncMock
            ) as mock_read_bytes,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = yaml_content

            local_path = component._get_local_path()

            # Verify .yml suffix was used
            assert str(local_path).endswith(".yml")
            assert local_path.read_bytes() == yaml_content

            # Cleanup
            component._cleanup_temp_file()

    def test_cleanup_temp_file(self, component_class):
        """Test that cleanup removes temp file."""
        component = component_class()

        # Create real temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"test": "data"}')
            temp_file = f.name

        component._temp_file_path = temp_file
        assert Path(temp_file).exists()

        component._cleanup_temp_file()
        assert not Path(temp_file).exists()

    def test_cleanup_temp_file_no_file(self, component_class):
        """Test that cleanup does nothing if no temp file exists."""
        component = component_class()
        # Should not raise an error
        component._cleanup_temp_file()

    def test_build_agent_with_local_json_file(self, component_class, mock_langchain_community):
        """Test build_agent with local JSON file."""
        component = component_class()

        # Create real JSON file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"users": [{"name": "Alice", "age": 30}]}')
            json_file = f.name

        try:
            component.set_attributes({"llm": MagicMock(), "path": json_file, "verbose": False})

            # Mock settings and LangChain agent components
            with patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                mock_json_spec = mock_langchain_community["JsonSpec"]
                mock_json_toolkit = mock_langchain_community["JsonToolkit"]
                mock_create_agent = mock_langchain_community["create_json_agent"]

                mock_spec = MagicMock()
                mock_json_spec.from_file.return_value = mock_spec
                mock_toolkit_instance = MagicMock()
                mock_json_toolkit.return_value = mock_toolkit_instance
                mock_agent = MagicMock()
                mock_create_agent.return_value = mock_agent

                agent = component.build_agent()

                assert agent == mock_agent
                # Verify real file was used
                mock_json_spec.from_file.assert_called_once_with(json_file)
        finally:
            Path(json_file).unlink()

    def test_build_agent_with_local_yaml_file(self, component_class, mock_langchain_community):
        """Test build_agent with local YAML file."""
        component = component_class()

        # Create real YAML file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("key: value\nnumber: 42")
            yaml_file = f.name

        try:
            component.set_attributes({"llm": MagicMock(), "path": yaml_file, "verbose": True})

            with (
                patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings,
                patch("builtins.open", create=True),
                patch("lfx.components.langchain_utilities.json_agent.yaml.safe_load") as mock_yaml_load,
            ):
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                yaml_data = {"key": "value", "number": 42}
                mock_yaml_load.return_value = yaml_data

                mock_json_spec = mock_langchain_community["JsonSpec"]
                mock_json_toolkit = mock_langchain_community["JsonToolkit"]
                mock_create_agent = mock_langchain_community["create_json_agent"]

                mock_spec = MagicMock()
                mock_json_spec.return_value = mock_spec
                mock_toolkit_instance = MagicMock()
                mock_json_toolkit.return_value = mock_toolkit_instance
                mock_agent = MagicMock()
                mock_create_agent.return_value = mock_agent

                agent = component.build_agent()

                assert agent == mock_agent
                # YAML files use JsonSpec(dict_=...) not from_file
                mock_json_spec.assert_called_once_with(dict_=yaml_data)
        finally:
            Path(yaml_file).unlink()

    def test_build_agent_with_s3_json_file(self, component_class, mock_langchain_community):
        """Test build_agent with S3 JSON file (downloads to temp)."""
        component = component_class()
        component.set_attributes({"llm": MagicMock(), "path": "flow_456/data.json", "verbose": False})

        json_content = b'{"users": []}'

        with (
            patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings,
            patch(
                "lfx.components.langchain_utilities.json_agent.read_file_bytes", new_callable=AsyncMock
            ) as mock_read_bytes,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = json_content

            mock_json_spec = mock_langchain_community["JsonSpec"]
            mock_json_toolkit = mock_langchain_community["JsonToolkit"]
            mock_create_agent = mock_langchain_community["create_json_agent"]

            mock_spec = MagicMock()
            mock_json_spec.from_file.return_value = mock_spec
            mock_toolkit_instance = MagicMock()
            mock_json_toolkit.return_value = mock_toolkit_instance
            mock_agent = MagicMock()
            mock_create_agent.return_value = mock_agent

            agent = component.build_agent()

            assert agent == mock_agent

            # Verify temp file was created and cleaned up
            call_path = mock_json_spec.from_file.call_args[0][0]
            import tempfile

            temp_dir = tempfile.gettempdir()
            assert call_path.startswith(temp_dir)
            assert call_path.endswith(".json")
            # Cleanup should have been called
            assert not Path(call_path).exists()

    def test_build_agent_cleans_up_on_error(self, component_class, mock_langchain_community):
        """Test that temp file is cleaned up even when agent creation fails."""
        component = component_class()
        component.set_attributes({"llm": MagicMock(), "path": "flow_456/data.json", "verbose": False})

        json_content = b'{"invalid'

        mock_create_agent = mock_langchain_community["create_json_agent"]
        mock_create_agent.side_effect = Exception("Invalid JSON")

        with (
            patch("lfx.components.langchain_utilities.json_agent.get_settings_service") as mock_get_settings,
            patch(
                "lfx.components.langchain_utilities.json_agent.read_file_bytes", new_callable=AsyncMock
            ) as mock_read_bytes,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = json_content

            with pytest.raises(Exception):  # noqa: B017, PT011
                component.build_agent()

            # Temp file should be cleaned up even after error
            if hasattr(component, "_temp_file_path"):
                temp_file_path = component._temp_file_path
                assert not Path(temp_file_path).exists()
