from urllib.parse import urlsplit

from lfx.utils.connection_string_parser import transform_connection_string


def test_transform_connection_string_encodes_slash_in_password():
    result = transform_connection_string("postgresql://user:pa/ss@db.example:5432/app")

    assert result == "postgresql://user:pa%2Fss@db.example:5432/app"
    assert urlsplit(result).hostname == "db.example"
