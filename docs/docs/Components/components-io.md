---
title: Inputs & Outputs
sidebar_position: 1
slug: /components-io
---

# Inputs & Outputs

This category of components defines where data enters and exits your flow. They dynamically alter the Playground and can be renamed to facilitate building and maintaining your flows.

## Inputs

Inputs are components used to define where data enters your flow. They can receive data from various sources, such as users, databases, or any other source that can be converted to Text or Data.

### Chat Input

This component collects user input from the chat.

The difference between Chat Input and other Input components is the output format, the number of configurable fields, and the way they are displayed in the Playground.

Chat Input components can output Text or Data. When you want to pass the sender name or sender to the next component, use the Data output. To pass only the message, use the Text output. Passing only the message is useful when saving the message to a database or a memory system like Zep.

#### Parameters

| Name         | Display Name | Info                                                                |
|--------------|--------------|---------------------------------------------------------------------|
| Sender Type  | Sender Type  | Specifies the sender type (User or Machine). Defaults to User       |
| Sender Name  | Sender Name  | Specifies the name of the sender. Defaults to User                  |
| Message      | Message      | Specifies the message text. Multiline text input                    |
| Session ID   | Session ID   | Specifies the session ID of the chat history                        |

:::note
If "As Data" is true and the "Message" is a Data, the data will be updated with the Sender, Sender Name, and Session ID.
:::

### Text Input

This component adds an Input field on the Playground, allowing parameter definition while running and testing your flow.

The Data Template field specifies how a Data should be converted into Text. This is particularly useful when you want to extract specific information from a Data and pass it as text to the next component in the sequence.

For example, if you have a Data with the following structure:

```json
{ "name": "John Doe", "age": 30, "email": "johndoe@email.com"}
```

A template with Name: `{name}, Age: {age}` will convert the Data into a text string of `Name: John Doe, Age: 30`.

If you pass more than one Data, the text will be concatenated with a new line separator.

#### Parameters

| Name          | Display Name  | Info                                                               |
|---------------|---------------|--------------------------------------------------------------------|
| Value         | Value         | Specifies the text input value. Defaults to an empty string        |
| Data Template | Data Template | Specifies how a Data should be converted into Text                 |

## Outputs

Outputs define where data exits your flow. They can send data to the user, the Playground, or define how data will be displayed in the Playground.

### Chat Output

This component sends a message to the chat.

#### Parameters

| Name         | Display Name | Info                                                                |
|--------------|--------------|---------------------------------------------------------------------|
| Sender Type  | Sender Type  | Specifies the sender type (Machine or User). Defaults to Machine    |
| Sender Name  | Sender Name  | Specifies the sender's name. Defaults to AI                         |
| Session ID   | Session ID   | Specifies the session ID of the chat history                        |
| Message      | Message      | Specifies the text of the message                                   |

:::note
If "As Data" is true and the "Message" is a Data, the data will be updated with the Sender, Sender Name, and Session ID.
:::

### Text Output

This component displays text data to the user without sending it to the chat. Defaults to an empty string.

#### Parameters

| Name  | Display Name | Info                                                    |
|-------|--------------|----------------------------------------------------------|
| Value | Value        | Specifies the text data to be displayed                  |

