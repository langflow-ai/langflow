from lfx.utils.secrets import is_secret_value, secret_value_to_str, unwrap_secret_value
from pydantic import SecretStr
from pydantic.v1 import SecretStr as SecretStrV1


class NestedSecret:
    def __init__(self, value):
        self.value = value

    def get_secret_value(self):
        return self.value


def test_unwrap_secret_value_supports_pydantic_v1_and_v2():
    assert unwrap_secret_value(SecretStr("v2-secret")) == "v2-secret"
    assert unwrap_secret_value(SecretStrV1("v1-secret")) == "v1-secret"


def test_unwrap_secret_value_unwraps_nested_secret_like_values():
    assert unwrap_secret_value(NestedSecret(SecretStr("nested-secret"))) == "nested-secret"


def test_secret_value_to_str_handles_none_and_stripping():
    assert secret_value_to_str(None) is None
    assert secret_value_to_str("  literal  ") == "  literal  "
    assert secret_value_to_str("  literal  ", strip=True) == "literal"


def test_is_secret_value_uses_secret_protocol():
    assert is_secret_value(SecretStr("secret"))
    assert not is_secret_value("secret")
