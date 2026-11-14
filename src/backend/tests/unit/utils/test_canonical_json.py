"""Unit tests for langflow.utils.canonical_json."""

from __future__ import annotations

import hashlib
import json

from langflow.utils.canonical_json import canonical_json_bytes, canonical_json_digest


def test_bytes_sorts_object_keys():
    # insertion order must not affect output bytes
    assert canonical_json_bytes({"b": 1, "a": 2}) == canonical_json_bytes({"a": 2, "b": 1})


def test_bytes_uses_compact_separators():
    out = canonical_json_bytes({"a": 1, "b": [1, 2, 3]})
    assert b", " not in out
    assert out == b'{"a":1,"b":[1,2,3]}'


def test_bytes_ensure_ascii_false_by_default():
    out = canonical_json_bytes({"name": "中文"})
    assert "中文".encode() in out  # raw UTF-8, not \uXXXX escapes


def test_bytes_ensure_ascii_true_escapes_non_ascii():
    out = canonical_json_bytes({"name": "中文"}, ensure_ascii=True)
    assert "中文".encode() not in out
    assert b"\\u4e2d\\u6587" in out


def test_bytes_custom_separators():
    out = canonical_json_bytes({"a": 1, "b": 2}, separators=(", ", ": "))
    assert out == b'{"a": 1, "b": 2}'


def test_digest_is_hex_sha256_of_bytes():
    value = {"z": 1, "a": 2}
    expected = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    assert canonical_json_digest(value) == expected
    assert len(canonical_json_digest(value)) == 64


def test_digest_deterministic_across_order():
    assert canonical_json_digest({"x": 1, "y": 2}) == canonical_json_digest({"y": 2, "x": 1})


def test_digest_changes_with_value():
    assert canonical_json_digest({"a": 1}) != canonical_json_digest({"a": 2})


def test_bytes_nested_structures():
    value = {"a": [{"c": 3, "b": 2}], "z": {"y": {"x": 1}}}
    out = canonical_json_bytes(value)
    # deep keys sorted too
    assert out == json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def test_bytes_default_callable_for_non_json_types():
    class _Obj:
        def __repr__(self):
            return "obj"

    out = canonical_json_bytes({"k": _Obj()}, default=lambda o: f"<{o.__repr__()}>")
    assert b'"<obj>"' in out


def test_bytes_scalar_inputs():
    assert canonical_json_bytes("hello") == b'"hello"'
    assert canonical_json_bytes(42) == b"42"
    assert canonical_json_bytes([1, 2, 3]) == b"[1,2,3]"
