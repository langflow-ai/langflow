"""Tests for langflow.schema.encoders module."""

from datetime import datetime, timezone

from langflow.schema.encoders import CUSTOM_ENCODERS, encode_callable, encode_datetime


class TestEncodeCallable:
    def test_named_function(self):
        def my_func():
            pass

        assert encode_callable(my_func) == "my_func"

    def test_lambda(self):
        f = lambda x: x  # noqa: E731
        assert encode_callable(f) == "<lambda>"

    def test_class_method(self):
        class MyClass:
            def method(self):
                pass

        assert encode_callable(MyClass.method) == "method"

    def test_object_without_name(self):
        class Callable:
            def __call__(self):
                pass

            def __str__(self):
                return "custom_str"

        # Remove __name__ if it exists
        obj = Callable()
        result = encode_callable(obj)
        assert result == "custom_str"


class TestEncodeDatetime:
    def test_with_utc(self):
        dt = datetime(2024, 1, 15, 10, 30, 45, tzinfo=timezone.utc)
        assert encode_datetime(dt) == "2024-01-15 10:30:45 UTC"

    def test_without_timezone(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        result = encode_datetime(dt)
        assert "2024-01-15 10:30:45" in result


class TestCustomEncoders:
    def test_has_callable_encoder(self):
        from collections.abc import Callable

        assert Callable in CUSTOM_ENCODERS

    def test_has_datetime_encoder(self):
        assert datetime in CUSTOM_ENCODERS
