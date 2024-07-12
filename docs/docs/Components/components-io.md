---
title: Inputs & Outputs
sidebar_position: 1
slug: /components-io
---



Inputs and Outputs are a category of components that are used to define where data comes in and out of your flow. They also dynamically change the Playground and can be renamed to facilitate building and maintaining your flows.


## Inputs {#6b1421ec66994d5ebe9fcce000829328}


---


Inputs are components used to define where data enters your flow. They can receive data from the user, a database, or any other source that can be converted to Text or Data.


The difference between Chat Input and other Input components is the output format, the number of configurable fields, and the way they are displayed in the Playground.


Chat Input components can output `Text` or `Data`. When you want to pass the sender name or sender to the next component, use the `Data` output. To pass only the message, use the `Text` output, useful when saving the message to a database or memory system like Zep.


You can find out more about Chat Input and other Inputs [here](/components-io).


### Chat Input {#2a5f02262f364f8fb75bcfa246e7bb26}


This component collects user input from the chat.


**Parameters**

- **Sender Type:** Specifies the sender type. Defaults to `User`. Options are `Machine` and `User`.
- **Sender Name:** Specifies the name of the sender. Defaults to `User`.
- **Message:** Specifies the message text. It is a multiline text input.
- **Session ID:** Specifies the session ID of the chat history. If provided, the message will be saved in the Message History.

:::note

If `As Data` is `true` and the `Message` is a `Data`, the data of the `Data` will be updated with the `Sender`, `Sender Name`, and `Session ID`.

:::




One significant capability of the Chat Input component is its ability to transform the Playground into a chat window. This feature is particularly valuable for scenarios requiring user input to initiate or influence the flow.


### Text Input {#260aef3726834896b496b56cdefb6d4a}


The **Text Input** component adds an **Input** field on the Playground. This enables you to define parameters while running and testing your flow.


**Parameters**

- **Value:** Specifies the text input value. This is where the user inputs text data that will be passed to the next component in the sequence. If no value is provided, it defaults to an empty string.
- **Data Template:** Specifies how a `Data` should be converted into `Text`.

The **Data Template** field is used to specify how a `Data` should be converted into `Text`. This is particularly useful when you want to extract specific information from a `Data` and pass it as text to the next component in the sequence.


For example, if you have a `Data` with the following structure:


`{  "name": "John Doe",  "age": 30,  "email": "johndoe@email.com"}`


A template with `Name: {name}, Age: {age}` will convert the `Data` into a text string of `Name: John Doe, Age: 30`.


If you pass more than one `Data`, the text will be concatenated with a new line separator.


## Outputs {#f62c5ad37a6f45a39b463c9b35ce7842}


---


Outputs are components that are used to define where data comes out of your flow. They can be used to send data to the user, to the Playground, or to define how the data will be displayed in the Playground.


The Chat Output works similarly to the Chat Input but does not have a field that allows for written input. It is used as an Output definition and can be used to send data to the user.


You can find out more about it and the other Outputs [here](/components-io).


### Chat Output {#1edd49b72781432ea29d70acbda4e7e7}


This component sends a message to the chat.


**Parameters**

- **Sender Type:** Specifies the sender type. Default is `"Machine"`. Options are `"Machine"` and `"User"`.
- **Sender Name:** Specifies the sender's name. Default is `"AI"`.
- **Session ID:** Specifies the session ID of the chat history. If provided, messages are saved in the Message History.
- **Message:** Specifies the text of the message.

:::note

If `As Data` is `true` and the `Message` is a `Data`, the data in the `Data` is updated with the `Sender`, `Sender Name`, and `Session ID`.

:::




### Text Output {#b607000bc0c5402db0433c1a7d734d01}


This component displays text data to the user. It is useful when you want to show text without sending it to the chat.


**Parameters**

- **Value:** Specifies the text data to be displayed. Defaults to an empty string.

The `TextOutput` component provides a simple way to display text data. It allows textual data to be visible in the chat window during your interaction flow.

