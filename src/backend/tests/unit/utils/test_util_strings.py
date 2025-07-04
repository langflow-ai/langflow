import pytest
from langflow.utils import util_strings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sqlite:///test.db", True),
        ("sqlite:////var/folders/test.db", True),
        ("sqlite:///:memory:", True),
        ("sqlite+aiosqlite:////var/folders/test.db", True),
        ("postgresql://user:pass@localhost/dbname", True),
        ("postgresql+psycopg2://scott:tiger@localhost:5432/mydatabase", True),
        ("postgresql+pg8000://dbuser:kx%40jj5%2Fg@pghost10/appdb", True),
        ("mysql://user:pass@localhost/dbname", True),
        ("mysql+mysqldb://scott:tiger@localhost/foo", True),
        ("mysql+pymysql://scott:tiger@localhost/foo", True),
        ("oracle://scott:tiger@localhost:1521/?service_name=freepdb1", True),
        ("oracle+cx_oracle://scott:tiger@tnsalias", True),
        ("oracle+oracledb://scott:tiger@localhost:1521/?service_name=freepdb1", True),
        ("", False),
        (" invalid ", False),
        ("not_a_url", False),
        (None, False),
        ("invalid://database", False),
        ("invalid://:@/test", False),
    ],
)
def test_is_valid_database_url(value, expected):
    assert util_strings.is_valid_database_url(value) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Basic case: single space -> underscore, to lowercase
        ("Some Name", "some_name"),
        # # Multiple spaces -> single underscore
        ("Some    Name", "some_name"),
        # # Non-alphanumeric characters (dash) are removed
        ("Some-Name", "somename"),
        # # Digits at start -> prepend underscore
        ("4some name", "_4some_name"),
        # # Special symbols ($) are removed
        ("some$name", "somename"),
        # # Mixed whitespace and symbols
        ("   Some!!Name###  ", "_somename_"),
        # # Already valid Pythonic string -> stays the same
        ("some_name", "some_name"),
        # # Empty string -> stays empty
        ("", ""),
        # # Single digit -> underscore + digit
        ("1", "_1"),
        # # Mixed digits and letters
        ("123abc", "_123abc"),
    ],
)
def test_to_pythonic_variable_name(name, expected):
    assert util_strings.to_pythonic_variable_name(name) == expected
