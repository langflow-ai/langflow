---
title: Inputs and outputs
slug: /components-io
---

# Input and output components in Langflow

This category of components defines where data enters and exits your flow. They dynamically alter the Playground and can be renamed to facilitate building and maintaining your flows.

The difference between Chat Input and Text Input components is the output format, the number of configurable fields, and the way they are displayed in the Playground.

## Chat Input

This component collects user input from the chat.

The Chat Input component creates a [Message](/concepts-objects) object that includes the input text, sender information, session ID, file attachments, and styling properties.

The component accepts the following input types:

* Text strings
* [Data](/concepts-objects#data-object)
* [DataFrame](/concepts-objects#dataframe-object)
* [Message](/concepts-objects#message-object)
* Lists of any of the above data types

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The Message to be passed as input. Accepts text, data objects, messages, and dataframes.|
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

The Text Input component adds an Input field on the Playground.

The Text Input component offers one input field for text, while the Chat Input has multiple fields for various chat-related features.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text to be passed as input.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|


## Chat Output

The Chat Output component creates a [Message](/concepts-objects) object that includes the input text, sender information, session ID, and styling properties.
It can optionally store the message in a chat history and supports customization of the message appearance, including background color, icon, and text color.

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

The TextOutputComponent displays text output in the **Playground**.
It takes a single input of text and returns a [Message](/concepts-objects) object containing that text.
The component is simpler compared to the Chat Output but focuses solely on displaying text without additional chat-specific features or customizations.

### Inputs

| Name | Display Name | Info |
|------|--------------|------|
|input_value|Text|The text to be passed as output.|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|



