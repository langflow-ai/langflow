from langflow.graph.utils import rewrite_file_path
import pytest


@pytest.mark.parametrize(
    "file_path, expected",
    [
        # Test case 1: Standard path with multiple directories
        ("/home/user/documents/file.txt", ["documents/file.txt"]),
        # Test case 2: Path with only one directory
        ("/documents/file.txt", ["documents/file.txt"]),
        # Test case 3: Path with no directories (just filename)
        ("file.txt", ["file.txt"]),
        # Test case 4: Path with multiple levels and special characters
        ("/home/user/my-docs/special_file!.pdf", ["my-docs/special_file!.pdf"]),
        # Test case 5: Path with trailing slash
        ("/home/user/documents/", ["user/documents"]),
        # Test case 6: Empty path
        ("", [""]),
        # Test case 7: Path with only slashes
        ("///", [""]),
        # Test case 8: Path with dots
        ("/home/user/../documents/./file.txt", ["./file.txt"]),
        # Test case 9: Windows-style path
        ("C:\\Users\\Documents\\file.txt", ["Documents/file.txt"]),
        # Test case 10: Windows path with trailing backslash
        ("C:\\Users\\Documents\\", ["Users/Documents"]),
        # Test case 11: Mixed separators
        ("C:/Users\\Documents/file.txt", ["Documents/file.txt"]),
        # Test case 12: Network path (UNC)
        ("\\\\server\\share\\file.txt", ["share/file.txt"]),
    ],
)
def test_rewrite_file_path(file_path, expected):
    result = rewrite_file_path(file_path)
    assert result == expected


# Additional test for type checking
def test_rewrite_file_path_type():
    result = rewrite_file_path("/home/user/file.txt")
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)
