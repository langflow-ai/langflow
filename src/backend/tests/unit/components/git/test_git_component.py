import tempfile
from pathlib import Path

import pytest
from langflow.components.git import GitLoaderComponent


@pytest.fixture
def git_component():
    return GitLoaderComponent()


@pytest.fixture
def test_files():
    """Create temporary test files for filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a Python file
        python_file = Path(temp_dir) / "test.py"
        python_file.write_text("import langchain\nclass TestComponent:\n    pass", encoding="utf-8")

        # Create a text file
        text_file = Path(temp_dir) / "test.txt"
        text_file.write_text("This is a test file", encoding="utf-8")

        # Create a binary file
        binary_file = Path(temp_dir) / "test.bin"
        binary_file.write_bytes(b"Binary\x00Content")

        # Create a directory for permission tests
        no_access_dir = Path(temp_dir) / "no_access"
        no_access_dir.mkdir()
        no_access_file = no_access_dir / "secret.txt"
        no_access_file.write_text("secret", encoding="utf-8")
        no_access_file.chmod(0o000)  # Remove all permissions

        yield temp_dir


def test_is_binary(git_component, test_files):
    """Test binary file detection."""
    temp_dir = Path(test_files)

    # Test regular files
    assert not git_component.is_binary(temp_dir / "test.py")
    assert not git_component.is_binary(temp_dir / "test.txt")
    assert git_component.is_binary(temp_dir / "test.bin")

    # Test error cases
    assert git_component.is_binary(temp_dir / "nonexistent.txt")  # Non-existent file
    assert git_component.is_binary(temp_dir / "no_access" / "secret.txt")  # No permission


def test_check_file_patterns(git_component, test_files):
    """Test file pattern matching."""
    temp_dir = Path(test_files)

    # Test single pattern
    assert git_component.check_file_patterns(temp_dir / "test.py", "*.py")
    assert not git_component.check_file_patterns(temp_dir / "test.txt", "*.py")

    # Test exclusion pattern
    assert not git_component.check_file_patterns(temp_dir / "test.py", "!*.py")

    # Test multiple patterns
    assert git_component.check_file_patterns(temp_dir / "test.py", "*.py,*.txt")
    assert git_component.check_file_patterns(temp_dir / "test.txt", "*.py,*.txt")

    # Test mixed include/exclude
    assert not git_component.check_file_patterns(temp_dir / "test.py", "*.py,!test.py")
    assert git_component.check_file_patterns(temp_dir / "other.py", "*.py,!test.py")

    # Test empty pattern (should include all)
    assert git_component.check_file_patterns(temp_dir / "test.py", "")
    assert git_component.check_file_patterns(temp_dir / "test.txt", "  ")

    # Test invalid pattern (should treat as literal string)
    assert not git_component.check_file_patterns(temp_dir / "test.py", "[")


def test_check_content_pattern(git_component, test_files):
    """Test content pattern matching."""
    temp_dir = Path(test_files)

    # Test simple content match
    assert git_component.check_content_pattern(temp_dir / "test.py", r"import langchain")
    assert not git_component.check_content_pattern(temp_dir / "test.txt", r"import langchain")

    # Test regex pattern
    assert git_component.check_content_pattern(temp_dir / "test.py", r"class.*Component")

    # Test binary file
    assert not git_component.check_content_pattern(temp_dir / "test.bin", r"Binary")

    # Test invalid regex patterns
    assert not git_component.check_content_pattern(temp_dir / "test.py", r"[")  # Unclosed bracket
    assert not git_component.check_content_pattern(temp_dir / "test.py", r"*")  # Invalid quantifier
    assert not git_component.check_content_pattern(temp_dir / "test.py", r"(?<)")  # Invalid lookbehind
    assert not git_component.check_content_pattern(temp_dir / "test.py", r"\1")  # Invalid backreference


def test_combined_filter(git_component, test_files):
    """Test the combined filter function."""
    temp_dir = Path(test_files)

    # Test with both patterns
    filter_func = git_component.build_combined_filter(
        file_filter_patterns="*.py", content_filter_pattern=r"class.*Component"
    )
    assert filter_func(str(temp_dir / "test.py"))
    assert not filter_func(str(temp_dir / "test.txt"))
    assert not filter_func(str(temp_dir / "test.bin"))

    # Test with only file pattern
    filter_func = git_component.build_combined_filter(file_filter_patterns="*.py")
    assert filter_func(str(temp_dir / "test.py"))
    assert not filter_func(str(temp_dir / "test.txt"))

    # Test with only content pattern
    filter_func = git_component.build_combined_filter(content_filter_pattern=r"class.*Component")
    assert filter_func(str(temp_dir / "test.py"))
    assert not filter_func(str(temp_dir / "test.txt"))

    # Test with empty patterns
    filter_func = git_component.build_combined_filter()
    assert filter_func(str(temp_dir / "test.py"))
    assert filter_func(str(temp_dir / "test.txt"))
    assert not filter_func(str(temp_dir / "test.bin"))  # Binary files still excluded

    # Test error cases
    filter_func = git_component.build_combined_filter(
        file_filter_patterns="*.py", content_filter_pattern=r"class.*Component"
    )
    assert not filter_func(str(temp_dir / "nonexistent.txt"))  # Non-existent file
    assert not filter_func(str(temp_dir / "no_access" / "secret.txt"))  # No permission
