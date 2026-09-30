from langflow.services.database.utils import normalize_string_or_none


class TestNormalizeStringOrNone:
    def test_none_returns_none(self):
        assert normalize_string_or_none(None) is None

    def test_empty_returns_none(self):
        assert normalize_string_or_none("") is None

    def test_whitespace_returns_none(self):
        assert normalize_string_or_none("   ") is None

    def test_strips_and_returns(self):
        assert normalize_string_or_none("  hello  ") == "hello"

    def test_non_blank_passthrough(self):
        assert normalize_string_or_none("hello") == "hello"
