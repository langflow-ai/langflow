import pytest
from langflow.components.input_output.chat import ChatInput
from langflow.schema.message import Message


@pytest.fixture
def chat_input_instances():
    """Create two instances of ChatInput for testing."""
    chat1 = ChatInput()
    chat2 = ChatInput()
    return chat1, chat2


def test_input_value_independence(chat_input_instances):
    """Test that input_value is independent between instances."""
    chat1, chat2 = chat_input_instances

    # Set different input values
    chat1.build(input_value="Hello from chat1")
    chat2.build(input_value="Hello from chat2")

    # Verify values are different
    assert chat1.input_value != chat2.input_value
    assert chat1.input_value == "Hello from chat1"
    assert chat2.input_value == "Hello from chat2"


def test_sender_name_independence(chat_input_instances):
    """Test that sender_name is independent between instances."""
    chat1, chat2 = chat_input_instances

    # Set different sender names
    chat1.build(sender_name="Alice")
    chat2.build(sender_name="Bob")

    # Verify values are different
    assert chat1.sender_name != chat2.sender_name
    assert chat1.sender_name == "Alice"
    assert chat2.sender_name == "Bob"


def test_multiple_attributes_independence(chat_input_instances):
    """Test that multiple attributes are independent between instances."""
    chat1, chat2 = chat_input_instances

    # Set multiple attributes for chat1
    chat1.build(input_value="Message 1", sender_name="Alice", background_color="blue", text_color="white")

    # Set different attributes for chat2
    chat2.build(input_value="Message 2", sender_name="Bob", background_color="red", text_color="black")

    # Verify all attributes are independent
    assert chat1.input_value != chat2.input_value
    assert chat1.sender_name != chat2.sender_name
    assert chat1.background_color != chat2.background_color
    assert chat1.text_color != chat2.text_color


async def test_message_output_independence(chat_input_instances):
    """Test that message outputs are independent between instances."""
    chat1, chat2 = chat_input_instances

    # Configure different messages
    chat1.build(
        input_value="Hello from chat1",
        sender_name="Alice",
        should_store_message=False,  # Prevent actual message storage
    )
    chat2.build(
        input_value="Hello from chat2",
        sender_name="Bob",
        should_store_message=False,  # Prevent actual message storage
    )

    # Get messages from both instances
    message1 = await chat1.message_response()
    message2 = await chat2.message_response()

    # Verify messages are different
    assert isinstance(message1, Message)
    assert isinstance(message2, Message)
    assert message1.text != message2.text
    assert message1.sender_name != message2.sender_name


async def test_status_independence(chat_input_instances):
    """Test that status attribute is independent between instances."""
    chat1, chat2 = chat_input_instances

    # Configure and run messages
    chat1.build(input_value="Status test 1", sender_name="Alice", should_store_message=False)
    chat2.build(input_value="Status test 2", sender_name="Bob", should_store_message=False)

    # Generate messages to update status
    await chat1.message_response()
    await chat2.message_response()

    # Verify status values are different
    assert chat1.status != chat2.status
    assert chat1.status.text == "Status test 1"
    assert chat2.status.text == "Status test 2"


def test_files_independence(chat_input_instances):
    """Test that files attribute is independent between instances."""
    chat1, chat2 = chat_input_instances

    # Set different files
    files1 = ["file1.txt", "file2.txt"]
    files2 = ["file3.txt", "file4.txt"]

    chat1.build(files=files1)
    chat2.build(files=files2)

    # Verify files are independent
    assert chat1.files != chat2.files
    assert chat1.files == files1
    assert chat2.files == files2
