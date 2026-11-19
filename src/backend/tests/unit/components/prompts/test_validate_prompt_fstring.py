"""f-string prompt variables: {{name}} is an escaped literal, {name} is a variable."""

import pytest
from lfx.base.prompts.api_utils import validate_prompt


@pytest.mark.parametrize(
    ("template", "expected"),
    [
        pytest.param("{a}", ["a"], id="variable"),
        pytest.param("{{a}}", [], id="escaped-only"),
        pytest.param("{a} and {{a}}", ["a"], id="variable-and-escaped-same-name"),
        pytest.param("{{a}} then {a}", ["a"], id="escaped-first"),
        pytest.param("{{{a}}}", ["a"], id="variable-inside-literal-braces"),
        pytest.param("{a} {{b}}", ["a"], id="escaped-other-name"),
    ],
)
def test_fstring_variables(template, expected):
    assert validate_prompt(template) == expected
