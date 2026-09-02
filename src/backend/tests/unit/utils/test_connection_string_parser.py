from urllib.parse import urlsplit

import pytest
from langflow.utils.connection_string_parser import transform_connection_string


@pytest.mark.parametrize(
    ("connection_string", "expected"),
    [
        ("protocol:user:password@host", "protocol:user:password@host"),
        ("protocol:user@host", "protocol:user@host"),
        ("protocol:user:pass@word@host", "protocol:user:pass%40word@host"),
        ("protocol:user:pa:ss:word@host", "protocol:user:pa:ss:word@host"),
        ("user:password@host", "user:password@host"),
        ("protocol::password@host", "protocol::password@host"),
        ("protocol:user:password@", "protocol:user:password@"),
        ("protocol:user:pa@ss@word@host", "protocol:user:pa%40ss%40word@host"),
    ],
)
def test_transform_connection_string(connection_string, expected):
    result = transform_connection_string(connection_string)
    assert result == expected


def test_transform_connection_string_encodes_slash_in_password():
    result = transform_connection_string("postgresql://user:pa/ss@db.example:5432/app")

    assert result == "postgresql://user:pa%2Fss@db.example:5432/app"
    assert urlsplit(result).hostname == "db.example"
