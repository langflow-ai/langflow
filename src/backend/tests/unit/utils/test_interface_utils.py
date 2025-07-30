import pytest
from langflow.interface.utils import extract_input_variables_from_prompt


@pytest.mark.parametrize(
    ("prompt", "expected"),
    [
        # Basic variable extraction
        ("Hello {name}!", ["name"]),
        ("Hi {name}, you are {age} years old", ["name", "age"]),
        # Empty prompt
        ("", []),
        ("No variables here", []),
        # Duplicate variables
        ("Hello {name}! How are you {name}?", ["name"]),
        # Whitespace handling - Formatter preserves whitespace in field names
        ("Hello { name }!", [" name "]),
        ("Hi {  name  }, bye", ["  name  "]),
        # Multiple braces (escaping)
        ("Escaped {{not_a_var}}", []),
        ("Mixed {{escaped}} and {real_var}", ["real_var"]),
        ("Double escaped {{{{not_this}}}}", []),
        # Complex cases
        ("Hello {name}! Your score is {{4 + 5}}, age: {age}", ["name", "age"]),
        ("Nested {{obj['key']}} with {normal_var}", ["normal_var"]),
        ("Template {{user.name}} with {id} and {type}", ["id", "type"]),
        # Edge cases
        ("{single}", ["single"]),
        ("{{double}}", []),
        ("{{{}}}", []),
        # Multiple variables with various spacing
        (
            """
        Multi-line with {var1}
        and {var2} plus
        {var3} at the end
        """,
            ["var1", "var2", "var3"],
        ),
    ],
)
def test_extract_input_variables(prompt, expected):
    """Test the extract_input_variables_from_prompt function with various cases."""
    result = extract_input_variables_from_prompt(prompt)
    assert sorted(result) == sorted(expected), f"Failed for prompt: {prompt}"


@pytest.mark.parametrize(
    ("prompt", "expected_error"),
    [
        # Malformed format strings that should raise ValueError
        ("}{", "Single '}' encountered in format string"),
        ("{incomplete", "expected '}' before end of string"),
        ("incomplete}", "Single '}' encountered in format string"),
    ],
)
def test_extract_input_variables_malformed(prompt, expected_error):
    """Test that malformed format strings raise ValueError."""
    with pytest.raises(ValueError, match=expected_error):
        extract_input_variables_from_prompt(prompt)
