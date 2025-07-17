from langflow.schema.message import Message


class TestMustacheTemplateProcessing:
    """Test mustache template processing in the Message class."""

    def test_format_text_mustache_basic(self):
        """Test basic mustache template formatting."""
        message = Message(template="Hello {{name}}!", variables={"name": "World"})
        result = message.format_text(template_format="mustache")

        assert result == "Hello World!"
        assert message.text == "Hello World!"

    def test_format_text_mustache_multiple_variables(self):
        """Test mustache template with multiple variables."""
        message = Message(
            template="Hello {{name}}! You are {{age}} years old.", variables={"name": "Alice", "age": "25"}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Hello Alice! You are 25 years old."

    def test_format_text_mustache_missing_variable(self):
        """Test mustache template with missing variable."""
        message = Message(template="Hello {{name}}! You are {{age}} years old.", variables={"name": "Bob"})
        result = message.format_text(template_format="mustache")

        # Missing variables should render as empty strings
        assert result == "Hello Bob! You are  years old."

    def test_format_text_mustache_no_variables(self):
        """Test mustache template with no variables."""
        message = Message(template="Hello World!", variables={})
        result = message.format_text(template_format="mustache")

        assert result == "Hello World!"

    def test_format_text_mustache_empty_template(self):
        """Test mustache template with empty template."""
        message = Message(template="", variables={"name": "Test"})
        result = message.format_text(template_format="mustache")

        assert result == ""

    def test_format_text_mustache_conditional_logic(self):
        """Test mustache template with conditional logic."""
        message = Message(
            template="{{#show_greeting}}Hello {{name}}!{{/show_greeting}}{{#show_age}} You are {{age}}.{{/show_age}}",
            variables={"name": "Charlie", "age": "30", "show_greeting": True, "show_age": False},
        )
        result = message.format_text(template_format="mustache")

        # Only greeting should show, age section should be hidden
        assert result == "Hello Charlie!"

    def test_format_text_mustache_with_lists(self):
        """Test mustache template with list iteration."""
        message = Message(
            template="Items:\n{{#items}}- {{.}}\n{{/items}}", variables={"items": ["apple", "banana", "cherry"]}
        )
        result = message.format_text(template_format="mustache")

        expected = "Items:\n- apple\n- banana\n- cherry\n"
        assert result == expected

    def test_format_text_mustache_with_objects(self):
        """Test mustache template with object properties."""
        message = Message(
            template="User: {{user.name}} ({{user.email}})",
            variables={"user": {"name": "John", "email": "john@example.com"}},
        )
        result = message.format_text(template_format="mustache")

        assert result == "User: John (john@example.com)"

    def test_format_text_mustache_with_boolean_true(self):
        """Test mustache template with boolean true."""
        message = Message(
            template="{{#is_admin}}Admin access{{/is_admin}}{{^is_admin}}Regular user{{/is_admin}}",
            variables={"is_admin": True},
        )
        result = message.format_text(template_format="mustache")

        assert result == "Admin access"

    def test_format_text_mustache_with_boolean_false(self):
        """Test mustache template with boolean false."""
        message = Message(
            template="{{#is_admin}}Admin access{{/is_admin}}{{^is_admin}}Regular user{{/is_admin}}",
            variables={"is_admin": False},
        )
        result = message.format_text(template_format="mustache")

        assert result == "Regular user"

    def test_format_text_mustache_with_inverted_section(self):
        """Test mustache template with inverted section."""
        message = Message(template="{{#items}}Has items{{/items}}{{^items}}No items{{/items}}", variables={"items": []})
        result = message.format_text(template_format="mustache")

        assert result == "No items"

    def test_format_text_mustache_with_special_characters(self):
        """Test mustache template with special characters."""
        message = Message(
            template="Message: {{content}}", variables={"content": "Hello! How are you? I'm 100% ready & excited!"}
        )
        result = message.format_text(template_format="mustache")

        # Mustache HTML-escapes by default
        assert result == "Message: Hello! How are you? I'm 100% ready &amp; excited!"

    def test_format_text_mustache_with_html_content(self):
        """Test mustache template with HTML-like content."""
        message = Message(template="Content: {{html}}", variables={"html": "<script>alert('test')</script>"})
        result = message.format_text(template_format="mustache")

        # Mustache HTML-escapes by default
        assert result == "Content: &lt;script&gt;alert('test')&lt;/script&gt;"

    def test_format_text_mustache_with_numeric_values(self):
        """Test mustache template with numeric values."""
        message = Message(
            template="Price: ${{price}}, Quantity: {{quantity}}", variables={"price": 19.99, "quantity": 3}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Price: $19.99, Quantity: 3"

    def test_format_text_mustache_with_newlines(self):
        """Test mustache template with newlines."""
        message = Message(
            template="Line 1: {{line1}}\nLine 2: {{line2}}", variables={"line1": "First", "line2": "Second"}
        )
        result = message.format_text(template_format="mustache")

        assert result == "Line 1: First\nLine 2: Second"

    def test_format_text_mustache_with_nested_objects(self):
        """Test mustache template with nested object properties."""
        message = Message(
            template="Company: {{company.name}}, CEO: {{company.ceo.name}}",
            variables={"company": {"name": "Tech Corp", "ceo": {"name": "Jane Smith"}}},
        )
        result = message.format_text(template_format="mustache")

        assert result == "Company: Tech Corp, CEO: Jane Smith"

    def test_format_text_mustache_with_empty_string_variable(self):
        """Test mustache template with empty string variable."""
        message = Message(template="Hello {{name}}!", variables={"name": ""})
        result = message.format_text(template_format="mustache")

        assert result == "Hello !"

    def test_format_text_mustache_with_none_variable(self):
        """Test mustache template with None variable."""
        message = Message(template="Hello {{name}}!", variables={"name": None})
        result = message.format_text(template_format="mustache")

        # None should render as empty string
        assert result == "Hello !"

    async def test_from_template_and_variables_mustache(self):
        """Test from_template_and_variables with mustache format."""
        message = await Message.from_template_and_variables(
            template="Hello {{name}}!", template_format="mustache", name="World"
        )

        assert isinstance(message, Message)
        assert message.text == "Hello World!"
        assert message.template == "Hello {{name}}!"
        assert message.variables == {"name": "World"}

    async def test_from_template_and_variables_mustache_complex(self):
        """Test from_template_and_variables with complex mustache template."""
        message = await Message.from_template_and_variables(
            template="{{#show}}Hello {{name}}!{{/show}} {{#items}}Item: {{.}}{{/items}}",
            template_format="mustache",
            name="Test",
            show=True,
            items=["A", "B"],
        )

        assert isinstance(message, Message)
        assert message.text == "Hello Test! Item: AItem: B"

    async def test_from_template_and_variables_mustache_no_variables(self):
        """Test from_template_and_variables with no variables."""
        message = await Message.from_template_and_variables(template="Static message", template_format="mustache")

        assert isinstance(message, Message)
        assert message.text == "Static message"
        assert message.variables == {}

    def test_format_text_mustache_preserves_original_variables(self):
        """Test that format_text doesn't modify the original variables."""
        original_variables = {"name": "Test", "age": 25}
        message = Message(template="Hello {{name}}, age {{age}}!", variables=original_variables.copy())

        result = message.format_text(template_format="mustache")

        assert result == "Hello Test, age 25!"
        assert message.variables == original_variables

    def test_format_text_mustache_with_zero_values(self):
        """Test mustache template with zero values."""
        message = Message(template="Count: {{count}}, Price: {{price}}", variables={"count": 0, "price": 0.0})
        result = message.format_text(template_format="mustache")

        assert result == "Count: 0, Price: 0.0"

    def test_format_text_mustache_with_false_values(self):
        """Test mustache template with false values in conditional."""
        message = Message(
            template="{{#enabled}}Feature enabled{{/enabled}}{{^enabled}}Feature disabled{{/enabled}}",
            variables={"enabled": False},
        )
        result = message.format_text(template_format="mustache")

        assert result == "Feature disabled"
