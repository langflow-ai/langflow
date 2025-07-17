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


async def test_mustache_prompt_complex_mustache_logic():
    """Test mustache prompt with conditional logic."""
    template = (
        "{{#show_greeting}}Hello {{name}}!{{/show_greeting}}{{#show_age}} You are {{age}} years old.{{/show_age}}"
    )
    outputs = await run_single_component(MustachePromptComponent, inputs={"template": template})

    assert isinstance(outputs["prompt"], Message)
    # Without variables, the template should render as is (but sections without variables are false)
    assert outputs["prompt"].text == ""


async def test_mustache_prompt_with_lists():
    """Test mustache prompt with list iteration."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={"template": "Shopping list:\n{{#items}}- {{.}}\n{{/items}}", "items": ["apples", "bananas", "oranges"]},
    )

    assert isinstance(outputs["prompt"], Message)
    expected = "Shopping list:\n- apples\n- bananas\n- oranges\n"
    assert outputs["prompt"].text == expected


async def test_mustache_prompt_with_objects():
    """Test mustache prompt with object properties."""
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


async def test_mustache_prompt_with_boolean_values():
    """Test mustache prompt with boolean values."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "{{#is_admin}}Admin privileges enabled{{/is_admin}}{{^is_admin}}Regular user{{/is_admin}}",
            "is_admin": True,
        },
    )

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "Admin privileges enabled"


async def test_mustache_prompt_with_inverted_section():
    """Test mustache prompt with inverted section (^)."""
    outputs = await run_single_component(
        MustachePromptComponent,
        inputs={
            "template": "{{#has_items}}Items available{{/has_items}}{{^has_items}}No items available{{/has_items}}",
            "has_items": False,
        },
    )

    assert isinstance(outputs["prompt"], Message)
    assert outputs["prompt"].text == "No items available"


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
