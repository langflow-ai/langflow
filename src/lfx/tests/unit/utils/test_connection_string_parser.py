import pytest
from lfx.utils.connection_string_parser import transform_connection_string


@pytest.mark.parametrize(
    ("connection_string", "expected"),
    [
        ("protocol:user:password@host", "protocol:user:password@host"),
        ("protocol:user@host", "protocol:user@host"),
        ("protocol:user:pass@word@host", "protocol:user:pass%40word@host"),
        # Password may contain ":" — encode the whole password (RFC 3986 userinfo).
        ("protocol:user:pa:ss:word@host", "protocol:user:pa%3Ass%3Aword@host"),
        # Legacy password may contain "://"; must not be treated as a URL scheme.
        ("protocol:user:p://ss@host", "protocol:user:p%3A%2F%2Fss@host"),
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
        # Colon + slash in the same password must both be encoded.
        (
            "postgresql://user:p:s/s@localhost/db",  # pragma: allowlist secret
            "postgresql://user:p%3As%2Fs@localhost/db",  # pragma: allowlist secret
        ),
        (
            "postgresql://user:pa:ss:word@host/db",  # pragma: allowlist secret
            "postgresql://user:pa%3Ass%3Aword@host/db",  # pragma: allowlist secret
        ),
        # no password: return unchanged
        ("postgresql://user@host:5432/db", "postgresql://user@host:5432/db"),
        ("postgresql+psycopg://user@host:5432/db", "postgresql+psycopg://user@host:5432/db"),
        ("postgresql://@host:5432/db", "postgresql://@host:5432/db"),
        # a password that starts with '//' is still encoded
        (
            "postgresql://user://pw@host:5432/db",  # pragma: allowlist secret
            "postgresql://user:%2F%2Fpw@host:5432/db",  # pragma: allowlist secret
        ),
        # Malformed inputs must not raise
        ("postgresql://localhost:5432/db", "postgresql://localhost:5432/db"),
        ("", ""),
    ],
)
def test_transform_connection_string(connection_string, expected):
    assert transform_connection_string(connection_string) == expected


def test_colon_in_password_was_truncated_before_fix():
    """Regression: rsplit(':', 1) kept only the segment after the last colon.

    A password like ``p:s/s`` was parsed as password ``s/s`` with a leftover
    ``p`` glued to the username, so the ``:`` was never encoded and the ``/``
    alone was — yielding a URL that authenticates with the wrong secret.
    """
    raw = "postgresql://dbuser:p:s/s@db.example:5432/app"  # pragma: allowlist secret
    fixed = transform_connection_string(raw)
    assert fixed == "postgresql://dbuser:p%3As%2Fs@db.example:5432/app"  # pragma: allowlist secret
    # The buggy rsplit form encoded only the trailing fragment:
    buggy = "postgresql://dbuser:p:s%2Fs@db.example:5432/app"  # pragma: allowlist secret
    assert fixed != buggy
