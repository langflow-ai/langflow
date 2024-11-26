---
title: Message Object
sidebar_position: 2
slug: /types-message
---

The `Message` object extends the functionality of `Data` and includes additional attributes and methods for chat interactions.

- **Core message data:**

  - `text`: The main text content of the message
  - `sender`: Identifier for the sender (e.g., "User" or "AI")
  - `sender_name`: Name of the sender
  - `session_id`: Identifier for the chat session
  - `timestamp`: Timestamp when the message was created (UTC)
  - `flow_id`: Identifier for the flow
  - `id`: Unique identifier for the message

- **Content and files:**

  - `files`: List of files or images associated with the message
  - `content_blocks`: List of structured content blocks
  - `properties`: Additional properties including visual styling and source information

- **Message state:**
  - `error`: Boolean indicating if there was an error
  - `edit`: Boolean indicating if the message was edited
  - `category`: Message category ("message", "error", "warning", "info")

The `Message` object can be used to send, store, and manipulate chat messages within Langflow. You can create a `Message` object by directly assigning key-value pairs to it. For example:

```python
from langflow.schema.message import Message

message = Message(text="Hello, AI!", sender="User", sender_name="John Doe")
```

To receive `Message` objects in a component input, you can use the `MessageInput` input type or `MessageTextInput` when the goal is to extract just the `text` field of the `Message` object.
