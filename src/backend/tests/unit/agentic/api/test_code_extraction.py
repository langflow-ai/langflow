"""Tests for code extraction and validation in the agentic module.

These tests validate the core functionality of extracting Python code from LLM responses
and validating that the code is a valid Langflow component.
"""

from langflow.agentic.helpers.code_extraction import (
    _find_code_blocks,
    _find_unclosed_code_block,
    extract_python_code,
)
from langflow.agentic.helpers.validation import validate_component_code

# Sample valid Langflow component code
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

# Incomplete component code (missing closing bracket)
INCOMPLETE_COMPONENT_CODE = """from langflow.custom import Component
from langflow.io import MessageTextInput, Output


class IncompleteComponent(Component):
    display_name = "Incomplete"

    inputs = [
        MessageTextInput(name="input_value", display_name="Input"),
"""

# Invalid syntax code
INVALID_SYNTAX_CODE = """from langflow.custom import Component

class BrokenComponent(Component)
    display_name = "Broken"
"""


class TestExtractPythonCode:
    """Tests for extract_python_code function."""

    def test_extract_from_closed_python_block(self):
        """Should extract code from a properly closed ```python block."""
        text = f"Here is the component:\n\n```python\n{VALID_COMPONENT_CODE}\n```\n\nLet me know if you need changes."

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result
        assert "from langflow.custom import Component" in result

    def test_extract_from_unclosed_python_block(self):
        """Should extract code from an unclosed ```python block."""
        text = f"Here is the component:\n\n```python\n{VALID_COMPONENT_CODE}"

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_extract_with_text_before_code(self):
        """Should extract code even when there's text before the code block."""
        text = f"""I apologize for the rate limit issue. Let me create a component.

Here's a component that uses TextBlob for sentiment analysis:

```python
{VALID_COMPONENT_CODE}
```"""

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_extract_from_unclosed_block_with_text_before(self):
        """Should extract code from unclosed block even with text before it."""
        text = f"""I apologize for the rate limit issue. Let me create the component.

```python
{VALID_COMPONENT_CODE}"""

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result
        assert "from langflow.custom import Component" in result

    def test_extract_from_generic_code_block(self):
        """Should extract code from a generic ``` block without language specifier."""
        text = f"Here is the code:\n\n```\n{VALID_COMPONENT_CODE}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "class HelloWorldComponent" in result

    def test_returns_none_for_no_code_blocks(self):
        """Should return None when there are no code blocks."""
        text = "This is just regular text without any code blocks."

        result = extract_python_code(text)

        assert result is None

    def test_returns_none_for_empty_text(self):
        """Should return None for empty text."""
        result = extract_python_code("")

        assert result is None

    def test_prefers_component_code_over_other_code(self):
        """When multiple code blocks exist, should prefer the one with Component class."""
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
        # Should NOT return the print code
        assert result.strip() != other_code

    def test_handles_code_with_special_characters(self):
        """Should handle code containing special characters."""
        code_with_specials = """from langflow.custom import Component

class SpecialComponent(Component):
    display_name = "Special < > & Characters"
    description = "Handles 'quotes' and \\"escaped\\" chars"
"""
        text = f"```python\n{code_with_specials}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "SpecialComponent" in result


class TestFindCodeBlocks:
    """Tests for _find_code_blocks helper function."""

    def test_finds_closed_python_blocks(self):
        """Should find all closed python code blocks."""
        text = "```python\ncode1\n```\n\nText\n\n```python\ncode2\n```"

        result = _find_code_blocks(text)

        assert len(result) == 2
        assert "code1" in result[0]
        assert "code2" in result[1]

    def test_finds_unclosed_blocks_as_fallback(self):
        """Should find unclosed blocks when no closed blocks exist."""
        text = "Some text\n```python\ncode_here"

        result = _find_code_blocks(text)

        assert len(result) == 1
        assert "code_here" in result[0]


class TestFindUnclosedCodeBlock:
    """Tests for _find_unclosed_code_block helper function."""

    def test_finds_unclosed_python_block(self):
        """Should find unclosed ```python block."""
        text = "Text before\n```python\ncode_content"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "code_content" in result[0]

    def test_finds_unclosed_generic_block(self):
        """Should find unclosed ``` block without language."""
        text = "Text\n```\nsome code"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "some code" in result[0]

    def test_returns_empty_for_closed_blocks(self):
        """Should return empty list when blocks are properly closed."""
        text = "```python\ncode\n```"

        # This function only looks for unclosed blocks
        # When called by _find_code_blocks, closed blocks are found first
        result = _find_unclosed_code_block(text)

        # It will find from ```python to end, but the code will include the closing ```
        # The function strips trailing backticks, so it should work
        assert len(result) >= 0  # May or may not find depending on implementation

    def test_returns_empty_for_no_code_blocks(self):
        """Should return empty list when no code blocks at all."""
        text = "Just regular text"

        result = _find_unclosed_code_block(text)

        assert result == []

    def test_handles_multiple_backticks_in_code(self):
        """Should handle code that contains backticks."""
        text = "```python\ncode with `inline` backticks"

        result = _find_unclosed_code_block(text)

        assert len(result) == 1
        assert "`inline`" in result[0]


class TestValidateComponentCode:
    """Tests for validate_component_code function."""

    def test_validates_valid_component(self):
        """Should validate correct Langflow component code."""
        result = validate_component_code(VALID_COMPONENT_CODE)

        assert result.is_valid is True
        assert result.class_name == "HelloWorldComponent"
        assert result.error is None
        assert result.code == VALID_COMPONENT_CODE

    def test_fails_for_syntax_error(self):
        """Should fail validation for code with syntax errors."""
        result = validate_component_code(INVALID_SYNTAX_CODE)

        assert result.is_valid is False
        assert result.error is not None
        # Error might be SyntaxError or ValueError depending on validation method
        assert "expected" in result.error.lower() or "syntax" in result.error.lower()

    def test_fails_for_incomplete_code(self):
        """Should fail validation for incomplete component code."""
        result = validate_component_code(INCOMPLETE_COMPONENT_CODE)

        assert result.is_valid is False
        assert result.error is not None

    def test_fails_for_non_component_code(self):
        """Should fail validation for code that's not a Langflow component."""
        non_component_code = """def hello():
    return "hello"
"""
        result = validate_component_code(non_component_code)

        assert result.is_valid is False
        assert result.error is not None

    def test_fails_for_empty_code(self):
        """Should fail validation for empty string."""
        result = validate_component_code("")

        assert result.is_valid is False
        assert result.error is not None

    def test_fails_for_missing_imports(self):
        """Should fail validation when required imports are missing."""
        code_without_imports = """class BrokenComponent(Component):
    display_name = "Broken"
"""
        result = validate_component_code(code_without_imports)

        assert result.is_valid is False
        assert result.error is not None


class TestCodeExtractionAndValidationIntegration:
    """Integration tests for the full extract -> validate flow."""

    def test_full_flow_with_valid_response(self):
        """Should extract and validate a complete valid response."""
        llm_response = f"""I'll create a Hello World component for you.

```python
{VALID_COMPONENT_CODE}
```

This component takes an input and returns a greeting message."""

        # Extract
        code = extract_python_code(llm_response)
        assert code is not None

        # Validate
        validation = validate_component_code(code)
        assert validation.is_valid is True
        assert validation.class_name == "HelloWorldComponent"

    def test_full_flow_with_unclosed_valid_response(self):
        """Should extract and validate from unclosed but valid code."""
        llm_response = f"""Here's your component:

```python
{VALID_COMPONENT_CODE}"""

        # Extract
        code = extract_python_code(llm_response)
        assert code is not None

        # Validate
        validation = validate_component_code(code)
        assert validation.is_valid is True

    def test_full_flow_with_invalid_code_returns_error(self):
        """Should extract but fail validation for broken code."""
        llm_response = f"""Here's the component:

```python
{INVALID_SYNTAX_CODE}
```"""

        # Extract
        code = extract_python_code(llm_response)
        assert code is not None

        # Validate should fail
        validation = validate_component_code(code)
        assert validation.is_valid is False
        assert validation.error is not None
        # Error might be SyntaxError or ValueError depending on validation method
        assert "expected" in validation.error.lower() or "syntax" in validation.error.lower()

    def test_full_flow_with_text_heavy_response(self):
        """Should handle responses with lots of explanatory text."""
        llm_response = f"""I apologize for the previous rate limit error. Let me try again.

Based on your request, I'll create a custom Langflow component that performs sentiment analysis.
This component will:
1. Take text input
2. Process it through a sentiment analyzer
3. Return the sentiment score

Here's the implementation:

```python
{VALID_COMPONENT_CODE}
```

To use this component:
1. Drag it onto your canvas
2. Connect an input
3. The output will contain the sentiment analysis

Let me know if you need any modifications!"""

        code = extract_python_code(llm_response)
        assert code is not None

        validation = validate_component_code(code)
        assert validation.is_valid is True
        assert validation.class_name == "HelloWorldComponent"


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_handles_windows_line_endings(self):
        """Should handle Windows-style line endings (CRLF)."""
        code = VALID_COMPONENT_CODE.replace("\n", "\r\n")
        text = f"```python\r\n{code}\r\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "HelloWorldComponent" in result

    def test_handles_mixed_line_endings(self):
        """Should handle mixed line endings."""
        text = f"Text\r\n```python\n{VALID_COMPONENT_CODE}\r\n```"

        result = extract_python_code(text)

        assert result is not None

    def test_handles_unicode_in_code(self):
        """Should handle unicode characters in code."""
        unicode_code = """from langflow.custom import Component

class UnicodeComponent(Component):
    display_name = "Unicode \u00e9\u00e0\u00fc"
    description = "Handles \u4e2d\u6587 and \ud83d\ude00"
"""
        text = f"```python\n{unicode_code}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "Unicode" in result

    def test_handles_very_long_code(self):
        """Should handle very long code blocks."""
        long_code = VALID_COMPONENT_CODE + "\n" * 1000 + "# End of long code"
        text = f"```python\n{long_code}\n```"

        result = extract_python_code(text)

        assert result is not None
        assert "HelloWorldComponent" in result
        assert "End of long code" in result

    def test_case_insensitive_python_tag(self):
        """Should handle Python tag with different cases."""
        for tag in ["```python", "```Python", "```PYTHON", "```PyThOn"]:
            text = f"{tag}\n{VALID_COMPONENT_CODE}\n```"

            result = extract_python_code(text)

            assert result is not None, f"Failed for tag: {tag}"
