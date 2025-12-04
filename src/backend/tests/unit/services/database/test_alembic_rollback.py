"""Tests for Alembic migration rollback/forward compatibility mechanism.

This tests the ability for Langflow to start up when the database has newer
migrations than the code (e.g., after rolling back code but not database).
"""

import re
from unittest.mock import Mock, patch

import pytest
from alembic import script
from alembic.util.exc import CommandError
from langflow.services.database.service import DatabaseService
from langflow.services.database.utils import initialize_database


class TestCheckIfDatabaseAhead:
    """Test the _check_if_database_ahead method."""

    def test_returns_false_when_error_not_about_missing_revision(self):
        """Should return False if error message doesn't contain 'Can't locate revision'."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = DatabaseService._check_if_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Some other error message"

        result = service._check_if_database_ahead(alembic_cfg, error_msg)

        assert result is False

    def test_returns_false_when_revision_exists_in_code(self):
        """Should return False if the DB revision exists in code (DB not ahead)."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = DatabaseService._check_if_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Can't locate revision identified by 'abc123'"

        # Mock script directory to return the revision (exists in code)
        mock_script_dir = Mock(spec=script.ScriptDirectory)
        mock_script_dir.get_revision = Mock(return_value=Mock())  # Revision found

        with patch(
            "langflow.services.database.service.script.ScriptDirectory.from_config",
            return_value=mock_script_dir,
        ):
            result = service._check_if_database_ahead(alembic_cfg, error_msg)

        assert result is False
        mock_script_dir.get_revision.assert_called_once_with("abc123")

    def test_returns_true_when_revision_not_in_code(self):
        """Should return True if the DB revision doesn't exist in code (DB is ahead)."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = DatabaseService._check_if_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Can't locate revision identified by 'xyz789'"

        # Mock script directory to raise exception (revision not found)
        mock_script_dir = Mock(spec=script.ScriptDirectory)
        mock_script_dir.get_revision = Mock(side_effect=Exception("Revision not found"))
        mock_script_dir.get_current_head = Mock(return_value="abc123")

        with (
            patch(
                "langflow.services.database.service.script.ScriptDirectory.from_config",
                return_value=mock_script_dir,
            ),
            patch("langflow.services.database.service.logger") as mock_logger,
        ):
            result = service._check_if_database_ahead(alembic_cfg, error_msg)

        assert result is True
        mock_script_dir.get_revision.assert_called_once_with("xyz789")
        mock_logger.warning.assert_called_once()
        warning_msg = mock_logger.warning.call_args[0][0]
        assert "xyz789" in warning_msg
        assert "abc123" in warning_msg
        assert "ahead" in warning_msg.lower()

    def test_handles_different_quote_styles(self):
        """Should extract revision from error messages with single or double quotes."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = DatabaseService._check_if_database_ahead.__get__(service)

        alembic_cfg = Mock()

        # Test with single quotes
        error_msg_single = "Can't locate revision identified by 'abc123'"
        # Test with double quotes
        error_msg_double = 'Can\'t locate revision identified by "xyz789"'

        mock_script_dir = Mock(spec=script.ScriptDirectory)
        mock_script_dir.get_revision = Mock(side_effect=Exception("Not found"))
        mock_script_dir.get_current_head = Mock(return_value="head")

        with (
            patch(
                "langflow.services.database.service.script.ScriptDirectory.from_config",
                return_value=mock_script_dir,
            ),
            patch("langflow.services.database.service.logger"),
        ):
            result1 = service._check_if_database_ahead(alembic_cfg, error_msg_single)
            result2 = service._check_if_database_ahead(alembic_cfg, error_msg_double)

        assert result1 is True
        assert result2 is True
        # Verify correct revisions were extracted
        assert mock_script_dir.get_revision.call_args_list[0][0][0] == "abc123"
        assert mock_script_dir.get_revision.call_args_list[1][0][0] == "xyz789"

    def test_returns_false_on_unexpected_exception(self):
        """Should return False and log debug message on unexpected exceptions."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = DatabaseService._check_if_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Can't locate revision identified by 'abc123'"

        # Mock script directory to raise unexpected exception
        with (
            patch(
                "langflow.services.database.service.script.ScriptDirectory.from_config",
                side_effect=RuntimeError("Unexpected"),
            ),
            patch("langflow.services.database.service.logger") as mock_logger,
        ):
            result = service._check_if_database_ahead(alembic_cfg, error_msg)

        assert result is False
        mock_logger.debug.assert_called_once()
        debug_msg = mock_logger.debug.call_args[0][0]
        assert "Could not determine if database is ahead" in debug_msg


class TestHandleDatabaseAhead:
    """Test the _handle_database_ahead method."""

    def test_returns_true_and_logs_when_database_ahead(self):
        """Should return True and log info message when database is ahead."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = Mock(return_value=True)
        service._handle_database_ahead = DatabaseService._handle_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Can't locate revision identified by 'xyz789'"

        with patch("langflow.services.database.service.logger") as mock_logger:
            result = service._handle_database_ahead(alembic_cfg, error_msg)

        assert result is True
        service._check_if_database_ahead.assert_called_once_with(alembic_cfg, error_msg)
        mock_logger.info.assert_called_once()
        info_msg = mock_logger.info.call_args[0][0]
        assert "newer migrations" in info_msg.lower()
        assert "backwards-compatible" in info_msg.lower()

    def test_returns_false_when_database_not_ahead(self):
        """Should return False when database is not ahead."""
        service = Mock(spec=DatabaseService)
        service._check_if_database_ahead = Mock(return_value=False)
        service._handle_database_ahead = DatabaseService._handle_database_ahead.__get__(service)

        alembic_cfg = Mock()
        error_msg = "Some other error"

        with patch("langflow.services.database.service.logger") as mock_logger:
            result = service._handle_database_ahead(alembic_cfg, error_msg)

        assert result is False
        service._check_if_database_ahead.assert_called_once_with(alembic_cfg, error_msg)
        mock_logger.info.assert_not_called()


class TestRunMigrationsWithRollback:
    """Test the _run_migrations method with rollback scenarios."""

    @patch("langflow.services.database.service.command")
    def test_allows_startup_when_database_ahead_on_check(self, mock_command):
        """Should allow startup when database is ahead (detected during check)."""
        service = Mock(spec=DatabaseService)
        service.alembic_log_to_stdout = True
        service.script_location = Mock()
        service.database_url = "sqlite:///test.db"
        service._handle_database_ahead = Mock(return_value=True)
        service._run_migrations = DatabaseService._run_migrations.__get__(service)

        # Simulate check() raising error about missing revision
        mock_command.check.side_effect = CommandError("Can't locate revision identified by 'xyz789'")

        # Should not raise exception
        service._run_migrations(should_initialize_alembic=False, fix=False)

        # Verify check was called
        mock_command.check.assert_called_once()
        # Verify upgrade was NOT called (startup allowed without migration)
        mock_command.upgrade.assert_not_called()
        # Verify database ahead handler was called
        service._handle_database_ahead.assert_called_once()

    @patch("langflow.services.database.service.command")
    def test_allows_startup_when_database_ahead_on_upgrade_failure(self, mock_command):
        """Should allow startup when database is ahead (detected during upgrade failure)."""
        service = Mock(spec=DatabaseService)
        service.alembic_log_to_stdout = True
        service.script_location = Mock()
        service.database_url = "sqlite:///test.db"
        service._handle_database_ahead = Mock(side_effect=[False, True])  # False on check, True on upgrade
        service._run_migrations = DatabaseService._run_migrations.__get__(service)

        # Simulate check() raising CommandError, then upgrade() also failing
        mock_command.check.side_effect = CommandError("AutogenerateDiffsDetected")
        mock_command.upgrade.side_effect = CommandError("Can't locate revision identified by 'xyz789'")

        # Should not raise exception
        service._run_migrations(should_initialize_alembic=False, fix=False)

        # Verify both check and upgrade were called
        mock_command.check.assert_called_once()
        mock_command.upgrade.assert_called_once()
        # Verify database ahead handler was called twice
        assert service._handle_database_ahead.call_count == 2

    @patch("langflow.services.database.service.command")
    def test_upgrades_when_database_behind(self, mock_command):
        """Should upgrade database when it's behind the code."""
        service = Mock(spec=DatabaseService)
        service.alembic_log_to_stdout = True
        service.script_location = Mock()
        service.database_url = "sqlite:///test.db"
        service._handle_database_ahead = Mock(return_value=False)
        service._run_migrations = DatabaseService._run_migrations.__get__(service)

        # Simulate check() raising CommandError (DB behind)
        mock_command.check.side_effect = [CommandError("Diffs detected"), None]  # Fails first, succeeds after upgrade

        # Should not raise exception
        service._run_migrations(should_initialize_alembic=False, fix=False)

        # Verify upgrade was called
        mock_command.upgrade.assert_called_once_with(mock_command.upgrade.call_args[0][0], "head")

    @patch("langflow.services.database.service.command")
    def test_raises_on_unhandled_error(self, mock_command):
        """Should raise exception for unhandled errors."""
        service = Mock(spec=DatabaseService)
        service.alembic_log_to_stdout = True
        service.script_location = Mock()
        service.database_url = "sqlite:///test.db"
        service._handle_database_ahead = Mock(return_value=False)
        service._run_migrations = DatabaseService._run_migrations.__get__(service)

        # Simulate check() raising unhandled error
        mock_command.check.side_effect = RuntimeError("Unexpected error")

        # Should raise the exception
        with pytest.raises(RuntimeError, match="Unexpected error"):
            service._run_migrations(should_initialize_alembic=False, fix=False)


class TestInitializeDatabaseWithRollback:
    """Test the initialize_database function with rollback scenarios."""

    @pytest.mark.asyncio
    async def test_allows_startup_when_database_ahead(self):
        """Should allow startup when CommandError indicates database is ahead."""
        from unittest.mock import AsyncMock

        mock_db_service = Mock(spec=DatabaseService)
        mock_settings_service = Mock()
        mock_settings_service.settings = Mock()
        mock_settings_service.settings.database_connection_retry = False
        mock_db_service.settings_service = mock_settings_service
        mock_db_service.create_db_and_tables = AsyncMock()
        mock_db_service.check_schema_health = AsyncMock()
        mock_db_service.run_migrations = AsyncMock(
            side_effect=CommandError("Can't locate revision identified by 'xyz789'")
        )

        mock_logger = Mock()
        mock_logger.adebug = AsyncMock()
        mock_logger.info = Mock()

        with (
            patch("langflow.services.deps.get_db_service", return_value=mock_db_service),
            patch("langflow.services.database.utils.logger", mock_logger),
        ):
            # Should not raise exception
            await initialize_database(fix_migration=False)

            # Verify info message was logged
            mock_logger.info.assert_called_once()
            info_msg = mock_logger.info.call_args[0][0]
            assert "ahead of code" in info_msg.lower()

    @pytest.mark.asyncio
    async def test_handles_overlapping_revisions(self):
        """Should drop alembic_version table and retry on overlapping revisions."""
        from unittest.mock import AsyncMock

        mock_db_service = Mock(spec=DatabaseService)
        mock_settings_service = Mock()
        mock_settings_service.settings = Mock()
        mock_settings_service.settings.database_connection_retry = False
        mock_db_service.settings_service = mock_settings_service
        mock_db_service.create_db_and_tables = AsyncMock()
        mock_db_service.check_schema_health = AsyncMock()

        # First call raises overlapping error, second succeeds
        mock_db_service.run_migrations = AsyncMock(side_effect=[
            CommandError("overlaps with other requested revisions"),
            None
        ])

        mock_session = Mock()
        mock_session.exec = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        mock_logger = Mock()
        mock_logger.adebug = AsyncMock()
        mock_logger.warning = Mock()

        with (
            patch("langflow.services.deps.get_db_service", return_value=mock_db_service),
            patch("langflow.services.database.utils.session_getter", return_value=mock_session),
            patch("langflow.services.database.utils.logger", mock_logger),
        ):
            # Should not raise exception
            await initialize_database(fix_migration=False)

            # Verify warning was logged
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Overlapping revisions" in warning_msg

            # Verify run_migrations was called twice
            assert mock_db_service.run_migrations.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_on_unhandled_command_error(self):
        """Should raise exception for unhandled CommandError."""
        from unittest.mock import AsyncMock

        mock_db_service = Mock(spec=DatabaseService)
        mock_settings_service = Mock()
        mock_settings_service.settings = Mock()
        mock_settings_service.settings.database_connection_retry = False
        mock_db_service.settings_service = mock_settings_service
        mock_db_service.create_db_and_tables = AsyncMock()
        mock_db_service.check_schema_health = AsyncMock()
        mock_db_service.run_migrations = AsyncMock(side_effect=CommandError("Unhandled error"))

        mock_logger = Mock()
        mock_logger.adebug = AsyncMock()

        with (
            patch("langflow.services.deps.get_db_service", return_value=mock_db_service),
            patch("langflow.services.database.utils.logger", mock_logger),
            pytest.raises(CommandError, match="Unhandled error"),
        ):
            await initialize_database(fix_migration=False)


class TestRevisionExtractionRegex:
    """Test the regex pattern used to extract revision IDs from error messages."""

    def test_extracts_revision_with_single_quotes(self):
        """Should extract revision ID from error with single quotes."""
        error_msg = "Can't locate revision identified by 'abc123def456'"
        match = re.search(r"identified by ['\"]([^'\"]+)['\"]", error_msg)
        assert match is not None
        assert match.group(1) == "abc123def456"

    def test_extracts_revision_with_double_quotes(self):
        """Should extract revision ID from error with double quotes."""
        error_msg = 'Can\'t locate revision identified by "xyz789ghi012"'
        match = re.search(r"identified by ['\"]([^'\"]+)['\"]", error_msg)
        assert match is not None
        assert match.group(1) == "xyz789ghi012"

    def test_handles_revision_with_special_characters(self):
        """Should extract revision ID with underscores and hyphens."""
        error_msg = "Can't locate revision identified by 'abc_123-def'"
        match = re.search(r"identified by ['\"]([^'\"]+)['\"]", error_msg)
        assert match is not None
        assert match.group(1) == "abc_123-def"

    def test_returns_none_for_malformed_message(self):
        """Should return None for messages without proper format."""
        error_msg = "Can't locate revision abc123"
        match = re.search(r"identified by ['\"]([^'\"]+)['\"]", error_msg)
        assert match is None

# Made with Bob
