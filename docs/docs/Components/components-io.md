---
title: Inputs and outputs
slug: /components-io
---

import Icon from "@site/src/components/icon";

# Input and output components in Langflow

Input and output components define where data enters and exits your flow.

Both components accept user input and return a `Message` object, but serve different purposes.

The **Text Input** component accepts a text string input and returns a `Message` object containing only the input text. The output does not appear in the **Playground**.

The **Chat Input** component accepts multiple input types including text, files, and metadata, and returns a `Message` object containing the text along with sender information, session ID, and file attachments.

The **Chat Input** component provides an interactive chat interface in the **Playground**.

## Chat Input

This component collects user input as `Text` strings from the chat and wraps it in a [Message](/concepts-objects#message-object) object that includes the input text, sender information, session ID, file attachments, and styling properties.

It can optionally store the message in a chat history.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The Message to be passed as input.
|should_store_message|Store Messages|Store the message in the history.|
|sender|Sender Type|The type of sender.|
|sender_name|Sender Name|The name of the sender.|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter is used.|
|files|Files|The files to be sent with the message.|
|background_color|Background Color|The background color of the icon.|
|chat_icon|Icon|The icon of the message.|
|text_color|Text Color|The text color of the name.|

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|

</details>

### Message method

The `ChatInput` class provides an asynchronous method to create and store a `Message` object based on the input parameters.
The `Message` object is created in the `message_response` method of the ChatInput class using the `Message.create()` factory method.

```python
message = await Message.create(
    text=self.input_value,
    sender=self.sender,
    sender_name=self.sender_name,
    session_id=self.session_id,
    files=self.files,
    properties={
        "background_color": background_color,
        "text_color": text_color,
        "icon": icon,
    },
)
```

## Text Input

The **Text Input** component accepts a text string input and returns a `Message` object containing only the input text.

The output does not appear in the **Playground**.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text/content to be passed as output.|

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|

</details>

## Chat Output

The **Chat Output** component creates a [Message](/concepts-objects#message-object) object that includes the input text, sender information, session ID, and styling properties.

The component accepts the following input types.
* [Data](/concepts-objects#data-object)
* [DataFrame](/concepts-objects#dataframe-object)
* [Message](/concepts-objects#message-object)

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The message to be passed as output.|
|should_store_message|Store Messages|The flag to store the message in the history.|
|sender|Sender Type|The type of sender.|
|sender_name|Sender Name|The name of the sender.|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter is used.|
|data_template|Data Template|The template to convert Data to Text. If the option is left empty, it is dynamically set to the Data's text key.|
|background_color|Background Color|The background color of the icon.|
|chat_icon|Icon|The icon of the message.|
|text_color|Text Color|The text color of the name.|
|clean_data|Basic Clean Data|When enabled, `DataFrame` inputs are cleaned when converted to text. Cleaning removes empty rows, empty lines in cells, and multiple newlines.|

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|

</details>

## Text Output

The **Text Output** takes a single input of text and returns a [Message](/concepts-objects#message-object) object containing that text.

The output does not appear in the **Playground**.

<details>
<summary>Parameters</summary>

**Inputs**

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text to be passed as output.|

**Outputs**

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|

</details>

## Chat components example flow

1. To use the **Chat Input** and **Chat Output** components in a flow, connect them to components that accept or send the [Message](/concepts-objects#message-object) type.

For this example, connect a **Chat Input** component to an **OpenAI** model component's **Input** port, and then connect the **OpenAI** model component's **Message** port to the **Chat Output** component.

2. In the **OpenAI** model component, in the **OpenAI API Key** field, add your **OpenAI API key**.

The flow looks like this:

![Chat input and output components connected to an OpenAI model](/img/component-chat-io.png)

3. To send a message to your flow, open the **Playground**, and then enter a message.
The **OpenAI** model component responds.
Optionally, in the **OpenAI** model component, enter a **System Message** to control the model's response.
4. In the Langflow UI, click your flow name, and then click **Logs**.
The **Logs** pane opens.
Here, you can inspect your component logs.
![Logs pane](/img/logs.png)

5. Your first message was sent by the **Chat Input** component to the **OpenAI** model component.
Click **Outputs** to view the sent message:
```text
  "messages": [
    {
      "message": "What's the recommended way to install Docker on Mac M1?",
      "sender": "User",
      "sender_name": "User",
      "session_id": "Session Apr 21, 17:37:04",
      "stream_url": null,
      "component_id": "ChatInput-4WKag",
      "files": [],
      "type": "text"
    }
  ],
```
6. Your second message was sent by the **OpenAI** model component to the **Chat Output** component.
This is the raw text output of the model's response.
The **Chat Output** component accepts this text as input and presents it as a formatted message.
Click **Outputs** to view the sent message:
```text
  "outputs":
    "text_output":
      "message": "To install Docker on a Mac with an M1 chip, you should use Docker Desktop for Mac, which is optimized for Apple Silicon. Here's a step-by-step guide to installing Docker on your M1 Mac:\n\n1.
      ...
      "type": "text"
```

:::tip
Optionally, to view the outputs of each component in the flow, click <Icon name="TextSearch" aria-label="Inspect icon" />.
:::

### Send chat messages with the API

The **Chat Input** component is often the entry point for passing messages to the Langflow API.
To send the same example messages programmatically to your Langflow server, do the following:

1. To get your Langflow endpoint, click **Publish**, and then click **API access**.
2. Copy the command from the **cURL** tab, and then paste it in your terminal.
It looks similar to this:
```text
curl --request POST \
  --url 'http://localhost:7860/api/v1/run/51eed711-4530-4fdc-9bce-5db4351cc73a?stream=false' \
  --header 'Content-Type: application/json' \
  --data '{
  "input_value": "What's the recommended way to install Docker on Mac M1?",
  "output_type": "chat",
  "input_type": "chat"
}'
```
3. Modify `input_value` so it contains the question, `What's the recommended way to install Docker on Mac M1?`.

Note the `output_type` and `input_type` parameters that are passed with the message. The `chat` type provides additional configuration options, and the messages appear in the **Playground**. The `text` type returns only text strings, and does not appear in the **Playground**.

4. Add a custom `session_id` to the message's `data` object.
```text
curl --request POST \
  --url 'http://localhost:7860/api/v1/run/51eed711-4530-4fdc-9bce-5db4351cc73a?stream=false' \
  --header 'Content-Type: application/json' \
  --data '{
  "input_value": "Whats the recommended way to install Docker on Mac M1",
  "session_id": "docker-question-on-m1",
  "output_type": "chat",
  "input_type": "chat"
}'
```
The custom `session_id` value starts a new chat session between your client and the Langflow server, and can be useful in keeping conversations and AI context separate.

5. Send the POST request.
Your request is answered.
6. Navigate to the **Playground**.
A new chat session called `docker-question-on-m1` has appeared, using your unique `session_id`.
7. To modify additional parameters with **Tweaks** for your **Chat Input** and **Chat Output** components, click **Publish**, and then click **API access**.
8. Click **Tweaks** to modify parameters in the component's `data` object.
For example, disabling storing messages from the **Chat Input** component adds a **Tweak** to your command:
```text
curl --request POST \
  --url 'http://localhost:7860/api/v1/run/51eed711-4530-4fdc-9bce-5db4351cc73a?stream=false' \
  --header 'Content-Type: application/json' \
  --data '{
  "input_value": "Text to input to the flow",
  "output_type": "chat",
  "input_type": "chat",
  "tweaks": {
    "ChatInput-4WKag": {
      "should_store_message": false
    }
  }
}'
```

To confirm your command is using the tweak, navigate to the **Logs** pane and view the request from the **Chat Input** component.
The value for `should_store_message` is `false`.
