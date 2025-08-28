"""Test data purge service."""

import asyncio
import pytest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from langflow.services.data_purge.service import DataPurgeService, parse_time_interval


class TestParseTimeInterval:
    """Test the parse_time_interval function."""
    
    def test_parse_minutes(self):
        """Test parsing minute intervals."""
        result = parse_time_interval("1m")
        assert result == timedelta(minutes=1)
        
        result = parse_time_interval("30m")
        assert result == timedelta(minutes=30)
    
    def test_parse_hours(self):
        """Test parsing hour intervals."""
        result = parse_time_interval("1h")
        assert result == timedelta(hours=1)
        
        result = parse_time_interval("24h")
        assert result == timedelta(hours=24)
    
    def test_parse_days(self):
        """Test parsing day intervals."""
        result = parse_time_interval("1d")
        assert result == timedelta(days=1)
        
        result = parse_time_interval("7d")
        assert result == timedelta(days=7)
    
    def test_parse_case_insensitive(self):
        """Test that parsing is case insensitive."""
        result = parse_time_interval("1M")
        assert result == timedelta(minutes=1)
        
        result = parse_time_interval("2H")
        assert result == timedelta(hours=2)
        
        result = parse_time_interval("3D")
        assert result == timedelta(days=3)
    
    def test_parse_with_whitespace(self):
        """Test parsing with leading/trailing whitespace."""
        result = parse_time_interval(" 1m ")
        assert result == timedelta(minutes=1)
    
    def test_parse_invalid_format(self):
        """Test parsing invalid formats returns None."""
        assert parse_time_interval("") is None
        assert parse_time_interval(None) is None
        assert parse_time_interval("1") is None
        assert parse_time_interval("m1") is None
        assert parse_time_interval("1s") is None  # seconds not supported
        assert parse_time_interval("1x") is None  # invalid unit
        assert parse_time_interval("abc") is None
    
    def test_parse_invalid_number(self):
        """Test parsing with invalid numbers."""
        assert parse_time_interval("0m") == timedelta(minutes=0)
        assert parse_time_interval("-1m") is None  # negative numbers don't match regex


class TestDataPurgeService:
    """Test the DataPurgeService class."""
    
    @pytest.fixture
    def mock_database_service(self):
        """Create mock database service."""
        mock_db = MagicMock()
        mock_db.session_factory = MagicMock()
        return mock_db
    
    @pytest.fixture
    def mock_settings_service(self):
        """Create mock settings service."""
        mock_settings = MagicMock()
        mock_settings.settings = MagicMock()
        return mock_settings
    
    @pytest.fixture
    def purge_service(self, mock_database_service, mock_settings_service):
        """Create DataPurgeService instance with mocks."""
        return DataPurgeService(mock_database_service, mock_settings_service)
    
    @pytest.mark.asyncio
    async def test_initialization_disabled(self, purge_service, mock_settings_service):
        """Test service initialization when disabled."""
        mock_settings_service.settings.data_purge_interval = None
        
        await purge_service.initialize_service()
        
        assert purge_service.cleanup_interval is None
        assert purge_service.cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_initialization_valid_interval(self, purge_service, mock_settings_service):
        """Test service initialization with valid interval."""
        mock_settings_service.settings.data_purge_interval = "1h"
        
        await purge_service.initialize_service()
        
        assert purge_service.cleanup_interval == timedelta(hours=1)
        assert purge_service.cleanup_task is not None
    
    @pytest.mark.asyncio
    async def test_initialization_invalid_interval(self, purge_service, mock_settings_service):
        """Test service initialization with invalid interval."""
        mock_settings_service.settings.data_purge_interval = "invalid"
        
        await purge_service.initialize_service()
        
        assert purge_service.cleanup_interval is None
        assert purge_service.cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_purge_old_data(self, purge_service, mock_database_service):
        """Test data purge functionality."""
        # Mock session and results for all three tables
        mock_session = AsyncMock()
        mock_vertex_result = MagicMock()
        mock_vertex_result.rowcount = 2
        mock_message_result = MagicMock()
        mock_message_result.rowcount = 3
        mock_transaction_result = MagicMock()
        mock_transaction_result.rowcount = 1
        
        # Mock execute to return different results for each call
        mock_session.execute.side_effect = [mock_vertex_result, mock_message_result, mock_transaction_result]
        mock_database_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        deleted_count = await purge_service.purge_old_data()
        
        assert deleted_count == 6  # 2 + 3 + 1
        assert mock_session.execute.call_count == 3  # Called for each table
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_purge_old_data_no_data(self, purge_service, mock_database_service):
        """Test data purge when no data exists."""
        # Mock session and results with no rows for all tables
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_session.execute.return_value = mock_result
        mock_database_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        deleted_count = await purge_service.purge_old_data()
        
        assert deleted_count == 0
        assert mock_session.execute.call_count == 3  # Still called for each table
    
    @pytest.mark.asyncio
    async def test_purge_old_data_database_error(self, purge_service, mock_database_service):
        """Test data purge handles database errors."""
        # Mock session that raises an exception
        mock_session = AsyncMock()
        mock_session.execute.side_effect = Exception("Database error")
        mock_database_service.session_factory.return_value.__aenter__.return_value = mock_session
        
        deleted_count = await purge_service.purge_old_data()
        
        assert deleted_count == 0
    
    @pytest.mark.asyncio
    async def test_stop_periodic_cleanup(self, purge_service):
        """Test stopping periodic cleanup."""
        # Create a mock task
        mock_task = AsyncMock()
        purge_service.cleanup_task = mock_task
        
        await purge_service.stop_periodic_cleanup()
        
        mock_task.cancel.assert_called_once()
        assert purge_service.cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_teardown_service(self, purge_service):
        """Test service teardown."""
        # Create a mock task
        mock_task = AsyncMock()
        purge_service.cleanup_task = mock_task
        
        await purge_service.teardown_service()
        
        mock_task.cancel.assert_called_once()
        assert purge_service.cleanup_task is None
    
    @pytest.mark.asyncio
    async def test_setup_only_runs_once(self, purge_service, mock_settings_service):
        """Test setup method only runs once."""
        mock_settings_service.settings.data_purge_interval = "1h"
        
        # First call should initialize
        await purge_service.setup()
        assert purge_service._initialized is True
        
        # Reset the interval to test if setup runs again
        purge_service.cleanup_interval = None
        
        # Second call should not reinitialize
        await purge_service.setup()
        assert purge_service.cleanup_interval is None  # Should remain None