---
title: Publish flows
slug: /concepts-publish
---
import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow provides several ways to publish and integrate your flows into external applications. Whether you want to expose your flow as an API endpoint, embed it as a chat widget in your website, or share it as a public playground, this guide covers the options available for making your flows accessible to users.

## API access

The **API access** pane presents code templates for integrating your flow into external applications.

![](/img/api-pane.png)

<Tabs>

<TabItem value="Python" label="Python">

The **Python** tab displays code to interact with your flow using the Python `requests` library.

1. Copy and paste the code into a Python script.
2. Run the script.

```python
python3 python-test-script.py --message="tell me about something interesting"
```

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>

<TabItem value="JavaScript" label="JavaScript" default>

The **JavaScript API** tab displays code to interact with your flow in JavaScript.

1. Copy and paste the code into a JavaScript file.
2. Run the script.

```text
node test-script.js "tell me about something interesting"
```

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>
<TabItem value="curl" label="curl" default>

The **cURL** tab displays sample code for posting a query to your flow.

Copy the code and run it to post a query to your flow and get the result.

The response content depends on your flow. Make sure the endpoint returns a successful response.

</TabItem>
</Tabs>

### Temporary overrides

The **Temporary overrides** tab displays the available parameters for your flow.
Modifying the parameters changes the code parameters across all windows.
For example, changing the **Chat Input** component's `input_value` changes that value across all API calls to the `/run` endpoint of this flow.

### Send files to your flow with the API

For information on sending files to the Langflow API, see [API examples](/api-reference-api-examples#upload-image-files-v1).

### Webhook cURL

When a **Webhook** component is added to the workspace, a new **Webhook cURL** tab becomes available in the **API** pane that contains an HTTP POST request for triggering the webhook component. For example:

```bash
curl -X POST \
  "http://127.0.0.1:7860/api/v1/webhook/**YOUR_FLOW_ID**" \
  -H 'Content-Type: application/json'\
  -d '{"any": "data"}'
```

To test the **Webhook** component in your flow, see the [Webhook component](/components-data#webhook).

## Embed into site

The **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

```html
<script src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js""></script>

  <langflow-chat
    window_title="Basic Prompting"
    flow_id="801abb1e-19b9-4278-9632-179b6d84f126"
    host_url="http://localhost:7860"

  ></langflow-chat>
```

### Embed the chat widget with React

To embed the Chat Widget using React, add this `<script>` tag to the React `index.html` file inside a `<body>`tag.

```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```

1. Declare your web component and encapsulate it in a React component.

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
2. Place the component anywhere in your code to display the chat widget.

### Embed the chat widget with Angular

To use the chat widget in Angular, add this `<script>` tag to the Angular `index.html` file inside a `<body>` tag.

```javascript
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
```

When you use a custom web component in an Angular template, the Angular compiler might show a warning when it doesn't recognize the custom elements by default. To suppress this warning, add `CUSTOM_ELEMENTS_SCHEMA` to the module's `@NgModule.schemas`.
`CUSTOM_ELEMENTS_SCHEMA` is a built-in schema that allows custom elements in your Angular templates, and suppresses warnings related to unknown elements like `langflow-chat`.

1. Open the module file `.module.ts` where you want to add the `langflow-chat` web component.
2. Import `CUSTOM_ELEMENTS_SCHEMA` at the top of the `.module.ts` file:

`import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';`

3. Add `CUSTOM_ELEMENTS_SCHEMA` to the 'schemas' array inside the '@NgModule' decorator:

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

4. In your Angular project, find the component belonging to the module where `CUSTOM_ELEMENTS_SCHEMA` was added. Inside the template, add the `langflow-chat` tag to include the chat widget in your component's view:

```javascript
<langflow-chat  chat_inputs='{"your_key":"value"}'  chat_input_field="your_chat_key"  flow_id="your_flow_id"  host_url="langflow_url"></langflow-chat>
```

### Chat widget configuration

Use the widget API to customize your Chat Widget.

Props with the type JSON need to be passed as stringified JSONs, with the format \{"key":"value"\}.

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

## Shareable playground

The **Shareable playground** exposes your Langflow application's **Playground** at the `/public_flow/{flow-id}` endpoint.

You can share this endpoint publicly using a sharing platform like [Ngrok](https://ngrok.com/docs/getting-started/?os=macos) or [zrok](https://docs.zrok.io/docs/getting-started).

If you're using **Datastax Langflow**, you can share the URL with any users within your **Organization**.

