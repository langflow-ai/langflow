import pytest
from langflow.utils import util_strings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("sqlite:///test.db", True),
        ("sqlite:////var/folders/test.db", True),
        ("sqlite:///:memory:", True),
        ("postgresql://user:pass@localhost/dbname", True),

        ("", False),
        (" invalid ", False),
        ("not_a_url", False),
        (None, False),
        ("invalid://database", False),
    ]
)


def test_is_valid_database_url(value, expected):
    assert util_strings.is_valid_database_url(value) == expected
