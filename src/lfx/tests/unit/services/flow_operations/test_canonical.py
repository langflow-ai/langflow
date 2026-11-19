"""Canonical equality of JSON values."""

from __future__ import annotations

import itertools

import pytest
from lfx.services.flow_operations import FlowDataValidationError, values_equal
from lfx.services.flow_operations.canonical import canonical_json

SAMPLES = [
    None,
    True,
    False,
    0,
    0.0,
    -0.0,
    1,
    1.0,
    1.5,
    2**53,
    2**53 + 1,
    float(2**53),
    1e21,
    "",
    "a",
    "1",
    [],
    [1],
    [1.0],
    [1, 2],
    [2, 1],
    {},
    {"a": 1},
    {"a": 1.0},
    {"b": 1},
    {"a": 1, "b": [True, None]},
    {"b": [True, None], "a": 1},
    {"a": {"b": {"c": 0}}},
    {"a": {"b": {"c": -0.0}}},
    {"a": {"b": {"c": 1}}},
]


@pytest.mark.parametrize(("left", "right"), list(itertools.product(SAMPLES, repeat=2)))
def test_equality_matches_the_canonical_form(left, right):
    assert values_equal(left, right) == (canonical_json(left) == canonical_json(right))


def test_numbers_compare_as_the_doubles_javascript_holds():
    assert values_equal(1, 1.0)
    assert values_equal(0, -0.0)
    assert values_equal(2**53 + 1, 2**53)
    assert not values_equal(left=True, right=1)


@pytest.mark.parametrize(
    ("left", "right"),
    [(float("nan"), 1.0), (1.0, float("inf")), ([1, float("-inf")], [1, 2])],
)
def test_non_finite_numbers_are_not_json(left, right):
    with pytest.raises(FlowDataValidationError, match="not valid JSON numbers"):
        values_equal(left, right)


def test_object_keys_must_be_strings():
    with pytest.raises(FlowDataValidationError, match="is not a string"):
        values_equal({1: "a"}, {"1": "a"})
