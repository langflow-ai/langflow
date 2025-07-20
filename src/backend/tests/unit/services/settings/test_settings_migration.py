import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from langflow.services.settings.base import Settings


@pytest.fixture
def temp_dirs():
    """Create temporary cache and config directories for testing."""
    cache_dir = tempfile.mkdtemp()
    config_dir = tempfile.mkdtemp()
    yield cache_dir, config_dir

    shutil.rmtree(cache_dir, ignore_errors=True)
    shutil.rmtree(config_dir, ignore_errors=True)


def test_config_dir_migration_from_cache_to_config(temp_dirs):
    """Test that data is migrated from cache directory to config directory."""
    cache_dir, config_dir = temp_dirs
    
    # Remove config directory to simulate first run after upgrade
    shutil.rmtree(config_dir)
    
    # Create some test files in cache directory
    test_file = Path(cache_dir) / "test.txt"
    test_file.write_text("test content")
    
    test_subdir = Path(cache_dir) / "subdir"
    test_subdir.mkdir()
    test_subfile = test_subdir / "subfile.txt"
    test_subfile.write_text("sub content")
    
    with patch("platformdirs.user_cache_dir") as mock_cache_dir, \
         patch("platformdirs.user_config_dir") as mock_config_dir:
        
        mock_cache_dir.return_value = cache_dir
        mock_config_dir.return_value = config_dir
        
        result = Settings.set_langflow_dir(None)
        
        assert result == config_dir
        assert (Path(config_dir) / "test.txt").exists()
        assert (Path(config_dir) / "test.txt").read_text() == "test content"
        assert (Path(config_dir) / "subdir" / "subfile.txt").exists()
        assert (Path(config_dir) / "subdir" / "subfile.txt").read_text() == "sub content"


def test_config_dir_no_migration_when_config_exists(temp_dirs):
    """Test that migration doesn't happen if config directory already exists."""
    cache_dir, config_dir = temp_dirs
    
    Path(config_dir).mkdir(exist_ok=True)
    cache_file = Path(cache_dir) / "cache_only.txt"
    cache_file.write_text("cache content")
    
    config_file = Path(config_dir) / "config_only.txt"
    config_file.write_text("config content")
    
    with patch("platformdirs.user_cache_dir") as mock_cache_dir, \
         patch("platformdirs.user_config_dir") as mock_config_dir:
        
        mock_cache_dir.return_value = cache_dir
        mock_config_dir.return_value = config_dir
        
        result = Settings.set_langflow_dir(None)
        assert result == config_dir
        # Cache file should NOT be migrated
        assert not (Path(config_dir) / "cache_only.txt").exists()
        
        # Config file should still exist
        assert (Path(config_dir) / "config_only.txt").exists()


def test_config_dir_fallback_on_migration_failure(temp_dirs, caplog):
    """Test that system falls back to cache directory if migration fails."""
    cache_dir, config_dir = temp_dirs
    
    # Remove config directory to trigger migration
    shutil.rmtree(config_dir)
    test_file = Path(cache_dir) / "test.txt"
    test_file.write_text("test content")
    
    with patch("platformdirs.user_cache_dir") as mock_cache_dir, \
         patch("platformdirs.user_config_dir") as mock_config_dir, \
         patch("pathlib.Path.mkdir") as mock_mkdir:
        
        mock_cache_dir.return_value = cache_dir
        mock_config_dir.return_value = config_dir
        
        # Make mkdir fail to simulate migration failure
        mock_mkdir.side_effect = PermissionError("Permission denied")
        
        result = Settings.set_langflow_dir(None)
        # Should fall back to cache directory
        assert result == cache_dir
        # Check that error was logged
        assert "Failed to migrate data from cache to config directory" in caplog.text


def test_config_dir_uses_provided_value():
    """Test that explicitly provided config_dir is used without migration."""
    custom_dir = tempfile.mkdtemp()
    
    try:
        result = Settings.set_langflow_dir(custom_dir)
        assert result == custom_dir
    finally:
        shutil.rmtree(custom_dir, ignore_errors=True)


def test_config_dir_creates_directory_if_not_exists():
    """Test that config_dir is created if it doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        non_existent_dir = Path(temp_dir) / "new_config"
        result = Settings.set_langflow_dir(str(non_existent_dir))
        assert result == str(non_existent_dir)
        assert non_existent_dir.exists()
        assert non_existent_dir.is_dir()