from lfx.custom.custom_component.base_component import BaseComponent


def test_infers_is_input_from_name_chatinput():
    class Dummy:
        name = "ChatInput"
        display_name = "Anything"
        is_input = None
        is_output = None

    cfg = BaseComponent.get_template_config(Dummy())
    assert cfg.get("is_input") is True


def test_infers_is_input_from_display_name_chat_input():
    class Dummy:
        name = "Anything"
        display_name = "Chat Input"
        is_input = None
        is_output = None

    cfg = BaseComponent.get_template_config(Dummy())
    assert cfg.get("is_input") is True


def test_does_not_override_explicit_is_input_false():
    class Dummy:
        name = "ChatInput"
        display_name = "Chat Input"
        is_input = False
        is_output = None

    cfg = BaseComponent.get_template_config(Dummy())
    assert cfg.get("is_input") is False


def test_infers_is_output_from_display_name_text_output():
    class Dummy:
        name = "Anything"
        display_name = "Text Output"
        is_input = None
        is_output = None

    cfg = BaseComponent.get_template_config(Dummy())
    assert cfg.get("is_output") is True
