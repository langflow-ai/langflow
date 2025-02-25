---
title: Inputs and outputs
slug: /components-io
---

# Input and output components in Langflow

Input and output components define where data enters and exits your flow.

Both components accept user input and return a [Message](/concepts-objects#message-object) object, but serve different purposes.

The **Text Input** component accepts a text string input and returns a `Message` object containing only the input text.

The **Chat Input** component accepts multiple input types including text, files, and metadata, and returns a `Message` object containing the text along with sender information, session ID, and file attachments.

The **Chat Input** component provides a more interactive chat interface in the **Playground**. The **Text Input** component displays only the basic text input field in the **Playground**.

## Chat Input

This component collects user input as `Text` strings from the chat and wraps it in a [Message](/concepts-objects) object that includes the input text, sender information, session ID, file attachments, and styling properties.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The Message to be passed as input.
|should_store_message|Store Messages|Store the message in the history.|
|sender|Sender Type|The type of sender.|
|sender_name|Sender Name|The name of the sender.|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter will be used.|
|files|Files|The files to be sent with the message.|
|background_color|Background Color|The background color of the icon.|
|chat_icon|Icon|The icon of the message.|
|text_color|Text Color|The text color of the name.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|

## Text Input

The **Text Input** component accepts a text string input and returns a `Message` object containing only the input text.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text/content to be passed as output.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|


## Chat Output

The **Chat Output** component creates a [Message](/concepts-objects#message-object) object that includes the input text, sender information, session ID, and styling properties.

The component accepts the following input types.
* [Data](/concepts-objects#data-object)
* [DataFrame](/concepts-objects#dataframe-object)
* [Message](/concepts-objects#message-object)

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The message to be passed as output.|
|should_store_message|Store Messages|The flag to store the message in the history.|
|sender|Sender Type|The type of sender.|
|sender_name|Sender Name|The name of the sender.|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter will be used.|
|data_template|Data Template|The template to convert Data to Text. If left empty, it will be dynamically set to the Data's text key.|
|background_color|Background Color|The background color of the icon.|
|chat_icon|Icon|The icon of the message.|
|text_color|Text Color|The text color of the name.|
|clean_data|Basic Clean Data|When enabled, `DataFrame` inputs are cleaned when converted to text. Cleaning removes empty rows, empty lines in cells, and multiple newlines.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|


## Text Output

The **Text Output** component displays text output in the **Playground**.
It takes a single input of text and returns a [Message](/concepts-objects) object containing that text.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text to be passed as output.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|



