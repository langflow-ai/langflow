import pytest
from urllib.parse import quote

@pytest.fixture
def client():
    pass

def transform_connection_string(connection_string):
    db_url_name = connection_string.split("@")[-1]
    password_url = connection_string.split(":")[-1]
    password_string = password_url.replace(f'@{db_url_name}', "")
    encoded_password = quote(password_string)
    protocol_user = connection_string.split(":")[:-1]
    transformed_connection_string = f'{":".join(protocol_user)}:{encoded_password}@{db_url_name}'
    return transformed_connection_string

@pytest.mark.parametrize("connection_string, expected", [
    ("protocol:user:password@host", "protocol:user:password@host"),
    ("protocol:user@host", "protocol:user@host"),
    ("protocol:user:pass@word@host", "protocol:user:pass%40word@host"),
    ("protocol:user:pa:ss:word@host", "protocol:user:pa%3Ass%3Aword@host"),
    ("user:password@host", "user:password%40host@host"),
    ("protocol::password@host", "protocol::password%40host@host"),
    ("protocol:user:password@", "protocol:user:password%40@"),
    ("protocol:user:pa@ss@word@host", "protocol:user:pa%40ss%40word@host"),
])
def test_transform_connection_string(connection_string, expected):
    result = transform_connection_string(connection_string)
    assert result == expected
