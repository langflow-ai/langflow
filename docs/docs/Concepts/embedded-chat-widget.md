---
title: Embedded chat widget
slug: /embedded-chat-widget
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import ChatWidget from '@site/src/components/ChatWidget';

On the [Publish pane](/concepts-publish), the **Embed into site** tab displays code that can be inserted in the `<body>` of your HTML to interact with your flow.

The chat widget is implemented as a web component called `langflow-chat` and is loaded from a CDN. For more information, see the [langflow-embedded-chat repository](https://github.com/langflow-ai/langflow-embedded-chat).

For a sandbox example, see the [Langflow embedded chat CodeSandbox](https://codesandbox.io/p/sandbox/langflow-embedded-chat-example-dv9zpx).

The following example includes the minimum required inputs, called [props](https://react.dev/learn/passing-props-to-a-component) in React, for using the chat widget in your HTML code, which are `host_url` and `flow_id`.
The `host_url` value must be `HTTPS`, and may not include a `/` after the URL.
The `flow_id` value is found in your Langflow URL.
For a Langflow server running the [Basic prompting flow](/basic-prompting) at `https://c822-73-64-93-151.ngrok-free.app/flow/dcbed533-859f-4b99-b1f5-16fce884f28f`, your chat widget code is similar to the following:
```html
<html>
  <head>
    <script src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
  </head>
  <body>
    <langflow-chat
      host_url="https://c822-73-64-93-151.ngrok-free.app"
      flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    ></langflow-chat>
  </body>
</html>
```

When this code is embedded within HTML, it becomes a responsive chatbot, powered by the basic prompting flow.

![Default chat widget](/img/chat-widget-default.png)

To configure your chat widget further, include additional props.

All props and their types are listed in [index.tsx](https://github.com/langflow-ai/langflow-embedded-chat/blob/main/src/index.tsx).

To add some styling to the chat widget, customize its elements with JSON:
```html
  <langflow-chat
    host_url="https://c822-73-64-93-151.ngrok-free.app"
    flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    chat_window_style='{
      "backgroundColor": "#1a0d0d",
      "border": "4px solid #b30000",
      "borderRadius": "16px",
      "boxShadow": "0 8px 32px #b30000",
      "color": "#fff",
      "fontFamily": "Georgia, serif",
      "padding": "16px"
    }'
    window_title="Custom Styled Chat"
    height="600"
    width="400"
  ></langflow-chat>
```

To add a custom [session ID](/session-id) value and an API key for authentication to your Langflow server:
```html
<html>
  <head>
    <script src="https://cdn.jsdelivr.net/gh/logspace-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
  </head>
  <body>
    <langflow-chat
      host_url="https://c822-73-64-93-151.ngrok-free.app"
      flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
      api_key="YOUR_API_KEY"
      session_id="YOUR_SESSION_ID"
    ></langflow-chat>
  </body>
</html>
```

The chat widget requires your flow to contain **Chat Input** and **Chat Output** components for the widget to communicate with it.
Sending a message to Langflow without a **Chat Input** still triggers the flow, but the LLM warns you the message is empty.
**Text Input** and **Text Output** components can send and receive messages with Langflow, but without the ongoing LLM "chat" context.

## Embed the chat widget with React

To use the chat widget in your React application, create a component that loads the widget script and renders the chat interface:

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
        host_url="https://c822-73-64-93-151.ngrok-free.app"
        flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
      ></langflow-chat>
    </div>
  );
}
```
2. Place the component anywhere in your code to display the chat widget.

For example, in this docset, the React widget component is located at `docs > src > components > ChatWidget > index.tsx`.
`index.tsx` includes a script to load the chat widget code from CDN and initialize the `ChatWidget` component with props pointing to a Langflow server.
```javascript
import React, { useEffect } from 'react';

// Component to load the chat widget script
const ChatScriptLoader = () => {
  useEffect(() => {
    if (!document.querySelector('script[src*="langflow-embedded-chat"]')) {
      const script = document.createElement('script');
      script.src = 'https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js';
      script.async = true;
      document.body.appendChild(script);
    }
  }, []);

  return null;
};

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
      <ChatScriptLoader />
      <langflow-chat
        host_url="https://c822-73-64-93-151.ngrok-free.app"
        flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
      ></langflow-chat>
    </div>
  );
}
```

3. To import the component to your page, add this to your site.
```
import ChatWidget from '@site/src/components/ChatWidget';
```
4. To add the widget to your page, include `<ChatWidget className="my-chat-widget" />`.

## Embed the chat widget with Angular

To use the chat widget in your [Angular](https://angular.dev/overview) application, create a component that loads the widget script and renders the chat interface.

Angular requires you to explicitly allow custom web components like `langflow-chat` in components, so you must add the `<langflow-chat>` element to your Angular template and configure Angular to recognize it. Add `CUSTOM_ELEMENTS_SCHEMA` to your module's configuration to enable this.

To add `CUSTOM_ELEMENTS_SCHEMA` to your module's configuration, do the following:

1. Open the module file `.module.ts` where you want to add the `langflow-chat` web component.
2. Import `CUSTOM_ELEMENTS_SCHEMA` at the top of the `.module.ts` file:

`import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';`

3. Add `CUSTOM_ELEMENTS_SCHEMA` to the `schemas` array inside the `@NgModule` decorator:

```javascript
import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
import { BrowserModule } from '@angular/platform-browser';
import { AppComponent } from './app.component';

@NgModule({
  declarations: [
    AppComponent
  ],
  imports: [
    BrowserModule
  ],
  schemas: [CUSTOM_ELEMENTS_SCHEMA],
  providers: [],
  bootstrap: [AppComponent]
})
export class AppModule { }
```

4. Add the chat widget to your component's template by including the `langflow-chat` element in your component's `.component.ts` file:

For style properties that accept `JSON` objects like `chat_window_style` and `bot_message_style`, use Angular's property binding syntax `[propertyName]` to pass them as JavaScript objects.

```javascript
import { Component } from '@angular/core';

@Component({
  selector: 'app-root',
  template: `
    <div class="container">
      <h1>Langflow Chat Test</h1>
      <langflow-chat
        host_url="https://c822-73-64-93-151.ngrok-free.app"
        flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
        [chat_window_style]='{"backgroundColor": "#ffffff"}'
        [bot_message_style]='{"color": "#000000"}'
        [user_message_style]='{"color": "#000000"}'
        window_title="Chat with us"
        placeholder="Type your message..."
        height="600"
        width="400"
        chat_position="bottom-right"
      ></langflow-chat>
    </div>
  `,
  styles: [`
    .container {
      padding: 20px;
      text-align: center;
    }
  `]
})
export class AppComponent {
  title = 'Langflow Chat Test';
}
```

## Chat widget configuration

Use the widget API to customize your chat widget.

Props with the type `JSON` need to be passed as stringified JSON, with the format \{"key":"value"\}.

All props and their types are listed in [index.tsx](https://github.com/langflow-ai/langflow-embedded-chat/blob/main/src/index.tsx).

| Prop                  | Type    | Description                                    |
|----------------------|---------|------------------------------------------------|
| flow_id              | String  | Required. Identifier for the flow associated with the component. |
| host_url             | String  | Required. URL of the host for communication with the chat component. |
| api_key              | String  | X-API-Key header to send to Langflow. |
| additional_headers   | JSON    | Additional headers to be sent to the Langflow server. |
| session_id           | String  | Custom session id to override the random session id. |
| height               | Number  | Height of the chat window in pixels. |
| width                | Number  | Width of the chat window in pixels. |
| chat_position        | String  | Position of chat window, such as `top-right` or `bottom-left`. |
| start_open           | Boolean | Whether the chat window should be open by default. |
| chat_window_style    | JSON    | Overall chat window appearance. |
| chat_trigger_style   | JSON    | Chat trigger button styling. |
| bot_message_style    | JSON    | Bot message formatting. |
| user_message_style   | JSON    | User message formatting. |
| error_message_style  | JSON    | Error message formatting. |
| input_style          | JSON    | Chat input field styling. |
| input_container_style| JSON    | Input container styling. |
| send_button_style    | JSON    | Send button styling. |
| send_icon_style      | JSON    | Send icon styling. |
| window_title         | String  | Title displayed in the chat window header. |
| placeholder          | String  | Placeholder text for the chat input field. |
| placeholder_sending  | String  | Placeholder text while sending a message. |
| online               | Boolean | Whether the chat component is online. |
| online_message       | String  | Custom message when chat is online. |
| input_type           | String  | Input type for chat messages. |
| output_type          | String  | Output type for chat messages. |
| output_component     | String  | Output ID when multiple outputs are present. |
| chat_output_key      | String  | Which output to display if multiple outputs are available. |
| tweaks               | JSON    | Additional custom adjustments for the flow. |