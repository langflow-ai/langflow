---
title: API pane
slug: /concepts-api
---

The **API** pane presents code templates for integrating your flow into external applications.

![](/img/api-pane.png)

## cURL

The **cURL** tab displays sample code for posting a query to your flow. Modify the `input_value` to change your input message. Copy the code and run it to post a query to your flow and get the result.

## Python API

The **Python API** tab displays code to interact with your flow using the Python HTTP `requests` library.

To use the `requests` library:

1. Copy and paste the code into a Python script.
2. Run the script and pass your message with it.

```python
python3 python-api-script.py --message="tell me about something interesting"
```
## Python code

The **Python Code** tab displays code to interact with your flow's `.json` file using the Langflow runtime.

To use your code in a Python application using the Langflow runtime, you have to first download your flow’s JSON file.

1. In your **Workspace**, click **Settings**, and then select **Export**.

2. Download the flow to your local machine. Make sure the flow path in the script matches the flow’s location on your machine.

3. Copy and paste the code from the API tab into a Python script file.
It will look like this:

```python
from langflow.load import run_flow_from_json
TWEAKS = {
  "ChatInput-kKhri": {},
  "Prompt-KDSi5": {},
  "ChatOutput-Vr3Q7": {},
  "OpenAIModel-4xYtx": {}
}

result = run_flow_from_json(flow="./basic-prompting-local.json",
                            input_value="tell me about something interesting",
                            fallback_to_env_vars=True, # False by default
                            tweaks=TWEAKS)

print(result)
```

4. Run the script:

```python
python3 python-api-script.py
```

## Tweaks

The **Tweaks** tab displays the available parameters for your flow. Modifying the parameters changes the code parameters across all windows. For example, changing the **Chat Input** component's `input_value` will change that value across all API calls.

## Send image files to your flow with the API

For information on sending files to the Langflow API, see [API examples](/api-reference-api-examples#upload-image-files).

## Chat Widget

The **Chat Widget HTML** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

The **Langflow Chat Widget** is a powerful web component that enables communication with a Langflow project. This widget allows for a chat interface embedding, allowing the integration of Langflow into web applications effortlessly.

You can get the HTML code embedded with the chat by clicking the Code button at the Sidebar after building a flow.

Clicking the Chat Widget HTML tab, you'll get the code to be inserted. Read below to learn how to use it with HTML, React and Angular.

### Embed the chat widget into HTML

To embed the chat widget into any HTML page, insert the code snippet. inside a `<body>` tag.

```html
<script src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js""></script>

  <langflow-chat
    window_title="Basic Prompting"
    flow_id="801abb1e-19b9-4278-9632-179b6d84f126"
    host_url="http://localhost:7860"

  ></langflow-chat>
```

### Embed the chat widget with React

To embed the Chat Widget using React, insert this `<script>` tag into the React _index.html_ file, inside the `<body>`tag:

```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```

Declare your Web Component and encapsulate it in a React component.

```javascript
declare global {
  namespace JSX {
    interface IntrinsicElements {
      "langflow-chat": any;
    }
  }
}

export default function ChatWidget({ className }) {
  return (
    <div className={className}>
      <langflow-chat
        chat_inputs='{"your_key":"value"}'
        chat_input_field="your_chat_key"
        flow_id="your_flow_id"
        host_url="langflow_url"
      ></langflow-chat>
    </div>
  );
}
```

Place the component anywhere in your code to display the Chat Widget.

### Embed the chat widget with Angular

To use the chat widget in Angular, first add this `<script>` tag into the Angular _index.html_ file, inside the `<body>` tag.

```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```

When you use a custom web component in an Angular template, the Angular compiler might show a warning when it doesn't recognize the custom elements by default. To suppress this warning, add `CUSTOM_ELEMENTS_SCHEMA` to the module's `@NgModule.schemas`.

- Open the module file (it typically ends with _.module.ts_) where you'd add the `langflow-chat` web component.
- Import `CUSTOM_ELEMENTS_SCHEMA` at the top of the file:

`import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';`

- Add `CUSTOM_ELEMENTS_SCHEMA` to the 'schemas' array inside the '@NgModule' decorator:

```javascript
@NgModule({
  declarations: [
    // ... Other components and directives ...
  ],
  imports: [
    // ... Other imported modules ...
  ],
  schemas: [
    CUSTOM_ELEMENTS_SCHEMA  // Add the CUSTOM_ELEMENTS_SCHEMA here
  ]
})
export class YourModule { }
```

In your Angular project, find the component belonging to the module where `CUSTOM_ELEMENTS_SCHEMA` was added. Inside the template, add the `langflow-chat` tag to include the Chat Widget in your component's view:

```javascript
<langflow-chat  chat_inputs='{"your_key":"value"}'  chat_input_field="your_chat_key"  flow_id="your_flow_id"  host_url="langflow_url"></langflow-chat>
```

:::tip

`CUSTOM_ELEMENTS_SCHEMA` is a built-in schema that allows Angular to recognize custom elements. Adding `CUSTOM_ELEMENTS_SCHEMA` tells Angular to allow custom elements in your templates, and it will suppress the warning related to unknown elements like `langflow-chat`. Notice that you can only use the Chat Widget in components that are part of the module where you added `CUSTOM_ELEMENTS_SCHEMA`.

:::

## Chat widget configuration

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

## Webhook cURL

When a **Webhook** component is added to the workspace, a new **Webhook cURL** tab becomes available in the **API** pane that contains an HTTP POST request for triggering the webhook component. For example:

```bash
curl -X POST \
  "http://127.0.0.1:7860/api/v1/webhook/**YOUR_FLOW_ID**" \
  -H 'Content-Type: application/json'\
  -d '{"any": "data"}'
  ```

To test the **Webhook** component in your flow, see the [Webhook component](/components-data#webhook).

