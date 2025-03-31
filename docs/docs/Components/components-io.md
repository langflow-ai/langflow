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
It can optionally store the message in a chat history and supports customization of the message appearance.

### Inputs

| Name | Display Name | Info | Type |
|------|--------------|------|------|
|input_value|Text|Message to be passed as input.|MultilineInput|
|should_store_message|Store Messages|Store the message in the history.|BoolInput|
|sender|Sender Type|Type of sender.|DropdownInput|
|sender_name|Sender Name|Name of the sender.|MessageTextInput|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter will be used.|MessageTextInput|
|files|Files|Files to be sent with the message.|FileInput|
|background_color|Background Color|The background color of the icon.|MessageTextInput|
|chat_icon|Icon|The icon of the message.|MessageTextInput|
|text_color|Text Color|The text color of the name|MessageTextInput|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|

## Text Input

The Text Input component adds an Input field on the Playground.

The Text Input component offers one input field for text, while the Chat Input has multiple fields for various chat-related features.

### Inputs

| Name | Display Name | Info | Type |
|------|--------------|------|------|
|input_value|Text|Text to be passed as input.|MultilineInput|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|


## Chat Output

The Chat Output component creates a [Message](/concepts-objects) object that includes the input text, sender information, session ID, and styling properties.
It can optionally store the message in a chat history and supports customization of the message appearance, including background color, icon, and text color.

### Inputs

| Name | Display Name | Info | Type |
|------|--------------|------|------|
|input_value|Text|Message to be passed as output.|MessageInput|
|should_store_message|Store Messages|Store the message in the history.|BoolInput|
|sender|Sender Type|Type of sender.|DropdownInput|
|sender_name|Sender Name|Name of the sender.|MessageTextInput|
|session_id|Session ID|The session ID of the chat. If empty, the current session ID parameter will be used.|MessageTextInput|
|data_template|Data Template|Template to convert data to text. If left empty, it will be dynamically set to the data's text key.|MessageTextInput|
|background_color|Background Color|The background color of the icon.|MessageTextInput|
|chat_icon|Icon|The icon of the message.|MessageTextInput|
|text_color|Text Color|The text color of the name|MessageTextInput|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|message|Message|The resulting chat message object with all specified properties.|


## Text Output

The TextOutputComponent displays text output in the **Playground**.
It takes a single input of text and returns a [Message](/concepts-objects) object containing that text.
The component is simpler compared to the Chat Output but focuses solely on displaying text without additional chat-specific features or customizations.

### Inputs

| Name | Display Name | Info | Type |
|------|--------------|------|------|
|input_value|Text|Text to be passed as output.|MultilineInput|

### Outputs

| Name | Display Name | Info |
|------|--------------|------|
|text|Text|The resulting text message.|



