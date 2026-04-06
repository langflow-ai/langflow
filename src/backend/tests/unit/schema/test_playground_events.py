"""Tests for langflow.schema.playground_events module."""

from uuid import UUID, uuid4

from langflow.schema.playground_events import (
    ErrorEvent,
    InfoEvent,
    MessageEvent,
    PlaygroundEvent,
    TokenEvent,
    WarningEvent,
    create_error,
    create_event_by_type,
    create_info,
    create_message,
    create_token,
    create_warning,
)


class TestPlaygroundEvent:
    def test_default_fields(self):
        e = PlaygroundEvent()
        assert e.format_type == "default"
        assert e.timestamp is not None
        assert "UTC" in e.timestamp

    def test_with_text(self):
        e = PlaygroundEvent(text="hello")
        assert e.text == "hello"

    def test_id_uuid_converted_to_str(self):
        uid = uuid4()
        e = PlaygroundEvent(id=uid)
        assert e.id_ == str(uid)

    def test_id_string_stays_string(self):
        e = PlaygroundEvent(id="my-id")
        assert e.id_ == "my-id"

    def test_id_none(self):
        e = PlaygroundEvent()
        assert e.id_ is None

    def test_timestamp_serialization(self):
        e = PlaygroundEvent(timestamp="2024-01-15T10:30:45")
        d = e.model_dump()
        assert isinstance(d["timestamp"], str)


class TestMessageEvent:
    def test_defaults(self):
        me = MessageEvent(text="hi")
        assert me.category == "message"
        assert me.format_type == "default"
        assert me.error is False
        assert me.edit is False
        assert me.sender_name == "User"

    def test_flow_id_uuid_converted(self):
        uid = uuid4()
        me = MessageEvent(text="t", flow_id=uid)
        assert me.flow_id == str(uid)

    def test_error_flag(self):
        me = MessageEvent(text="err", error=True)
        assert me.error is True

    def test_session_id(self):
        me = MessageEvent(text="t", session_id="sess-123")
        assert me.session_id == "sess-123"


class TestErrorEvent:
    def test_defaults(self):
        ee = ErrorEvent(text="error occurred")
        assert ee.format_type == "error"
        assert ee.category == "error"
        assert ee.background_color == "#FF0000"
        assert ee.text_color == "#FFFFFF"
        assert ee.allow_markdown is False


class TestWarningEvent:
    def test_defaults(self):
        we = WarningEvent(text="warning")
        assert we.format_type == "warning"
        assert we.background_color == "#FFA500"
        assert we.text_color == "#000000"


class TestInfoEvent:
    def test_defaults(self):
        ie = InfoEvent(text="info")
        assert ie.format_type == "info"
        assert ie.background_color == "#0000FF"
        assert ie.text_color == "#FFFFFF"


class TestTokenEvent:
    def test_creation(self):
        te = TokenEvent(chunk="hello", id="tok-1")
        assert te.chunk == "hello"
        assert te.id == "tok-1"
        assert te.timestamp is not None

    def test_uuid_id(self):
        uid = uuid4()
        te = TokenEvent(chunk="c", id=str(uid))
        assert te.id == str(uid)


class TestCreateMessage:
    _TS = "2024-01-15 10:30:45 UTC"
    _SENDER = "User"
    _SENDER_NAME = "User"

    def test_basic(self):
        result = create_message("hello", timestamp=self._TS, sender=self._SENDER, sender_name=self._SENDER_NAME)
        assert isinstance(result, MessageEvent)
        assert result.text == "hello"
        assert result.category == "message"

    def test_with_error(self):
        result = create_message("err", error=True, category="error", timestamp=self._TS, sender=self._SENDER, sender_name=self._SENDER_NAME)
        assert result.error is True
        assert result.category == "error"

    def test_with_session_id(self):
        result = create_message("hi", session_id="s1", timestamp=self._TS, sender=self._SENDER, sender_name=self._SENDER_NAME)
        assert result.session_id == "s1"

    def test_with_flow_id(self):
        uid = uuid4()
        result = create_message("hi", flow_id=uid, timestamp=self._TS, sender=self._SENDER, sender_name=self._SENDER_NAME)
        assert result.flow_id == str(uid)


class TestCreateError:
    _TS = "2024-01-15 10:30:45 UTC"

    def test_basic(self):
        result = create_error("something broke", timestamp=self._TS)
        assert isinstance(result, ErrorEvent)
        assert result.text == "something broke"

    def test_with_traceback(self):
        result = create_error("error", traceback="Traceback...", timestamp=self._TS)
        assert result.content_blocks is not None
        assert len(result.content_blocks) == 1

    def test_without_traceback(self):
        result = create_error("error", timestamp=self._TS)
        # No traceback means content_blocks stays None
        assert result.content_blocks is None


class TestCreateWarning:
    def test_basic(self):
        result = create_warning("watch out")
        assert isinstance(result, WarningEvent)
        assert result.text == "watch out"


class TestCreateInfo:
    def test_basic(self):
        result = create_info("fyi")
        assert isinstance(result, InfoEvent)
        assert result.text == "fyi"


class TestCreateToken:
    def test_basic(self):
        result = create_token("tok", "id-1")
        assert isinstance(result, TokenEvent)
        assert result.chunk == "tok"


class TestCreateEventByType:
    _MSG_KWARGS = {"text": "hello", "sender": "User", "sender_name": "User", "timestamp": "2024-01-15 10:30:45 UTC"}

    def test_message(self):
        result = create_event_by_type("message", **self._MSG_KWARGS)
        assert isinstance(result, MessageEvent)

    def test_error(self):
        result = create_event_by_type("error", text="err", timestamp="2024-01-15 10:30:45 UTC")
        assert isinstance(result, ErrorEvent)

    def test_warning(self):
        result = create_event_by_type("warning", message="warn")
        assert isinstance(result, WarningEvent)

    def test_info(self):
        result = create_event_by_type("info", message="info msg")
        assert isinstance(result, InfoEvent)

    def test_token(self):
        result = create_event_by_type("token", chunk="c", id="1")
        assert isinstance(result, TokenEvent)

    def test_unknown_type_returns_dict(self):
        result = create_event_by_type("nonexistent", foo="bar")
        assert isinstance(result, dict)
        assert result == {"foo": "bar"}

    def test_extra_params_filtered(self):
        result = create_event_by_type("message", text="hi", unknown_param="x", sender="User", sender_name="User", timestamp="2024-01-15 10:30:45 UTC")
        assert isinstance(result, MessageEvent)
        assert result.text == "hi"
