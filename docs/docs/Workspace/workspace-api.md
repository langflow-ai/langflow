---
title: API
sidebar_position: 2
slug: /workspace-api
---

import ReactPlayer from "react-player";

The **API** section presents code templates for integrating your flow into external applications.


![](/img/api-pane.png)


### cURL {#4eb287a8424349c4b0b436a6703de5f3}


The **cURL** tab displays sample code for posting a query to your flow. Modify the `input_value` to change your input message. Copy the code and run it to post a query to your flow and get the result.


### Python API {#fb7db14e6330418389562ef647aa2354}


The **Python API** tab displays code to interact with your flow using the Python HTTP requests library.


### Python Code {#7af87438549b4972907ac310a4193067}


The **Python Code** tab displays code to interact with your flow's `.json` file using the Langflow runtime.


### Tweaks {#5680600063724590ac2302b4ddeea867}


The **Tweaks** tab displays the available parameters for your flow. Modifying the parameters changes the code parameters across all windows. For example, changing the **Chat Input** component's `input_value` will change that value across all API calls.


## Send image files to your flow with the API

Send image files to the Langflow API for AI analysis.

The default file limit is 100 MB. To configure this value, change the `LANGFLOW_MAX_FILE_SIZE_UPLOAD` environment variable.
For more information, see [Supported environment variables](/environment-variables#supported-variables).

1. To send an image to your flow with the API, POST the image file to the `v1/files/upload/<YOUR-FLOW-ID>` endpoint of your flow.

```curl
curl -X POST "http://127.0.0.1:7860/api/v1/files/upload/a430cc57-06bb-4c11-be39-d3d4de68d2c4" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@image-file.png"
```

The API returns the image file path in the format `"file_path":"<YOUR-FLOW-ID>/<TIMESTAMP>_<FILE-NAME>"}`.

```json
{"flowId":"a430cc57-06bb-4c11-be39-d3d4de68d2c4","file_path":"a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png"}
```

2. Post the image file to the **Chat Input** component of a **Basic prompting** flow.
Pass the file path value as an input in the **Tweaks** section of the curl call to Langflow.

```curl
curl -X POST \
    "http://127.0.0.1:7860/api/v1/run/a430cc57-06bb-4c11-be39-d3d4de68d2c4?stream=false" \
    -H 'Content-Type: application/json'\
    -d '{
    "output_type": "chat",
    "input_type": "chat",
    "tweaks": {
  "ChatInput-b67sL": {
    "files": "a430cc57-06bb-4c11-be39-d3d4de68d2c4/2024-11-27_14-47-50_image-file.png",
    "input_value": "what do you see?"
  }
}}'
```

Your chatbot describes the image file you sent.

```plain
"text": "This flowchart appears to represent a complex system for processing financial inquiries using various AI agents and tools. Here’s a breakdown of its components and how they might work together..."
```

## Chat Widget {#48f121a6cb3243979a341753da0c2700}


---


The **Chat Widget HTML** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.


The **Langflow Chat Widget** is a powerful web component that enables communication with a Langflow project. This widget allows for a chat interface embedding, allowing the integration of Langflow into web applications effortlessly.


You can get the HTML code embedded with the chat by clicking the Code button at the Sidebar after building a flow.


Clicking the Chat Widget HTML tab, you'll get the code to be inserted. Read below to learn how to use it with HTML, React and Angular.


### Embed your flow into HTML {#6e84db2f2a0d451db6fa03c57e9bf9a4}


The Chat Widget can be embedded into any HTML page, inside a `<body>` tag, as demonstrated in the video below.


### Embed your flow with React {#fe5d3b1c42e74e4c84ebc9d1799b7665}


To embed the Chat Widget using React, insert this `<script>` tag into the React _index.html_ file, inside the `<body>`tag:


```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```


Declare your Web Component and encapsulate it in a React component.


```javascript
declare global {  namespace JSX {    interface IntrinsicElements {      "langflow-chat": any;    }  }}export default function ChatWidget({ className }) {  return (    <div className={className}>      <langflow-chat        chat_inputs='{"your_key":"value"}'        chat_input_field="your_chat_key"        flow_id="your_flow_id"        host_url="langflow_url"      ></langflow-chat>    </div>  );}
```



Finally, you can place the component anywhere in your code to display the Chat Widget.


### Embed your flow with Angular {#4fd87355b9aa409894acfbb9e1497980}


To use the chat widget in Angular, first add this `<script>` tag into the Angular _index.html_ file, inside the `<body>` tag.


```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```



When you use a custom web component in an Angular template, the Angular compiler might show a warning when it doesn't recognize the custom elements by default. To suppress this warning, add `CUSTOM_ELEMENTS_SCHEMA` to the module's `@NgModule.schemas`.

- Open the module file (it typically ends with _.module.ts_) where you'd add the `langflow-chat` web component.
- Import `CUSTOM_ELEMENTS_SCHEMA` at the top of the file:

`import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from "@angular/core";`

- Add `CUSTOM_ELEMENTS_SCHEMA` to the 'schemas' array inside the '@NgModule' decorator:

```javascript
@NgModule({  declarations: [    // ... Other components and directives ...  ],  imports: [    // ... Other imported modules ...  ],  schemas: [CUSTOM_ELEMENTS_SCHEMA], // Add the CUSTOM_ELEMENTS_SCHEMA here})export class YourModule {}
```



In your Angular project, find the component belonging to the module where `CUSTOM_ELEMENTS_SCHEMA` was added. Inside the template, add the `langflow-chat` tag to include the Chat Widget in your component's view:


```javascript
<langflow-chat  chat_inputs='{"your_key":"value"}'  chat_input_field="your_chat_key"  flow_id="your_flow_id"  host_url="langflow_url"></langflow-chat>
```


:::tip

`CUSTOM_ELEMENTS_SCHEMA` is a built-in schema that allows Angular to recognize custom elements. Adding `CUSTOM_ELEMENTS_SCHEMA` tells Angular to allow custom elements in your templates, and it will suppress the warning related to unknown elements like `langflow-chat`. Notice that you can only use the Chat Widget in components that are part of the module where you added `CUSTOM_ELEMENTS_SCHEMA`.

:::




## Chat Widget Configuration {#5ede4bbbd2ac43e29c90f3edb43cba58}


---


Use the widget API to customize your Chat Widget:


:::caution

Props with the type JSON need to be passed as stringified JSONs, with the format \{"key":"value"\}.

:::




| Prop                  | Type    | Required | Description                                                                                                                                                      |
| --------------------- | ------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| bot_message_style     | JSON    | No       | Applies custom formatting to bot messages.                                                                                                                       |
| chat_input_field      | String  | Yes      | Defines the type of the input field for chat messages.                                                                                                           |
| chat_inputs           | JSON    | Yes      | Determines the chat input elements and their respective values.                                                                                                  |
| chat_output_key       | String  | No       | Specifies which output to display if multiple outputs are available.                                                                                             |
| chat_position         | String  | No       | Positions the chat window on the screen (options include: top-left, top-center, top-right, center-left, center-right, bottom-right, bottom-center, bottom-left). |
| chat_trigger_style    | JSON    | No       | Styles the chat trigger button.                                                                                                                                  |
| chat_window_style     | JSON    | No       | Customizes the overall appearance of the chat window.                                                                                                            |
| error_message_style   | JSON    | No       | Sets the format for error messages within the chat window.                                                                                                       |
| flow_id               | String  | Yes      | Identifies the flow that the component is associated with.                                                                                                       |
| height                | Number  | No       | Sets the height of the chat window in pixels.                                                                                                                    |
| host_url              | String  | Yes      | Specifies the URL of the host for chat component communication.                                                                                                  |
| input_container_style | JSON    | No       | Applies styling to the container where chat messages are entered.                                                                                                |
| input_style           | JSON    | No       | Sets the style for the chat input field.                                                                                                                         |
| online                | Boolean | No       | Toggles the online status of the chat component.                                                                                                                 |
| online_message        | String  | No       | Sets a custom message to display when the chat component is online.                                                                                              |
| placeholder           | String  | No       | Sets the placeholder text for the chat input field.                                                                                                              |
| placeholder_sending   | String  | No       | Sets the placeholder text to display while a message is being sent.                                                                                              |
| send_button_style     | JSON    | No       | Sets the style for the send button in the chat window.                                                                                                           |
| send_icon_style       | JSON    | No       | Sets the style for the send icon in the chat window.                                                                                                             |
| tweaks                | JSON    | No       | Applies additional custom adjustments for the associated flow.                                                                                                   |
| user_message_style    | JSON    | No       | Determines the formatting for user messages in the chat window.                                                                                                  |
| width                 | Number  | No       | Sets the width of the chat window in pixels.                                                                                                                     |
| window_title          | String  | No       | Sets the title displayed in the chat window's header or title bar.                                                                                               |

