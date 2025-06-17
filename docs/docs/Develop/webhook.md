---
title: Trigger flows with webhooks
slug: /webhook
---

import Icon from "@site/src/components/icon";

You can use the **Webhook** component in Langflow to make your flows react to external events. By sending data to a specific URL, you can automatically trigger a Langflow flow and process the incoming information.

To see how the **Webhook** component interacts with incoming data, you'll often want to connect it to a **Parser** component. This allows you to inspect and structure the data sent to your webhook. Here's how you can set this up:

1.  **Add a Webhook Component:** Drag and drop a **Webhook** component onto your Langflow canvas. This component will be the entry point for external data.

2.  **Add a Parser Component:** Next, add a [Parser](/components-processing#parser) component to your flow. This component will help you make sense of the raw data received by the webhook.

3.  **Connect the Components:** Link the **Data** output of the **Webhook** component to the **Data** input of the **Parser** component. This ensures that any data received by the webhook is passed on to the parser for processing.

4.  **Define Your Data Structure in the Parser:** In the **Template** field of the **Parser** component, you need to specify how you want to extract information from the incoming data. You define variables within the template that correspond to keys in your data payload, just like you would in a [Prompt](/components-prompts) component.

    For instance, if your webhook receives JSON data like this:

    ```json
    {
      "id": "54321",
      "product": "widget",
      "quantity": 10
    }
    ```

    You can create a template in the **Parser** component to extract these values:

    ```text
    Product ID: {id} - Item: {product} - Count: {quantity}
    ```

    :::important
    Sometimes, the **Parser** component might encounter issues during the flow building process because it anticipates data from the **Webhook**, which hasn't been triggered yet. If you run into build errors, try changing the **Mode** in the **Parser** component to **Stringify**. This will force the parser to output the incoming data as a single string, which can resolve the build issue.
    :::

5.  **Get Your Webhook Endpoint:** The **Webhook** component provides a unique API endpoint that external applications can use to trigger your flow. You'll find this URL in the **Endpoint** field of the **Webhook** component's settings. Copy this URL, as you'll need it to send requests.

6.  **Retrieve an Example Request (Optional):** To get a ready-to-use example of how to send data to your webhook, you can click **Controls** within the **Webhook** component's settings. Look for the **cURL** value field, which contains a sample `curl` command that you can adapt.

7.  **Send a POST Request to Trigger Your Flow:** Now, you can send a POST request to the webhook endpoint with the data you want your flow to process. The data should typically be in JSON format.

    Let's say your flow ID is `my_awesome_flow` and you want to send the product information from the earlier example. You can use a tool like `curl` in your terminal:

    ```bash
    curl -X POST "[http://127.0.0.1:7860/api/v1/webhook/my_awesome_flow](http://127.0.0.1:7860/api/v1/webhook/my_awesome_flow)" \
        -H 'Content-Type: application/json' \
        -d '{"id": "54321", "product": "widget", "quantity": 10}'
    ```

    When Langflow successfully receives your request and starts processing the flow in the background, you'll typically see a response like this:

    ```json
    {"message":"Task started in the background","status":"in progress"}
    ```

8.  **Inspect the Received Data:** To see how the **Parser** component has processed the data from your webhook request, click the <Icon name="TextSearch" aria-label="Inspect icon" /> icon within the **Parser** component.

    You should now see a structured string based on the template you defined earlier, for example: `Product ID: 54321 - Item: widget - Count: 10`.

Congratulations! You've successfully triggered a Langflow flow using a webhook and parsed the incoming JSON data.

By leveraging the **Webhook** component, you can create powerful integrations where external applications or services can directly feed data into your Langflow processes. You can then use this data to trigger further actions within your flow, such as calling other components, interacting with APIs, or updating databases.

## Testing Your Webhooks

When working with webhooks, it's often helpful to have a way to inspect the data being sent to your webhook endpoint. Here are a couple of useful tools for this purpose:

* **Beeceptor:** [https://beeceptor.com/](https://beeceptor.com/) allows you to create temporary, mockable endpoints where you can inspect HTTP requests in real-time. This is great for debugging and understanding the structure of the data your webhook is receiving.

* **HTTPBin:** [https://httpbin.org/](https://httpbin.org/) is another excellent tool for testing HTTP requests. You can send requests to various HTTPBin endpoints (like `/post` to inspect the POST request body) and see the server's response, including the data you sent.

Using these tools, you can easily examine the data being sent to your Langflow webhook endpoint without needing to fully set up the receiving flow initially. This can significantly simplify the development and debugging process.

## Further Applications

Beyond simply parsing the data, you can connect the **Webhook** component to a chain of other Langflow components. This allows you to build sophisticated workflows that react to external events in complex ways. For example, you could:

* Receive customer feedback via a webhook and use a language model to analyze its sentiment.
* Get notifications from a monitoring system and trigger an automated response.
* Integrate with e-commerce platforms to process new orders and update inventory.

The possibilities are vast, and webhooks provide a powerful mechanism for making your Langflow flows truly event-driven and integrated with the wider ecosystem of applications and services you use.

## Trigger Flows with Composio Webhooks

Now that you've triggered the webhook component manually, you can also explore how to trigger flows with payloads from external applications by following this step-by-step video guide: [How to Use Webhooks in Langflow](https://www.youtube.com/watch?v=IC1CAtzFRE0). This video provides a visual demonstration of connecting external services to your Langflow webhooks.
