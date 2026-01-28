from lfx.base.io.chat import _extract_model_name


class TestExtractModelName:
    def test_should_return_string_when_input_is_string(self):
        assert _extract_model_name("gpt-4o-mini") == "gpt-4o-mini"

    def test_should_return_name_when_input_is_model_input_list(self):
        model_input = [{"name": "gpt-4o-mini", "icon": "OpenAI", "provider": "OpenAI"}]
        assert _extract_model_name(model_input) == "gpt-4o-mini"

    def test_should_return_name_when_input_is_dict(self):
        model_dict = {"name": "claude-3", "provider": "Anthropic"}
        assert _extract_model_name(model_dict) == "claude-3"

    def test_should_return_none_when_input_is_empty_list(self):
        assert _extract_model_name([]) is None

    def test_should_return_none_when_input_is_none(self):
        assert _extract_model_name(None) is None

    def test_should_return_none_when_list_has_no_name_key(self):
        assert _extract_model_name([{"provider": "OpenAI"}]) is None

    def test_should_return_none_when_dict_has_no_name_key(self):
        assert _extract_model_name({"provider": "OpenAI"}) is None

    def test_should_return_none_when_input_is_integer(self):
        assert _extract_model_name(123) is None
