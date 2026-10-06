import pytest
from lfx.utils.connection_string_parser import transform_connection_string


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
        # '/' is left alone by quote()'s default safe='/' and must be encoded explicitly
        ("protocol:user:p/ss@host", "protocol:user:p%2Fss@host"),
        ("protocol:user:a/b/c@host", "protocol:user:a%2Fb%2Fc@host"),
        (
            "postgresql://user:p@ss/w0rd@host:5432/db",  # pragma: allowlist secret
            "postgresql://user:p%40ss%2Fw0rd@host:5432/db",  # pragma: allowlist secret
        ),
        # no password: the last ':' is the scheme separator, so there is nothing to encode
        ("postgresql://user@host:5432/db", "postgresql://user@host:5432/db"),
        ("postgresql+psycopg://user@host:5432/db", "postgresql+psycopg://user@host:5432/db"),
        ("postgresql://@host:5432/db", "postgresql://@host:5432/db"),
        # a password that starts with '//' is still encoded
        (
            "postgresql://user://pw@host:5432/db",  # pragma: allowlist secret
            "postgresql://user:%2F%2Fpw@host:5432/db",  # pragma: allowlist secret
        ),
    ],
)
def test_transform_connection_string(connection_string, expected):
    assert transform_connection_string(connection_string) == expected
