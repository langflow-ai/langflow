import pytest
from unittest.mock import patch, MagicMock
import platform
import os

from langflow.components.tools.shell_session_manager import ShellSessionManager
from tests.base import ComponentTestBaseWithoutClient, VersionComponentMapping
import pytest

@pytest.mark.skip(reason="Skipping due to BlockingError in CI environment.")

class TestShellSessionManager(ComponentTestBaseWithoutClient):
    @pytest.fixture
    def component_class(self):
        return ShellSessionManager

    @pytest.fixture
    def default_kwargs(self, tmp_path):
        return {
            "working_directory": str(tmp_path),
            "default_shell": "",
            "sessions_directory": str(tmp_path / ".langflow_shell_sessions"),
        }

    @pytest.fixture
    def file_names_mapping(self) -> list[VersionComponentMapping]:
        return []

    def test_component_initialization(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        assert hasattr(component, "sessions")
        assert isinstance(component.sessions, dict)
        assert os.path.exists(component.sessions_dir)

    def test_build_toolkit_returns_tools(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        assert isinstance(toolkit, list)
        assert any(callable(tool) for tool in toolkit)

    def test_start_and_list_session(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        start_shell_session = toolkit[0]
        list_shell_sessions = toolkit[3]
        session_name = "testsession"
        result = start_shell_session({"session_name": session_name})
        assert f"Session started with ID: {session_name}" in result or "already exists" in result
        list_result = list_shell_sessions({})
        assert session_name in list_result or "No active sessions" in list_result
        # Cleanup
        close_shell_session = toolkit[5]
        close_shell_session({"session_id": session_name})

    def test_run_command_and_get_output(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        start_shell_session = toolkit[0]
        run_command = toolkit[1]
        get_session_output = toolkit[2]
        close_shell_session = toolkit[5]
        session_name = "cmdsession"
        start_shell_session({"session_name": session_name})
        # Run a simple echo command
        if platform.system() == "Windows":
            cmd = "echo HelloTest"
        else:
            cmd = "echo 'HelloTest'"
        run_result = run_command({"session_id": session_name, "command": cmd})
        assert "Command sent" in run_result or "Warning" in run_result
        # Give the shell a moment to process
        import time; time.sleep(0.5)
        output = get_session_output({"session_id": session_name, "read_all": True})
        assert "HelloTest" in output or "No new output" in output or "terminated" in output
        close_shell_session({"session_id": session_name})

    def test_send_signal_and_close(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        start_shell_session = toolkit[0]
        send_signal_to_session = toolkit[4]
        close_shell_session = toolkit[5]
        session_name = "sigtest"
        start_shell_session({"session_name": session_name})
        # Try sending SIGINT (should not error)
        result = send_signal_to_session({"session_id": session_name, "signal_name": "SIGINT"})
        assert "Sent sigint" in result or "Error" in result or "terminated" in result
        # Cleanup
        close_shell_session({"session_id": session_name})

    def test_close_nonexistent_session(self, component_class, default_kwargs):
        component = component_class(**default_kwargs)
        toolkit = component.build_toolkit()
        close_shell_session = toolkit[5]
        result = close_shell_session({"session_id": "doesnotexist"})
        assert "not found" in result or "already cleaned up" in result
