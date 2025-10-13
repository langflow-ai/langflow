import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from langflow.components.langchain_utilities.csv_agent import CSVAgentComponent
from langflow.schema import Message
from tests.base import ComponentTestBaseWithoutClient


class TestCSVAgentComponent(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        """Return the component class to test."""
        return CSVAgentComponent

    @pytest.fixture
    def default_kwargs(self):
        """Return the default kwargs for the component."""
        return {
            "llm": MagicMock(),
            "path": "/tmp/test.csv",
            "agent_type": "openai-tools",
            "input_value": "What is the sum of column A?",
        }

    @pytest.fixture
    def file_names_mapping(self):
        """Return the file names mapping for different versions."""
        return []

    def test_basic_setup(self, component_class, default_kwargs):
        """Test basic component initialization."""
        component = component_class()
        component.set_attributes(default_kwargs)
        assert component.agent_type == "openai-tools"
        assert component.input_value == "What is the sum of column A?"

    def test_path_message_input(self, component_class):
        """Test that path can be provided as Message object."""
        component = component_class()
        message = Message(text="/tmp/test.csv")
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": message,
                "agent_type": "openai-tools",
                "input_value": "test query",
            }
        )
        assert component._path() == "/tmp/test.csv"

    def test_path_string_input(self, component_class):
        """Test that path can be provided as string."""
        component = component_class()
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": "/tmp/test.csv",
                "agent_type": "openai-tools",
                "input_value": "test query",
            }
        )
        assert component._path() == "/tmp/test.csv"

    def test_get_local_path_with_local_file(self, component_class):
        """Test _get_local_path returns path as-is for local storage."""
        component = component_class()
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": "/tmp/test.csv",
                "agent_type": "openai-tools",
                "input_value": "test",
            }
        )

        # Mock settings to indicate local storage
        with patch("langflow.services.deps.get_settings_service") as mock_get_settings:
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "local"
            mock_get_settings.return_value = mock_settings

            local_path = component._get_local_path()
            assert local_path == "/tmp/test.csv"
            # Should not have created temp file path
            assert not hasattr(component, "_temp_file_path")

    def test_get_local_path_with_s3_file(self, component_class):
        """Test _get_local_path downloads S3 files to temp."""
        component = component_class()
        s3_path = "flow_123/data.csv"
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": s3_path,
                "agent_type": "openai-tools",
                "input_value": "test",
            }
        )

        csv_content = b"col1,col2\n1,2\n3,4"

        # Mock S3 storage and read operations - real temp file creation and cleanup
        with (
            patch("langflow.services.deps.get_settings_service") as mock_get_settings,
            patch("langflow.base.data.storage_utils.read_file_bytes") as mock_read_bytes,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = csv_content

            # Real temp file creation
            local_path = component._get_local_path()

            # Verify real temp file was created (use tempfile.gettempdir() for cross-platform)
            import tempfile

            temp_dir = tempfile.gettempdir()
            assert local_path.startswith(temp_dir)
            assert local_path.endswith(".csv")
            assert Path(local_path).exists()
            assert Path(local_path).read_bytes() == csv_content
            assert hasattr(component, "_temp_file_path")

            # Cleanup
            component._cleanup_temp_file()
            assert not Path(local_path).exists()

    def test_get_local_path_with_absolute_path_no_download(self, component_class):
        """Test that local files are used directly when storage is local."""
        component = component_class()

        # Create a real temp file to simulate existing local file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2\n1,2")
            temp_file = f.name

        try:
            component.set_attributes(
                {
                    "llm": MagicMock(),
                    "path": temp_file,
                    "agent_type": "openai-tools",
                    "input_value": "test",
                }
            )

            # Mock settings to indicate local storage
            with patch("langflow.services.deps.get_settings_service") as mock_get_settings:
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                local_path = component._get_local_path()

                # Should return original path without downloading
                assert local_path == temp_file
                assert not hasattr(component, "_temp_file_path")
        finally:
            Path(temp_file).unlink()

    def test_cleanup_temp_file(self, component_class):
        """Test that cleanup removes temp file."""
        component = component_class()

        # Create a real temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("test")
            temp_file = f.name

        component._temp_file_path = temp_file
        assert Path(temp_file).exists()

        component._cleanup_temp_file()
        assert not Path(temp_file).exists()

    def test_cleanup_temp_file_no_file(self, component_class):
        """Test that cleanup does nothing if no temp file exists."""
        component = component_class()
        # No _temp_file_path attribute set
        # Should not raise an error
        component._cleanup_temp_file()

    def test_cleanup_temp_file_handles_errors(self, component_class):
        """Test that cleanup silently handles errors for non-existent files."""
        component = component_class()
        component._temp_file_path = "/tmp/non_existent_file_xyz.csv"
        # Should not raise an error
        component._cleanup_temp_file()

    def test_build_agent_response_with_local_file(self, component_class):
        """Test build_agent_response with local CSV file."""
        component = component_class()

        # Create a real CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2\n1,a\n2,b")
            csv_file = f.name

        try:
            component.set_attributes(
                {
                    "llm": MagicMock(),
                    "path": csv_file,
                    "agent_type": "openai-tools",
                    "input_value": "What is the sum?",
                    "verbose": False,
                    "handle_parsing_errors": True,
                    "pandas_kwargs": {},
                }
            )

            # Mock settings and LangChain agent
            with (
                patch("langflow.services.deps.get_settings_service") as mock_get_settings,
                patch("langflow.components.langchain_utilities.csv_agent.create_csv_agent") as mock_create_agent,
            ):
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                mock_agent = MagicMock()
                mock_agent.invoke.return_value = {"output": "The sum is 3"}
                mock_create_agent.return_value = mock_agent

                result = component.build_agent_response()

                assert isinstance(result, Message)
                assert result.text == "The sum is 3"
                mock_create_agent.assert_called_once()
                # Verify real file was passed
                call_kwargs = mock_create_agent.call_args[1]
                assert call_kwargs["path"] == csv_file
        finally:
            Path(csv_file).unlink()

    def test_build_agent_response_with_s3_file(self, component_class):
        """Test build_agent_response with S3 CSV file (downloads to temp)."""
        component = component_class()
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": "flow_123/data.csv",
                "agent_type": "openai-tools",
                "input_value": "What is the total?",
                "verbose": False,
                "handle_parsing_errors": True,
                "pandas_kwargs": {},
            }
        )

        csv_content = b"col1,col2\n1,2\n3,4"

        # Mock S3 settings, storage read, and LangChain agent creation
        with (
            patch("langflow.services.deps.get_settings_service") as mock_get_settings,
            patch("langflow.base.data.storage_utils.read_file_bytes") as mock_read_bytes,
            patch("langflow.components.langchain_utilities.csv_agent.create_csv_agent") as mock_create_agent,
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = csv_content

            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {"output": "The total is 10"}
            mock_create_agent.return_value = mock_agent

            result = component.build_agent_response()

            assert isinstance(result, Message)
            assert result.text == "The total is 10"

            # Verify agent was created with real temp file path
            mock_create_agent.assert_called_once()
            call_kwargs = mock_create_agent.call_args[1]
            created_path = call_kwargs["path"]
            import tempfile

            temp_dir = tempfile.gettempdir()
            assert created_path.startswith(temp_dir)
            assert created_path.endswith(".csv")
            # Temp file should be cleaned up after execution
            assert not Path(created_path).exists()

    def test_build_agent_response_cleans_up_on_error(self, component_class):
        """Test that temp file is cleaned up even when agent execution fails."""
        component = component_class()
        component.set_attributes(
            {
                "llm": MagicMock(),
                "path": "flow_123/data.csv",
                "agent_type": "openai-tools",
                "input_value": "test",
                "verbose": False,
                "handle_parsing_errors": True,
                "pandas_kwargs": {},
            }
        )

        csv_content = b"col1\n1\n2"
        temp_file_path = None

        with (
            patch("langflow.services.deps.get_settings_service") as mock_get_settings,
            patch("langflow.base.data.storage_utils.read_file_bytes") as mock_read_bytes,
            patch(
                "langflow.components.langchain_utilities.csv_agent.create_csv_agent",
                side_effect=Exception("Agent creation failed"),
            ),
        ):
            mock_settings = MagicMock()
            mock_settings.settings.storage_type = "s3"
            mock_get_settings.return_value = mock_settings
            mock_read_bytes.return_value = csv_content

            with pytest.raises(Exception, match="Agent creation failed"):
                component.build_agent_response()

            # Temp file should be cleaned up even after error
            if hasattr(component, "_temp_file_path"):
                temp_file_path = component._temp_file_path
                assert not Path(temp_file_path).exists()

    def test_build_agent(self, component_class):
        """Test build_agent method."""
        component = component_class()

        # Create real CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2\n1,a\n2,b")
            csv_file = f.name

        try:
            component.set_attributes(
                {
                    "llm": MagicMock(),
                    "path": csv_file,
                    "agent_type": "openai-tools",
                    "input_value": "test",
                    "verbose": True,
                    "handle_parsing_errors": False,
                    "pandas_kwargs": {"encoding": "utf-8"},
                }
            )

            with (
                patch("langflow.services.deps.get_settings_service") as mock_get_settings,
                patch("langflow.components.langchain_utilities.csv_agent.create_csv_agent") as mock_create_agent,
            ):
                mock_settings = MagicMock()
                mock_settings.settings.storage_type = "local"
                mock_get_settings.return_value = mock_settings

                mock_agent = MagicMock()
                mock_create_agent.return_value = mock_agent

                agent = component.build_agent()

                assert agent == mock_agent
                mock_create_agent.assert_called_once()
                call_kwargs = mock_create_agent.call_args[1]
                assert call_kwargs["verbose"] is True
                assert call_kwargs["allow_dangerous_code"] is True
                assert call_kwargs["handle_parsing_errors"] is False
                assert call_kwargs["pandas_kwargs"] == {"encoding": "utf-8"}
                assert call_kwargs["path"] == csv_file
        finally:
            Path(csv_file).unlink()
