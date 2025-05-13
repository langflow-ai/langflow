---
title: Trigger flows with webhooks
slug: /webhook
---

import Icon from "@site/src/components/icon";

Add a **Webhook** component to your flow to trigger it with external requests.

To connect the **Webhook** to a **Parser** component to view and parse your data payload, do the following:

1. Add a **Webhook** component to your flow.
2. Add a [Parser](/components-processing#parser) component to your flow.
3. Connect the **Webhook** component's **Data** output to the **Parser** component's **Data** input.
4. In the **Template** field of the **Parser** component, enter a template for parsing the **Webhook** component's input into structured text.
    :::important
    The component may fail to build because it needs data from the **Webhook** first.
    If you experience issues, change the **Mode** on the **Parser** component to **Stringify**, so the component outputs a single string.
    :::
    Create variables for values in the `template` the same way you would in a [Prompt](/components-prompts) component.
    For example, to parse `id`, `name`, and `email` strings:
    ```text
    ID: {id} - Name: {name} - Email: {email}
    ```

5. In the **Endpoint** field of the **Webhook** component, copy the API endpoint for your external requests.
6. Optionally, to retrieve a complete example request from the component, click **Controls**, and then copy the command from the **cURL** value field.
    :::important
    The default curl command includes a field for `x-api-key`. This field is **optional** and can be deleted from the command if you aren't using authentication.
    :::
7. Send a POST request with any data to trigger your flow.
This example uses `id`, `name`, and `email` strings.
Replace **YOUR_FLOW_ID** with your flow ID.
    ```text
    curl -X POST "http://127.0.0.1:7860/api/v1/webhook/YOUR_FLOW_ID" \
        -H 'Content-Type: application/json' \
        -d '{"id": "12345", "name": "alex", "email": "alex@email.com"}'
    ```

    This response indicates Langflow received your request:

    ```text
    {"message":"Task started in the background","status":"in progress"}
    ```

8. To view the data received from your request, in the **Parser** component, click <Icon name="TextSearch" aria-label="Inspect icon" />.

You should receive a string of parsed text, like `ID: 12345 - Name: alex - Email: alex@email.com`.

You have successfully parsed data out of an external JSON payload.

By passing the event trigger data payload directly into a flow, you can also parse the event data with a chain of components, and use its data to trigger other events.

## Trigger flows with Composio webhooks

Now that you've triggered the webhook component manually, follow along with this step-by-step video guide for triggering flows with payloads from external applications: [How to Use Webhooks in Langflow](https://www.youtube.com/watch?v=IC1CAtzFRE0).