---
title: Share and embed flows
slug: /concepts-publish
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Langflow provides several ways to share and integrate your flows into external applications:

* [Trigger flows with the Langflow API](#api-access)
* [Add an embedded chat widget to a website](#embedded-chat-widget)
* [Access a Langflow MCP server](#access-a-langflow-mcp-server)
* [Share a public flow Playground](#share-a-flows-playground)

Although you can use these options with an isolated, local Langflow instance, they are typically more valuable when you have deployed a Langflow server or packaged Langflow as a dependency of an application.
For more information, see [Deployment overview](/deployment-overview) and [Application development overview](/develop-application).

## Use the Langflow API to run flows {#api-access}

The Langflow API is the primary way to access your flows and Langflow servers programmatically.

:::tip Try it
For an example of a script that calls the Langflow API, see the [Quickstart](/get-started-quickstart).
:::

### Generate API code snippets

To help you embed Langflow API requests in your scripts, Langflow automatically generates Python, JavaScript, and curl code snippets for your flows.
To get these code snippets, do the following:

1. In Langflow, open the flow that you want to embed in your application.
2. Click **Share**, and then select **API access**.

    These code snippets call the `/v1/run/$FLOW_ID` endpoint, and they automatically populate minimum values, like the Langflow server URL, flow ID, headers, and request parameters.

    ![API access pane](/img/api-pane.png)

3. Optional: Click [**Input Schema**](#input-schema) to modify component parameters in the code snippets without changing the flow itself.

4. Copy the snippet for the language that you want to use.

5. Run the snippet as is, or use the snippet in the context of a larger script.

For more information and examples of other Langflow API endpoints, see [Get started with the Langflow API](/api-reference-api-examples).

### Langflow API authentication

In Langflow versions 1.5 and later, most API endpoints require authentication with a Langflow API key.
The only exceptions are the MCP endpoints `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`, which never require authentication.

Code snippets generated in the **API access** pane include a script that checks for a `LANGFLOW_API_KEY` environment variable set in the local terminal session.
This script doesn't check for Langflow API keys set anywhere besides the local terminal session.

For this script to work, you must set a `LANGFLOW_API_KEY` variable in the terminal session where you intend to run the code snippet, such as `export LANGFLOW_API_KEY="sk..."`.

Alternatively, you can edit the code snippet to include an `x-api-key` header and ensure that the request can authenticate to the Langflow API.

For more information, see [API keys](/configuration-api-keys) and [Get started with the Langflow API](/api-reference-api-examples)

### Input Schema (tweaks) {#input-schema}

Tweaks are one-time overrides that modify component parameters for at runtime, rather than permanently modifying the flow itself.
For an example of tweaks in a script, see the [Quickstart](/get-started-quickstart).

:::tip
Tweaks make your flows more dynamic and reusable.

You can create one flow and use it for multiple applications by passing application-specific tweaks in each application's Langflow API requests.
:::

In the **API access** pane, click **Input Schema** to add `tweaks` to the request payload in a flow's code snippets.

Changes to a flow's **Input Schema** are saved exclusively as tweaks for that flow's **API access** code snippets.
These tweaks don't change the flow parameters set in the **Workspace**, and they don't apply to other flows.

Adding tweaks through the **Input Schema** can help you troubleshoot formatting issues with tweaks that you manually added to Langflow API requests.

### Use a flow ID alias

If you want your requests to use an alias instead of the actual flow ID, you can rename the flow's `/v1/run/$FLOW_ID` endpoint:

1. In Langflow, open the flow, click **Share**, and then select **API access**.
2. Click **Input Schema**.
3. In the **Endpoint Name** field, enter an alias for your flow's ID, such as a memorable, human-readable name.

    The name can contain only letters, numbers, hyphens, and underscores, such as `flow-customer-database-agent`.

4. To save the change, close the **Input Schema** pane.

The automatically generated code snippets now use your new endpoint name instead of the original flow ID, such as `url = "http://localhost:7868/api/v1/run/flow-customer-database-agent`.

## Embed a flow into a website {#embedded-chat-widget}

For each flow, Langflow provides a code snippet that you can insert into the `<body>` of your website's HTML to interact with your flow through an embedded chat widget.

:::important Required components
The chat widget only supports flows that have **Chat Input** and **Chat Output** components, which are required for the chat experience.
**Text Input** and **Text Output** components can send and receive messages, but they don't include ongoing LLM chat context.

Attempting to chat with a flow that doesn't have a valid input component will trigger the flow, but the response only indicates that the input was empty.
:::

### Get a langflow-chat snippet

To get a flow's embedded chat widget code snippet, do the following:

1. In Langflow, open the flow you want to embed.
2. Click **Share**, and then select **Embed into site**.
3. Copy the code snippet and use it in the `<body>` of your website's HTML.

The chat widget is implemented as a web component called `langflow-chat` that is loaded from a CDN. For more information, see the [langflow-embedded-chat repository](https://github.com/langflow-ai/langflow-embedded-chat).

For example, the following HTML embeds a chat widget for a [Basic prompting flow](/basic-prompting) hosted on a Langflow server deployed on ngrok:

```html
<html>
  <head>
    <script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@main/dist/build/static/js/bundle.min.js"></script>
  </head>
  <body>
    <langflow-chat
      host_url="https://c822-73-64-93-151.ngrok-free.app"
      flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    ></langflow-chat>
  </body>
</html>
```

When this code is deployed to a live site, it renders as a responsive chatbot.
If a user interacts with the chatbot, the input triggers the specified flow, and then the chatbot returns the output from the flow run.

![Default chat widget](/img/chat-widget-default.png)

:::tip Try it
Use the [Langflow embedded chat CodeSandbox](https://codesandbox.io/p/sandbox/langflow-embedded-chat-example-dv9zpx) for an interactive live demo of the embedded chat widget that uses your own flow.
For more information, see the [langflow-embedded-chat README](https://github.com/langflow-ai/langflow-embedded-chat?tab=readme-ov-file#live-example).
:::

### Embed the chat widget with React, Angular, or HTML

The following examples show how to use embedded chat widget in React, Angular, and plain HTML.

<Tabs>
  <TabItem value="react" label="React" default>

To use the chat widget in your React application, create a component that loads the widget script and renders the chat interface:

1. Declare your web component, and then encapsulate it in a React component:

    ```javascript
    //Declaration of langflow-chat web component
    declare global {
    namespace JSX {
        interface IntrinsicElements {
        "langflow-chat": any;
        }
    }
    }

    //Definition for langflow-chat React component
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

2. Place the component anywhere in your code to render the chat widget.

    In the following example, the React widget component is located at `docs/src/components/ChatWidget/index.tsx`, and `index.tsx` includes a script to load the chat widget code from CDN, along with the declaration and definition from the previous step:

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

    //Declaration of langflow-chat web component
    declare global {
    namespace JSX {
        interface IntrinsicElements {
        "langflow-chat": any;
        }
    }
    }

    //Definition for langflow-chat React component
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

3. Import the `langflow-chat` React component to make it available for use on a page.
Modify the following import statement with your React component's name and path:

    ```jsx
    import ChatWidget from '@site/src/components/ChatWidget';
    ```

4. To display the widget, call your `langflow-chat` component in the desired location on the page.
Modify the following reference for your React component's name and the desired `className`:

   ```
   <ChatWidget className="my-chat-widget" />
   ```

  </TabItem>
  <TabItem value="angular" label="Angular">

To use the chat widget in your Angular application, create a component that loads the widget script and renders the chat interface.

In an Angular application, `langflow-chat` is a custom web component that you must explicitly allow in your site's `.components.ts`.
Therefore, to use the embedded chat widget, you must add `CUSTOM_ELEMENTS_SCHEMA` to your module's configuration, and then integrate the `<langflow-chat>` element.

Angular requires you to explicitly allow custom web components, like `langflow-chat`, in your site's  `components`.
Therefore, you must add the `<langflow-chat>` element to your Angular template and configure Angular to recognize it.
You must add `CUSTOM_ELEMENTS_SCHEMA` to your module's configuration to enable this.

1. In your Angular application, edit the `.module.ts` file where you want to add the `langflow-chat` web component.

2. At the top of `.module.ts`, import `CUSTOM_ELEMENTS_SCHEMA`:

    ```
    import { NgModule, CUSTOM_ELEMENTS_SCHEMA } from '@angular/core';
    ```

3. In the `@NgModule` decorator, add `CUSTOM_ELEMENTS_SCHEMA` to the `schemas` array:

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

4. Edit the `.component.ts` file where you want to use the embedded chat widget.

5. In the `@Component` decorator, add the `<langflow-chat>` element to the `template` key:

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

  </TabItem>
  <TabItem value="html" label="HTML">

```html
<html lang="en">
<head>
<script src="https://cdn.jsdelivr.net/gh/langflow-ai/langflow-embedded-chat@v1.0.7/dist/build/static/js/bundle.min.js"></script>
</head>
<body>
<langflow-chat
    host_url="https://c822-73-64-93-151.ngrok-free.app"
    flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
  ></langflow-chat>
</body>
</html>
```

  </TabItem>
</Tabs>

### Configure the langflow-chat web component

To use the embedded chat widget in your HTML, the `langflow-chat` web component must include the following minimum inputs (also known as _props_ in React):

* `host_url`: Your Langflow server URL. Must be `HTTPS`. Don't include a trailing slash (`/`).
* `flow_id`: The ID of the flow you want to embed.

The minimum inputs are automatically populated in the [**Embed into site** code snippet](#get-a-langflow-chat-snippet) that is generated by Langflow.

You can use additional inputs (props) to modify the embedded chat widget.
For a list of all props, types, and descriptions, see the [langflow-embedded-chat README](https://github.com/langflow-ai/langflow-embedded-chat?tab=readme-ov-file#configuration).

:::tip
The `api_key` prop isn't required, but it's recommended to ensure the widget has permission to run the flow.
:::

<details>
<summary>Example: Langflow API key prop</summary>

The `api_key` prop stores a Langflow API key that the chat widget can use to authenticate the underlying Langflow API request.

The Langflow team recommends following industry best practices for handling sensitive credentials.
For example, securely store your API key, and then retrieve with an environment variable:

```html
<langflow-chat
    host_url="https://c822-73-64-93-151.ngrok-free.app"
    flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    api_key="$LANGFLOW_API_KEY"
></langflow-chat>
```

</details>

<details>
<summary>Example: Style props</summary>

There are many props you can use to customize the style and positioning of the embedded chat widget.
Many of these props are of type JSON, and they require specific formatting, depending on where you embed the `langflow-chat` web component.

In React and plain HTML, JSON props are expressed as JSON objects or stringified JSON, such as `\{"key":"value"\}`:

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

For Angular applications, use [property binding syntax](https://angular.dev/guide/templates/binding#binding-dynamic-properties-and-attributes) to pass JSON props as JavaScript objects.
For example:

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

</details>

<details>
<summary>Example: Session ID prop</summary>

The following example adds a custom [session ID](/session-id) to help identify flow runs started by the embeded chat widget:

```html
<langflow-chat
    host_url="https://c822-73-64-93-151.ngrok-free.app"
    flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    session_id="$SESSION_ID"
></langflow-chat>
```

</details>

<details>
<summary>Example: Tweaks prop</summary>

Use the `tweaks` prop to modify flow parameters at runtime.
The available keys for the `tweaks` object depend on the flow you are serving through the embedded chat widget.

In React and plain HTML, `tweaks` are declared as a JSON object, similar to how you would pass them to a Langflow API endpoint like [`/v1/run/$FLOW_ID`](/api-flows-run#run-flow).
For example:

```html
<langflow-chat
    host_url="https://c822-73-64-93-151.ngrok-free.app"
    flow_id="dcbed533-859f-4b99-b1f5-16fce884f28f"
    tweaks='{
        "model_name": "llama-3.1-8b-instant"
    }'
></langflow-chat>
```

For Angular applications, use [property binding syntax](https://angular.dev/guide/templates/binding#binding-dynamic-properties-and-attributes) to pass JSON props as JavaScript objects.
For example:

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
        [tweaks]='{"model_name": "llama-3.1-8b-instant"}'
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

</details>

## Access a Langflow MCP server

Each [Langflow project](/concepts-flows#projects) has an MCP server that exposes the project's flows as [tools](https://modelcontextprotocol.io/docs/concepts/tools) that [MCP clients](https://modelcontextprotocol.io/clients) can use to generate responses.

You can also use Langflow as an MCP client, and you can serve your flows as tools to a Langflow MCP client.

For more information, see [Use Langflow as an MCP server](/mcp-server) and [Use Langflow as an MCP client](/mcp-client).

## Share a flow's Playground

:::important
The **Shareable Playground** is for testing purposes only.

The **Playground** isn't meant for embedding flows in applications. For information about running flows in applications or websites, see the following:

* [Embed a flow into a website](#embedded-chat-widget)
* [Use the Langflow API to run flows](#api-access)
* [About developing and configuring Langflow applications](/develop-overview)
:::

The **Shareable Playground** option exposes the [**Playground**](/concepts-playground) for a single flow at the `/public_flow/$FLOW_ID` endpoint.

After you [deploy a public Langflow server](/deployment-overview), you can share this public URL with another user to allow them to access the specified flow's **Playground** only.
The user can interact with the flow's chat input and output and view the results without installing Langflow or generating a Langflow API key.

To share a flow's **Playground** with another user, do the following:

1. In Langflow, open the flow you want share.
2. From the **Workspace**, click **Share**, and then enable **Shareable Playground**.
3. Click **Shareable Playground** again to open the **Playground** window.
This window's URL is the flow's **Shareable Playground** address, such as `https://3f7c-73-64-93-151.ngrok-free.app/playground/d764c4b8-5cec-4c0f-9de0-4b419b11901a`.
4. Send the URL to another user to give them access to the flow's **Playground**.

## See also

* [Develop an application with Langflow](/develop-application)
* [Langflow deployment overview](/deployment-overview)
* [Import and export flows](/concepts-flows-import)
* [Files endpoints](/api-files)