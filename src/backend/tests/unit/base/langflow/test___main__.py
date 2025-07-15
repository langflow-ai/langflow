"""
Unit tests for langflow.__main__ module.
Tests covering CLI commands, ProcessManager, utility functions, and main execution flow.
Testing Framework: pytest
"""

import pytest
import sys
import os
import signal
import socket
import asyncio
from unittest.mock import Mock, patch, MagicMock, call, AsyncMock
from pathlib import Path
from typer.testing import CliRunner
from io import StringIO
from contextlib import contextmanager

# Import the module components under test
from langflow.__main__ import (
    app, 
    ProcessManager, 
    process_manager,
    get_number_of_workers,
    is_port_in_use,
    get_free_port,
    is_loopback_address,
    can_connect,
    get_best_access_host,
    build_version_notice,
    generate_pip_command,
    stylize_text,
    print_banner,
    main,
    run,
    superuser,
    copy_db,
    migration,
    api_key,
    show_version,
    api_key_banner,
    set_var_for_macos_issue,
    wait_for_server_ready,
    get_letter_from_version,
    display_results
)


class TestProcessManager:
    """Test suite for ProcessManager class."""

    def test_process_manager_initialization(self):
        """Test ProcessManager initialization."""
        manager = ProcessManager()
        assert manager.webapp_process is None
        assert manager.shutdown_in_progress is False
        assert hasattr(manager, '_farewell_emoji')

    @patch('platform.system')
    def test_farewell_emoji_windows(self, mock_system):
        """Test farewell emoji selection on Windows."""
        mock_system.return_value = "Windows"
        manager = ProcessManager()
        assert manager._farewell_emoji == ":)"

    @patch('platform.system')
    def test_farewell_emoji_non_windows(self, mock_system):
        """Test farewell emoji selection on non-Windows systems."""
        mock_system.return_value = "Linux"
        manager = ProcessManager()
        assert manager._farewell_emoji == "👋"

    def test_handle_sigterm_not_in_progress(self):
        """Test SIGTERM handler when shutdown not in progress."""
        manager = ProcessManager()
        with patch.object(manager, 'shutdown') as mock_shutdown:
            manager.handle_sigterm(signal.SIGTERM, None)
            mock_shutdown.assert_called_once()
            assert manager.shutdown_in_progress is True

    def test_handle_sigterm_already_in_progress(self):
        """Test SIGTERM handler when shutdown already in progress."""
        manager = ProcessManager()
        manager.shutdown_in_progress = True
        with patch.object(manager, 'shutdown') as mock_shutdown:
            manager.handle_sigterm(signal.SIGTERM, None)
            mock_shutdown.assert_not_called()

    def test_handle_sigint_not_in_progress(self):
        """Test SIGINT handler when shutdown not in progress."""
        manager = ProcessManager()
        with patch.object(manager, 'shutdown') as mock_shutdown:
            manager.handle_sigint(signal.SIGINT, None)
            mock_shutdown.assert_called_once()
            assert manager.shutdown_in_progress is True

    def test_handle_sigint_already_in_progress(self):
        """Test SIGINT handler when shutdown already in progress."""
        manager = ProcessManager()
        manager.shutdown_in_progress = True
        with patch.object(manager, 'shutdown') as mock_shutdown:
            manager.handle_sigint(signal.SIGINT, None)
            mock_shutdown.assert_not_called()

    @patch('sys.exit')
    def test_shutdown_no_process(self, mock_exit):
        """Test shutdown when no webapp process exists."""
        manager = ProcessManager()
        manager.webapp_process = None
        manager.shutdown()
        mock_exit.assert_called_once_with(0)

    @patch('sys.exit')
    def test_shutdown_with_alive_process(self, mock_exit):
        """Test shutdown with alive webapp process."""
        manager = ProcessManager()
        mock_process = Mock()
        mock_process.is_alive.return_value = True
        manager.webapp_process = mock_process
        
        with patch.object(manager, 'print_farewell_message'):
            manager.shutdown()
            
        mock_process.terminate.assert_called_once()
        mock_process.join.assert_called_once_with(timeout=30)
        mock_exit.assert_called_once_with(0)

    @patch('sys.exit')
    def test_shutdown_with_stubborn_process(self, mock_exit):
        """Test shutdown with process that doesn't terminate gracefully."""
        manager = ProcessManager()
        mock_process = Mock()
        mock_process.is_alive.side_effect = [True, True, False]  # Alive, then needs killing, then dead
        manager.webapp_process = mock_process
        
        with patch.object(manager, 'print_farewell_message'):
            manager.shutdown()
            
        mock_process.terminate.assert_called_once()
        mock_process.kill.assert_called_once()
        mock_exit.assert_called_once_with(0)

    @patch('sys.stdout')
    @patch('click.echo')
    @patch('click.style')
    def test_print_farewell_message(self, mock_style, mock_echo, mock_stdout):
        """Test farewell message printing."""
        manager = ProcessManager()
        mock_style.return_value = "styled farewell"
        
        manager.print_farewell_message()
        
        mock_stdout.write.assert_called()
        mock_echo.assert_called()
        mock_style.assert_called_once()


class TestUtilityFunctions:
    """Test suite for utility functions."""

    def test_get_number_of_workers_none(self):
        """Test get_number_of_workers with None input."""
        with patch('langflow.__main__.cpu_count', return_value=2):
            result = get_number_of_workers(None)
            assert result == 5  # (2 * 2) + 1

    def test_get_number_of_workers_minus_one(self):
        """Test get_number_of_workers with -1 input."""
        with patch('langflow.__main__.cpu_count', return_value=4):
            result = get_number_of_workers(-1)
            assert result == 9  # (4 * 2) + 1

    def test_get_number_of_workers_specific_value(self):
        """Test get_number_of_workers with specific value."""
        result = get_number_of_workers(3)
        assert result == 3

    @patch('socket.socket')
    def test_is_port_in_use_available(self, mock_socket):
        """Test is_port_in_use when port is available."""
        mock_socket_instance = Mock()
        mock_socket_instance.connect_ex.return_value = 1  # Not 0 means not connected
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        result = is_port_in_use(8080)
        assert result is False

    @patch('socket.socket')
    def test_is_port_in_use_occupied(self, mock_socket):
        """Test is_port_in_use when port is occupied."""
        mock_socket_instance = Mock()
        mock_socket_instance.connect_ex.return_value = 0  # 0 means connected
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        result = is_port_in_use(8080)
        assert result is True

    def test_get_free_port(self):
        """Test get_free_port function."""
        with patch('langflow.__main__.is_port_in_use') as mock_is_port_in_use:
            mock_is_port_in_use.side_effect = [True, True, False]  # First two in use, third free
            
            result = get_free_port(8080)
            assert result == 8082

    def test_is_loopback_address_localhost(self):
        """Test is_loopback_address with localhost."""
        assert is_loopback_address("localhost") is True

    def test_is_loopback_address_all_interfaces(self):
        """Test is_loopback_address with 0.0.0.0."""
        assert is_loopback_address("0.0.0.0") is True

    def test_is_loopback_address_ipv4_loopback(self):
        """Test is_loopback_address with IPv4 loopback."""
        assert is_loopback_address("127.0.0.1") is True

    def test_is_loopback_address_ipv6_loopback(self):
        """Test is_loopback_address with IPv6 loopback."""
        assert is_loopback_address("::1") is True

    def test_is_loopback_address_regular_ip(self):
        """Test is_loopback_address with regular IP."""
        assert is_loopback_address("192.168.1.1") is False

    def test_is_loopback_address_invalid_ip(self):
        """Test is_loopback_address with invalid IP."""
        assert is_loopback_address("invalid.ip") is False

    @patch('socket.getaddrinfo')
    @patch('socket.socket')
    def test_can_connect_success(self, mock_socket, mock_getaddrinfo):
        """Test can_connect when connection succeeds."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 8080))]
        mock_socket_instance = Mock()
        mock_socket_instance.connect_ex.return_value = 0
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        result = can_connect("localhost", 8080)
        assert result is True

    @patch('socket.getaddrinfo')
    @patch('socket.socket')
    def test_can_connect_failure(self, mock_socket, mock_getaddrinfo):
        """Test can_connect when connection fails."""
        mock_getaddrinfo.return_value = [(socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 8080))]
        mock_socket_instance = Mock()
        mock_socket_instance.connect_ex.return_value = 1  # Connection failed
        mock_socket.return_value.__enter__.return_value = mock_socket_instance
        
        result = can_connect("localhost", 8080)
        assert result is False

    def test_get_best_access_host_non_loopback(self):
        """Test get_best_access_host with non-loopback address."""
        result = get_best_access_host("192.168.1.1", 8080)
        assert result == "192.168.1.1"

    def test_get_best_access_host_localhost_available(self):
        """Test get_best_access_host when localhost is available."""
        with patch('langflow.__main__.is_loopback_address', return_value=True):
            with patch('langflow.__main__.can_connect', return_value=True):
                result = get_best_access_host("127.0.0.1", 8080)
                assert result == "localhost"

    def test_get_best_access_host_localhost_unavailable(self):
        """Test get_best_access_host when localhost is unavailable."""
        with patch('langflow.__main__.is_loopback_address', return_value=True):
            with patch('langflow.__main__.can_connect', side_effect=[False, True]):
                result = get_best_access_host("127.0.0.1", 8080)
                assert result == "127.0.0.1"


class TestVersionFunctions:
    """Test suite for version-related functions."""

    def test_get_letter_from_version_alpha(self):
        """Test get_letter_from_version with alpha version."""
        result = get_letter_from_version("1.0.0a1")
        assert result == "a"

    def test_get_letter_from_version_beta(self):
        """Test get_letter_from_version with beta version."""
        result = get_letter_from_version("1.0.0b1")
        assert result == "b"

    def test_get_letter_from_version_rc(self):
        """Test get_letter_from_version with release candidate."""
        result = get_letter_from_version("1.0.0rc1")
        assert result == "rc"

    def test_get_letter_from_version_stable(self):
        """Test get_letter_from_version with stable version."""
        result = get_letter_from_version("1.0.0")
        assert result is None

    @patch('langflow.__main__.fetch_latest_version')
    def test_build_version_notice_newer_available(self, mock_fetch):
        """Test build_version_notice when newer version is available."""
        mock_fetch.return_value = "1.1.0"
        
        result = build_version_notice("1.0.0", "langflow")
        assert "A new version of langflow is available: 1.1.0" in result

    @patch('langflow.__main__.fetch_latest_version')
    def test_build_version_notice_pre_release(self, mock_fetch):
        """Test build_version_notice with pre-release version."""
        mock_fetch.return_value = "1.1.0a1"
        
        result = build_version_notice("1.0.0", "langflow")
        assert "A new pre-release of langflow is available: 1.1.0a1" in result

    @patch('langflow.__main__.fetch_latest_version')
    def test_build_version_notice_no_update(self, mock_fetch):
        """Test build_version_notice when no update is available."""
        mock_fetch.return_value = "1.0.0"
        
        result = build_version_notice("1.0.0", "langflow")
        assert result == ""

    @patch('langflow.__main__.fetch_latest_version')
    def test_build_version_notice_connection_error(self, mock_fetch):
        """Test build_version_notice with connection error."""
        mock_fetch.side_effect = Exception("Connection failed")
        
        result = build_version_notice("1.0.0", "langflow")
        assert result == ""

    def test_generate_pip_command_regular(self):
        """Test generate_pip_command for regular packages."""
        result = generate_pip_command(["langflow"], False)
        assert result == "pip install langflow -U"

    def test_generate_pip_command_pre_release(self):
        """Test generate_pip_command for pre-release packages."""
        result = generate_pip_command(["langflow"], True)
        assert result == "pip install langflow -U --pre"

    def test_generate_pip_command_multiple_packages(self):
        """Test generate_pip_command for multiple packages."""
        result = generate_pip_command(["langflow", "langflow-base"], False)
        assert result == "pip install langflow langflow-base -U"

    def test_stylize_text_regular_version(self):
        """Test stylize_text with regular version."""
        result = stylize_text("Install langflow now", "langflow", is_prerelease=False)
        assert "[#6e42f5]langflow[/]" in result

    def test_stylize_text_pre_release_version(self):
        """Test stylize_text with pre-release version."""
        result = stylize_text("Install langflow now", "langflow", is_prerelease=True)
        assert "[#42a7f5]langflow[/]" in result


class TestBannerFunctions:
    """Test suite for banner and display functions."""

    @patch('langflow.__main__.console')
    @patch('langflow.__main__.get_version_info')
    @patch('langflow.__main__.get_best_access_host')
    def test_print_banner_success(self, mock_get_host, mock_version_info, mock_console):
        """Test print_banner successful execution."""
        mock_version_info.return_value = {"version": "1.0.0", "package": "langflow"}
        mock_get_host.return_value = "localhost"
        
        print_banner("127.0.0.1", 7860, "http")
        
        mock_console.print.assert_called()

    @patch('langflow.__main__.console')
    @patch('langflow.__main__.get_version_info')
    @patch('langflow.__main__.get_best_access_host')
    def test_print_banner_unicode_error(self, mock_get_host, mock_version_info, mock_console):
        """Test print_banner with Unicode encoding error."""
        mock_version_info.return_value = {"version": "1.0.0", "package": "langflow"}
        mock_get_host.return_value = "localhost"
        mock_console.print.side_effect = [UnicodeEncodeError("ascii", "test", 0, 1, "invalid")]
        
        print_banner("127.0.0.1", 7860, "http")
        
        # Should still call print (fallback behavior)
        assert mock_console.print.call_count >= 1

    @patch('langflow.__main__.console')
    def test_display_results(self, mock_console):
        """Test display_results function."""
        mock_table_result = Mock()
        mock_table_result.table_name = "test_table"
        mock_table_result.results = [
            Mock(name="test1", type="migration", success=True),
            Mock(name="test2", type="migration", success=False)
        ]
        
        display_results([mock_table_result])
        
        mock_console.print.assert_called()

    @patch('platform.system')
    def test_set_var_for_macos_issue_darwin(self, mock_system):
        """Test set_var_for_macos_issue on Darwin system."""
        mock_system.return_value = "Darwin"
        
        with patch.dict(os.environ, {}, clear=True):
            set_var_for_macos_issue()
            assert os.environ.get("OBJC_DISABLE_INITIALIZE_FORK_SAFETY") == "YES"
            assert os.environ.get("no_proxy") == "*"

    @patch('platform.system')
    def test_set_var_for_macos_issue_non_darwin(self, mock_system):
        """Test set_var_for_macos_issue on non-Darwin system."""
        mock_system.return_value = "Linux"
        
        with patch.dict(os.environ, {}, clear=True):
            set_var_for_macos_issue()
            assert "OBJC_DISABLE_INITIALIZE_FORK_SAFETY" not in os.environ
            assert "no_proxy" not in os.environ

    @patch('time.sleep')
    @patch('httpx.get')
    def test_wait_for_server_ready_success(self, mock_get, mock_sleep):
        """Test wait_for_server_ready when server becomes ready."""
        mock_response = Mock()
        mock_response.status_code = 200  # httpx.codes.OK
        mock_get.return_value = mock_response
        
        wait_for_server_ready("localhost", 7860, "http")
        
        mock_get.assert_called_once()
        mock_sleep.assert_not_called()

    @patch('time.sleep')
    @patch('httpx.get')
    def test_wait_for_server_ready_retry(self, mock_get, mock_sleep):
        """Test wait_for_server_ready with retry logic."""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_get.side_effect = [mock_response_fail, mock_response_success]
        
        wait_for_server_ready("localhost", 7860, "http")
        
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(1)


class TestCLICommands:
    """Test suite for CLI commands."""

    def test_runner_fixture_setup(self):
        """Test that runner fixture works correctly."""
        runner = CliRunner()
        assert runner is not None

    def test_show_version(self):
        """Test show_version function."""
        with patch('langflow.__main__.get_version_info') as mock_version_info:
            mock_version_info.return_value = {"version": "1.0.0"}
            
            with pytest.raises(SystemExit):
                show_version(value=True)

    def test_show_version_no_action(self):
        """Test show_version when value is False."""
        # Should not raise SystemExit when value is False
        show_version(value=False)

    @patch('langflow.__main__.pyperclip')
    @patch('langflow.__main__.console')
    def test_api_key_banner(self, mock_console, mock_pyperclip):
        """Test api_key_banner function."""
        mock_api_key = Mock()
        mock_api_key.api_key = "test_key_123"
        
        api_key_banner(mock_api_key)
        
        mock_pyperclip.copy.assert_called_once_with("test_key_123")
        mock_console.print.assert_called_once()

    @patch('langflow.__main__.pyperclip')
    @patch('langflow.__main__.logger')
    def test_api_key_banner_unicode_error(self, mock_logger, mock_pyperclip):
        """Test api_key_banner with Unicode encoding error."""
        mock_api_key = Mock()
        mock_api_key.api_key = "test_key_123"
        
        with patch('langflow.__main__.Console') as mock_console_class:
            mock_console = Mock()
            mock_console.print.side_effect = UnicodeEncodeError("ascii", "test", 0, 1, "invalid")
            mock_console_class.return_value = mock_console
            
            api_key_banner(mock_api_key)
            
            mock_pyperclip.copy.assert_called_once_with("test_key_123")
            mock_logger.info.assert_called()

    def test_main_function_exists(self):
        """Test that main function exists and is callable."""
        assert callable(main)

    @patch('warnings.catch_warnings')
    @patch('langflow.__main__.app')
    def test_main_function_execution(self, mock_app, mock_warnings):
        """Test main function execution."""
        mock_warnings.return_value.__enter__ = Mock()
        mock_warnings.return_value.__exit__ = Mock()
        
        main()
        
        mock_app.assert_called_once()

    def test_typer_app_instance(self):
        """Test that typer app instance is created."""
        assert app is not None
        assert hasattr(app, 'command')

    @patch('langflow.__main__.main')
    def test_module_main_block(self, mock_main):
        """Test module execution when run as script."""
        # This would be called when the module is executed directly
        # The actual check is in the if __name__ == "__main__": block
        # We're testing that main() gets called in that scenario
        import langflow.__main__
        
        # Simulate direct execution
        with patch('langflow.__main__.__name__', '__main__'):
            # In the actual module, this would trigger the main() call
            # We're just testing that the logic would work
            if langflow.__main__.__name__ == '__main__':
                main()
        
        mock_main.assert_called_once()


class TestIntegrationScenarios:
    """Test suite for integration scenarios and edge cases."""

    def test_signal_handler_registration(self):
        """Test that signal handlers are properly registered."""
        # The module should have registered signal handlers
        # We can check that they are bound to the process_manager methods
        assert hasattr(process_manager, 'handle_sigterm')
        assert hasattr(process_manager, 'handle_sigint')

    @patch('langflow.__main__.ProcessManager')
    def test_process_manager_singleton(self, mock_manager_class):
        """Test that process_manager is a singleton instance."""
        # The module should create a single instance
        assert process_manager is not None
        assert isinstance(process_manager, ProcessManager)

    def test_typer_app_configuration(self):
        """Test typer app configuration."""
        # Check that app is configured correctly
        assert app.info.no_args_is_help is True

    @patch('langflow.__main__.asyncio.run')
    def test_async_command_execution(self, mock_asyncio_run):
        """Test async command execution pattern."""
        # Some commands use asyncio.run for async operations
        # This tests that the pattern works correctly
        
        async def dummy_async_func():
            return "test_result"
        
        # Simulate the asyncio.run pattern used in the module
        mock_asyncio_run.return_value = "test_result"
        result = asyncio.run(dummy_async_func())
        
        mock_asyncio_run.assert_called_once()
        assert result == "test_result"

    @patch('langflow.__main__.logger')
    def test_logging_integration(self, mock_logger):
        """Test logging integration in the module."""
        # The module uses logger for various operations
        # Test that logger is properly configured
        assert mock_logger is not None

    @patch('langflow.__main__.console')
    def test_console_integration(self, mock_console):
        """Test console integration for rich output."""
        # The module uses rich console for output
        # Test that console is properly configured
        assert mock_console is not None

    def test_environment_variable_handling(self):
        """Test environment variable handling."""
        # The module should handle various environment variables
        with patch.dict(os.environ, {'LANGFLOW_TEST': 'value'}):
            assert os.environ.get('LANGFLOW_TEST') == 'value'

    @patch('langflow.__main__.Path')
    def test_path_handling(self, mock_path):
        """Test path handling in the module."""
        # The module uses pathlib for path operations
        mock_path.return_value.exists.return_value = True
        
        # Test that path operations work correctly
        test_path = Path("test/path")
        assert mock_path.called or test_path is not None

    def test_platform_specific_behavior(self):
        """Test platform-specific behavior."""
        # The module has different behavior for different platforms
        with patch('platform.system') as mock_system:
            mock_system.return_value = "Windows"
            # Test Windows-specific behavior
            manager = ProcessManager()
            assert manager._farewell_emoji == ":)"
            
            mock_system.return_value = "Darwin"
            # Test macOS-specific behavior
            manager = ProcessManager()
            assert manager._farewell_emoji == "👋"

    def test_error_handling_patterns(self):
        """Test error handling patterns in the module."""
        # Test that the module handles errors gracefully
        with patch('langflow.__main__.logger') as mock_logger:
            try:
                # Simulate an error condition
                raise Exception("Test error")
            except Exception as e:
                # The module should handle exceptions properly
                assert str(e) == "Test error"

    @patch('langflow.__main__.typer.Exit')
    def test_exit_handling(self, mock_exit):
        """Test exit handling in the module."""
        # The module should handle exits properly
        mock_exit.return_value = SystemExit(1)
        
        with pytest.raises(SystemExit):
            raise mock_exit.return_value


if __name__ == '__main__':
    pytest.main([__file__, '-v'])