import pytest
from langflow.base.data.utils import format_directory_path


@pytest.mark.parametrize(
    ("input_path", "expected"),
    [
        # Test case 1: Standard path with no newlines (no change expected)
        ("/home/user/documents/file.txt", "/home/user/documents/file.txt"),
        # Test case 2: Path with newline character (replace \n with \\n)
        ("/home/user/docu\nments/file.txt", "/home/user/docu\\nments/file.txt"),
        # Test case 3: Path with multiple newline characters
        ("/home/user/\ndocu\nments/file.txt", "/home/user/\\ndocu\\nments/file.txt"),
        # Test case 4: Path with only newline characters
        ("\n\n\n", "\\n\\n\\n"),
        # Test case 5: Empty path (as per the original function, this remains an empty string)
        ("", ""),
        # Test case 6: Path with mixed newlines and other special characters
        ("/home/user/my-\ndocs/special_file!.pdf", "/home/user/my-\\ndocs/special_file!.pdf"),
        # Test case 7: Windows-style path with newline
        ("C:\\Users\\\nDocuments\\file.txt", "C:\\Users\\\\nDocuments\\file.txt"),  # No conversion of backslashes
        # Test case 8: Path with trailing newline
        ("/home/user/documents/\n", "/home/user/documents/\\n"),
        # Test case 9: Path with leading newline
        ("\n/home/user/documents/", "\\n/home/user/documents/"),
        # Test case 10: Path with multiple consecutive newlines
        ("/home/user/docu\n\nments/file.txt", "/home/user/docu\\n\\nments/file.txt"),
        # Test case 11: Windows-style path (backslashes remain unchanged)
        ("C:\\Users\\Documents\\file.txt", "C:\\Users\\Documents\\file.txt"),
        # Test case 12: Windows path with trailing backslash
        ("C:\\Users\\Documents\\", "C:\\Users\\Documents\\"),
        # Test case 13: Mixed separators (leave as is)
        ("C:/Users\\Documents/file.txt", "C:/Users\\Documents/file.txt"),
        # Test case 14: Network path (UNC) (leave backslashes as is)
        ("\\\\server\\share\\file.txt", "\\\\server\\share\\file.txt"),
    ],
)
def test_format_directory_path(input_path, expected):
    result = format_directory_path(input_path)
    assert result == expected


# Additional test for type checking
def test_format_directory_path_type():
    result = format_directory_path("/home/user/file.txt")
    assert isinstance(result, str)
