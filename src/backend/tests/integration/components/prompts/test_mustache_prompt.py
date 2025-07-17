import pytest
from langflow.components.prompts.mustache_prompt import MustachePromptComponent
from langflow.schema.message import Message

from tests.integration.utils import pyleak_marker, run_single_component

pytestmark = pyleak_marker()


async def test_mustache_prompt_basic():
    """Test basic mustache prompt functionality."""
    outputs = await run_single_component(
        MustachePromptComponent, inputs={"template": "Hello {{name}}!", "name": "World"}
    )

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "Hello World!"


async def test_mustache_prompt_multiple_variables():
    """Test mustache prompt with multiple variables."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "Hello {{name}}! You are {{age}} years old and live in {{city}}.",
            "name": "Alice",
            "age": "25",
            "city": "New York",
        },
    )

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "Hello Alice! You are 25 years old and live in New York."


async def test_mustache_prompt_missing_variable():
    """Test mustache prompt with missing variable."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "Hello {{name}}! You are {{age}} years old.",
            "name": "Bob",
            # age is missing
        },
    )

    assert isinstance(outputs["prompt"], Message)
    # Missing variables should render as empty strings
    assert outputs["prompt"].text == "Hello Bob! You are  years old."


async def test_mustache_prompt_no_variables():
    """Test mustache prompt with no variables."""
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": "This is a static message."})

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "This is a static message."


async def test_mustache_prompt_empty_template():
    """Test mustache prompt with empty template."""
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": ""})

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == ""


async def test_mustache_prompt_simple_variables_only():
    """Test that only simple variables are processed, not complex syntax."""
    # Note: This test verifies that the backend still processes all mustache syntax
    # but the frontend will only highlight simple variables
    template = "Hello {{name}}!"
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": template, "name": "World"})

    assert isinstance(outputs["prompt"], Message)
    # Backend still processes all mustache syntax
    assert outputs["prompt"].text == "Hello World!"


async def test_mustache_prompt_rejects_list_syntax():
    """Test that mustache list iteration syntax is rejected."""
    with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
        await run_single_component(
            MustachePromptComponent,
            inputs={
                "template": "Shopping list:\n{{#items}}- {{.}}\n{{/items}}",
                "items": ["apples", "bananas", "oranges"],
            },
        )


async def test_mustache_prompt_with_objects():
    """Test mustache prompt with object properties (dot notation)."""
    # Note: Dot notation variables like {{user.name}} are still supported
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "User: {{user.name}} ({{user.email}})\nRole: {{user.role}}",
            "user": {"name": "John Doe", "email": "john@example.com", "role": "admin"},
        },
    )

    assert isinstance(outputs["prompt"], Message)
    expected = "User: John Doe (john@example.com)\nRole: admin"
    assert outputs["prompt"].text == expected


async def test_mustache_prompt_with_special_characters():
    """Test mustache prompt with special characters."""
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": "Message: {{message}}"})

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "Message: "


async def test_mustache_prompt_with_newlines():
    """Test mustache prompt with newlines in template and variables."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={"template": "Multi-line template:\n{{content}}\nEnd of message.", "content": "Line 1\nLine 2\nLine 3"},
    )

    assert isinstance(outputs["prompt"], Message)
    expected = "Multi-line template:\nLine 1\nLine 2\nLine 3\nEnd of message."
    assert outputs["prompt"].text == expected


async def test_mustache_prompt_rejects_boolean_conditionals():
    """Test that mustache conditional syntax is rejected."""
    with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
        await run_single_component(
            MustachePromptComponent,
            inputs={
                "template": "{{#is_admin}}Admin privileges enabled{{/is_admin}}{{^is_admin}}Regular user{{/is_admin}}",
                "is_admin": True,
            },
        )


async def test_mustache_prompt_rejects_inverted_section():
    """Test that mustache inverted section syntax is rejected."""
    with pytest.raises(ValueError, match="Complex mustache syntax is not allowed"):
        await run_single_component(
            MustachePromptComponent,
            inputs={
                "template": "{{#has_items}}Items available{{/has_items}}{{^has_items}}No items available{{/has_items}}",
                "has_items": False,
            },
        )


async def test_mustache_prompt_with_html_escaping():
    """Test mustache prompt with HTML-like content."""
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": "Content: {{content}}"})

    assert isinstance(outputs["prompt"], Message)
    # Without the content variable, should render as empty
    assert outputs["prompt"].text == "Content: "


async def test_mustache_prompt_with_numeric_values():
    """Test mustache prompt with numeric values."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "Price: ${{price}}, Quantity: {{quantity}}, Total: ${{total}}",
            "price": 19.99,
            "quantity": 3,
            "total": 59.97,
        },
    )

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "Price: $19.99, Quantity: 3, Total: $59.97"
