import pytest
from langflow.base.data.utils import format_directory_path


@pytest.mark.parametrize(
    "path, expected",
    [
        # Test case 1: Standard path with forward slashes
        ("/home/user/documents/file.txt", "/home/user/documents/file.txt"),
        # Test case 2: Path with backslashes (Windows-style)
        ("C:\\Users\\Documents\\file.txt", "C:/Users/Documents/file.txt"),
        # Test case 3: Mixed separators
        ("C:/Users\\Documents/file.txt", "C:/Users/Documents/file.txt"),
        # Test case 4: Path with only forward slashes
        ("/home/user/documents/", "/home/user/documents/"),
        # Test case 5: Path with only backslashes
        ("\\\\server\\share\\file.txt", "//server/share/file.txt"),
        # Test case 6: Path with no separators
        ("file.txt", "file.txt"),
        # Test case 7: Empty path
        ("", ""),
        # Test case 8: Path with special characters
        ("/home/user/my-docs/special_file!.pdf", "/home/user/my-docs/special_file!.pdf"),
        # Test case 9: Path with dots
        ("/home/user/../documents/./file.txt", "/home/user/../documents/./file.txt"),
    ],
)
def test_format_directory_path(path, expected):
    result = format_directory_path(path)
    assert result == expected


# Additional test for type checking
def test_format_directory_path_type():
    result = format_directory_path("/home/user/file.txt")
    assert isinstance(result, str)
