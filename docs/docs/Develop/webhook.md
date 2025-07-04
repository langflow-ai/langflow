---
title: Trigger flows with webhooks
slug: /webhook
---

import Icon from "@site/src/components/icon";

You can use the **Webhook** component to start a flow run in response to an external event.

With the **Webhook** component, a flow can receive data directly from external sources. Then, the flow can parse the data and pass it to other components in the flow to initiate other actions, such as calling APIs, writing to databases, and chatting with LLMs.

The **Webhook** component provides a versatile entrypoint that can make your flows more event-driven and integrated with your entire stack of applications and services.
For example:

* Use an LLM to analyze the sentiment and content of customer feedback or survey responses.
* Get notifications from a monitoring system, and then trigger a variety of automated responses based on the notification type and severity level.
* Integrate with e-commerce platforms to process orders and update inventory.

## Configure the Webhook component

To use the **Webhook** component in a flow, do the following:

1. In Langflow, open the flow where you want use the **Webhook** component.

2. Add a [**Webhook** component](/components-data#webhook) and a [**Parser** component](/components-processing#parser) to your flow.

    The **Parser** component extracts relevant data from the raw payload received by the **Webhook** component.

3. Connect the Webhook component's **Data** output to the Parser component's **Data** input.

4. In the Parser component's **Template** field, enter a template to parse the raw payload into structured text.

    In the template, use variables for payload keys in the same way you would define variables in a [**Prompt** component](/components-prompts).

    For example, assume that you expect your **Webhook** component to receive the following JSON data:

    ```json
    {
      "id": "",
      "name": "",
      "email": ""
    }
    ```

    Then, you can use curly braces to reference the JSON keys anywhere in your parser template:

    ```text
    ID: {id} - Name: {name} - Email: {email}
    ```

5. Connect the Parser component's **Parsed Text** output to the next logical component in your flow, such as a Chat Input component.

    If you want to test only the Webhook and Parser components, you can connect the **Parsed Text** output directly to a Chat Output component's **Text** input. Then, you can see the parsed data in the **Playground** after you run the flow.

6. From the Webhook component's **Endpoint** field, copy the API endpoint that you will use to send data to the Webhook component and trigger the flow.

    Alternatively, to get a complete `POST /v1/webhook/$FLOW_ID` code snippet, open the flow's [**API access** pane](/concept-publish#api-access), and then click the **Webhook cURL** tab.

    You can also modify the default curl command in the Webhook component's **cURL** field.
    If this field isn't visible by default, click the Webhook component, and then click **Controls** in the component's header menu.

7. Send a POST request with `data` to the flow's `webhook` endpoint to trigger the flow.

    The following example sends a payload containing `id`, `name`, and `email` strings:

    ```bash
    curl -X POST "$LANGFLOW_SERVER_URL/api/v1/webhook/$FLOW_ID" \
        -H 'Content-Type: application/json' \
        -d '{"id": "12345", "name": "alex", "email": "alex@email.com"}'
    ```

    A successful response indicates that Langflow started the flow:

    ```json
    {
      "message": "Task started in the background",
      "status": "in progress"
    }
    ```

    The output for the entire flow isn't returned by the `webhook` endpoint.

8. To view the flow's most recent parsed payload, click the **Parser** component, and then click <Icon name="TextSearch" aria-hidden="true"/> **Inspect output**.
For the preceding example, the parsed payload would be a string like `ID: 12345 - Name: alex - Email: alex@email.com`.

## Troubleshoot Parser component build failure

The **Parser** component can fail to build if it doesn't receive data from the **Webhook** component or if there is a problem with the incoming data.

If this occurs, try changing the Parser component's **Mode** to **Stringify** so that the component outputs the parsed payload as a single string.

Then, you can examine the string output and troubleshoot your parsing template, or work with the parsed data in string form.

## Trigger flows with Composio webhooks

Typically, you won't manually trigger the webhook component.
To learn about triggering flows with payloads from external applications, see the video tutorial [How to Use Webhooks in Langflow](https://www.youtube.com/watch?v=IC1CAtzFRE0).

## See also

- [Webhook component](/components-data#webhook)
- [Flow trigger endpoints](/api-flows-run)