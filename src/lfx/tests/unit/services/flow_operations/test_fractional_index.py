"""Fractional positions agree with the shared fixture every implementation runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lfx.services.flow_operations.fractional_index import (
    BASE_62_DIGITS,
    FractionalIndexError,
    generate_key_between,
    generate_n_keys_between,
    is_order_key,
)

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "fractional_index_cases.json").read_text())


def _case_id(case: dict) -> str:
    return f"{case['a']}..{case['b']}" + (f"x{case['n']}" if "n" in case else "")


def test_fixture_uses_the_same_digits():
    assert FIXTURE["digits"] == BASE_62_DIGITS


@pytest.mark.parametrize("case", FIXTURE["between"], ids=_case_id)
def test_key_between(case):
    if "error" in case:
        with pytest.raises(FractionalIndexError, match=f"^{case['error']}$"):
            generate_key_between(case["a"], case["b"])
        return
    key = generate_key_between(case["a"], case["b"])

    assert key == case["expected"]
    assert is_order_key(key)
    assert case["a"] is None or case["a"] < key
    assert case["b"] is None or key < case["b"]


@pytest.mark.parametrize("case", FIXTURE["n_between"], ids=_case_id)
def test_n_keys_between(case):
    keys = generate_n_keys_between(case["a"], case["b"], case["n"])

    assert keys == case["expected"]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


def test_repeated_inserts_at_one_spot_stay_ordered():
    low, high = "a0", "a1"
    for _ in range(50):
        middle = generate_key_between(low, high)
        assert low < middle < high
        high = middle


@pytest.mark.parametrize("key", ["", "a", "a00", "0", "A00000000000000000000000000", None, 5])
def test_invalid_keys(key):
    assert not is_order_key(key)
