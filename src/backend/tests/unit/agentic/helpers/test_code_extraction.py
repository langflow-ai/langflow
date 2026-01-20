"""Tests for Python code extraction from markdown responses."""

from langflow.agentic.helpers.code_extraction import (
    _find_code_blocks,
    _find_component_code,
    _find_unclosed_code_block,
    extract_python_code,
)

VALID_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output
from langflow.schema.message import Message


class HelloWorldComponent(Component):
    display_name = "Hello World"
    description = "A simple hello world component."

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
    ]

    outputs = [
        Output(display_name="Output", name="output", method="process"),
    ]

    def process(self) -> Message:
        return Message(text=f"Hello, {self.input_value}!")
"""


class TestExtractPythonCode:
    """Tests for extract_python_code function."""

    def test_should_extract_code_from_closed_python_block(self):
        text = f"Here is the component:\n\n```python\n{VALID_COMPONENT_CODE}\n```\n\nLet me know."

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result
        assert "from langflow.custom import Component" in result

    def test_should_extract_code_from_unclosed_python_block(self):
        text = f"Here is the component:\n\n```python\n{VALID_COMPONENT_CODE}"

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_should_extract_code_with_text_before_block(self):
        text = f"""I apologize for the rate limit issue.

Here's a component:

```python
{VALID_COMPONENT_CODE}
```"""

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_should_extract_from_generic_code_block(self):
        text = f"Here is the code:\n\n```\n{VALID_COMPONENT_CODE}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_should_return_none_when_no_code_blocks(self):
        text = "This is just regular text without any code blocks."

        result = extract_python_code(text)

        assert result is None

    def test_should_return_none_for_empty_text(self):
        result = extract_python_code("")

        assert result is None

    def test_should_prefer_component_code_over_other_code(self):
        other_code = "print('hello world')"
        text = f"""Here's a simple print:

```python
{other_code}
```

And here's the component:

```python
{VALID_COMPONENT_CODE}
```"""

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result
        assert result.strip() != other_code

    def test_should_handle_code_with_special_characters(self):
        code_with_specials = """from langflow.custom import Component

class SpecialComponent(Component):
    display_name = "Special < > & Characters"
    description = "Handles 'quotes' and \\"escaped\\" chars"
"""
        text = f"```python\n{code_with_specials}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "SpecialComponent" in result

    def test_should_handle_case_insensitive_python_tag(self):
        for tag in ["```python", "```Python", "```PYTHON", "```PyThOn"]:
            text = f"{tag}\n{VALID_COMPONENT_CODE}\n```"

            result = extract_python_code(text)

            assert result is not None, f"Failed for tag: {tag}"


class TestFindCodeBlocks:
    """Tests for _find_code_blocks helper function."""

    def test_should_find_closed_python_blocks(self):
        text = "```python\ncode1\n```\n\nText\n\n```python\ncode2\n```"

        result = _find_code_blocks(text)

        assert len(result) == 2
        assert "code1" in result[0]
        assert "code2" in result[1]

    def test_should_find_unclosed_blocks_as_fallback(self):
        text = "Some text\n```python\ncode_here"

        result = _find_code_blocks(text)

        assert len(result) == 1
        assert "code_here" in result[0]

    def test_should_return_empty_list_for_no_blocks(self):
        text = "Just regular text"

        result = _find_code_blocks(text)

        assert result == []


class TestFindUnclosedCodeBlock:
    """Tests for _find_unclosed_code_block helper function."""

    def test_should_find_unclosed_python_block(self):
        text = "Text before\n```python\ncode_content"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "code_content" in result[0]

    def test_should_find_unclosed_generic_block(self):
        text = "Text\n```\nsome code"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "some code" in result[0]

    def test_should_return_empty_for_no_code_blocks(self):
        text = "Just regular text"

        result = _find_unclosed_code_block(text)

        assert result == []

    def test_should_handle_multiple_backticks_in_code(self):
        text = "```python\ncode with `inline` backticks"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "`inline`" in result[0]


class TestFindComponentCode:
    """Tests for _find_component_code helper function."""

    def test_should_find_component_code_in_matches(self):
        matches = ["print('hello')", VALID_COMPONENT_CODE]

        result = _find_component_code(matches)

        assert result is not None
        assert "HelloWorldComponent" in result

    def test_should_return_none_when_no_component(self):
        matches = ["print('hello')", "x = 1 + 2"]

        result = _find_component_code(matches)

        assert result is None

    def test_should_return_first_component_when_multiple(self):
        first_component = """from langflow.custom import Component

class FirstComponent(Component):
    pass
"""
        second_component = """from langflow.custom import Component

class SecondComponent(Component):
    pass
"""
        matches = [first_component, second_component]

        result = _find_component_code(matches)

        assert result is not None
        assert "FirstComponent" in result
        assert "SecondComponent" not in result


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_should_handle_windows_line_endings(self):
        code = VALID_COMPONENT_CODE.replace("\n", "\r\n")
        text = f"```python\r\n{code}\r\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "HelloWorldComponent" in result

    def test_should_handle_mixed_line_endings(self):
        text = f"Text\r\n```python\n{VALID_COMPONENT_CODE}\r\n```"

        result = extract_python_code(text)

        assert result is not None

    def test_should_handle_unicode_in_code(self):
        unicode_code = """from langflow.custom import Component

class UnicodeComponent(Component):
    display_name = "Unicode éàü"
    description = "Handles 中文 and 😀"
"""
        text = f"```python\n{unicode_code}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "Unicode" in result

    def test_should_handle_very_long_code(self):
        long_code = VALID_COMPONENT_CODE + "\n" * 1000 + "# End of long code"
        text = f"```python\n{long_code}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "HelloWorldComponent" in result
        assert "End of long code" in result

    def test_should_handle_empty_code_block(self):
        text = "```python\n```"

        result = extract_python_code(text)

        assert result == "" or result is None

    def test_should_handle_whitespace_only_code_block(self):
        text = "```python\n   \n\t\n```"

        result = extract_python_code(text)

        assert result is None or result.strip() == ""
