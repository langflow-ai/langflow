import pytest

from lfx.base.data.utils import format_directory_path


@pytest.mark.parametrize(
    ("input_path", "expected"),
    [
        # Test case 1: Standard path with no newlines
        ("/home/user/documents/file.txt", "/home/user/documents/file.txt"),
        # Test case 2: Path with newline character
        ("/home/user/docu\nments/file.txt", "/home/user/docu\\nments/file.txt"),
        # Test case 3: Path with multiple newline characters
        ("/home/user/\ndocu\nments/file.txt", "/home/user/\\ndocu\\nments/file.txt"),
        # Test case 4: Path with only newline characters
        ("\n\n\n", "\\n\\n\\n"),
        # Test case 5: Empty path
        ("", ""),
        # Test case 6: Path with mixed newlines and other special characters
        ("/home/user/my-\ndocs/special_file!.pdf", "/home/user/my-\\ndocs/special_file!.pdf"),
        # Test case 7: Windows-style path with newline
        ("C:\\Users\\\nDocuments\\file.txt", "C:\\Users\\\\nDocuments\\file.txt"),
        # Test case 8: Path with trailing newline
        ("/home/user/documents/\n", "/home/user/documents/\\n"),
        # Test case 9: Path with leading newline
        ("\n/home/user/documents/", "\\n/home/user/documents/"),
        # Test case 10: Path with multiple consecutive newlines
        ("/home/user/docu\n\nments/file.txt", "/home/user/docu\\n\\nments/file.txt"),
    ],
)
def test_format_directory_path(input_path, expected):
    result = format_directory_path(input_path)
    assert result == expected


# Additional test for type checking
def test_format_directory_path_type():
    result = format_directory_path("/home/user/file.txt")
    assert isinstance(result, str)
