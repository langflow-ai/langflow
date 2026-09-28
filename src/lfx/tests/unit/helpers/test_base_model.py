import pytest
from lfx.helpers.base_model import coalesce_bool


# Table cells reach components as-is, so a flag can arrive as a real boolean or
# as whatever string was typed into the cell.
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (False, False),
        ("True", True),
        ("true", True),
        ("TRUE", True),
        (" true ", True),
        ("\ttrue\n", True),
        ("1", True),
        ("t", True),
        ("y", True),
        ("yes", True),
        ("False", False),
        ("false", False),
        (" false ", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("   ", False),
        (1, True),
        (0, False),
        (None, False),
    ],
)
def test_coalesce_bool(value, expected):
    assert coalesce_bool(value) is expected
