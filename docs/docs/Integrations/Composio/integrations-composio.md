---
title: Integrate Composio with Langflow
slug: /integrations-composio
---

Langflow integrates with [Composio](https://docs.composio.dev/introduction/intro/overview) as a toolset for your **Agent** component.

Instead of juggling multiple integrations and components in your flow, connect the Composio component to an **Agent** component to use all of Composio's supported APIs and actions as **Tools** for your agent.

## Prerequisites

- [Composio API key created](https://app.composio.dev/)
- [SerpApi API key created](https://serpapi.com/)
- [OpenAI API key created](https://platform.openai.com/)

## Create a Composio tool

1. Navigate to the [Composio application](https://app.composio.dev/dashboard).
In the **Integrations** tab, navigate to the tool you want integrate with Langflow.
This example uses the SerpApi tool in Composio.
Click **Setup Serpapi integration**.
2. To connect Composio to your SerpApi account, in the **API Key** field, paste your SerpApi API key.
3. In the **User ID** field, enter the email address you created your Composio API key with.
You can also use the value `default` for testing.
The **User ID** value will have to match the Langflow component's **Entity ID** value for authentication.
4. Click the **Try connecting serpapi** button.
The **Execute tools** pane opens. Here, you can test the connection to your API.
5. In the **Query** field, enter a `string` to query SerpApi, and then click **Run**.
A successful test returns a SerpApi data object that includes `successful=true`.
Composio is now connected to your SerpApi account.
If the test returns `401, message='Unauthorized`, check your API key and try again.

## Connect Langflow to a Composio tool

1. In the Langflow **Workspace**, add an **Agent** component.
2. In the **Workspace**, add the **Composio Tools** component.
3. Connect the **Agent** component's **Tools** port to the **Composio Tools** component's **Tools** port.
4. In the **Composio API Key** field, paste your Composio API key.
Alternatively, add the key as a [global variable](/configuration-global-variables).
5. In the **App Name** field, select the tool you want your Agent to have access to.
For this example, select **SerpApi**.
6. Click **Refresh**.
The component's fields change based on the tool you selected.
7. In the **API Key** field, paste your SerpApi API key.
Alternatively, add the key as a [global variable](/configuration-global-variables).
8. Ensure the **Composio** component's **User ID** value matches the Langflow component's **Entity ID**.
9. Click **Refresh**.
The **Auth Status** field changes to a ✅, which indicates the Langflow component is connected to your Composio account.

:::important
If you created your Composio component in Langflow **before** creating the tool in Composio, you have to refresh the component again for it to incorporate the changes in your account.
:::

10. In the **Actions to use** field, select the search action you want the **Agent** to take with the **SerpApi** tool.
The **SerpApi** integration supports multiple actions, and also supports multiple actions within the same tool.
The default value of **SERPAPI_DUCK_DUCK_GO_SEARCH** is OK for this example.
For more information, see the [Composio documentation](https://docs.composio.dev/patterns/tools/use-tools/use-specific-actions).

## Create a Composio flow

1. In the **Workspace**, add **Chat Input** and **Chat Output** components to your flow.
2. Connect the components so they look like this.

![Create Composio Flow](/img/composio/composio-create-flow.png)

3. In the **OpenAI API Key** field of the **Agent** component, paste your OpenAI API key.
Alternatively, add the key as a [global variable](/configuration-global-variables).
4. To open the **Playground** pane, click **Playground**.
5. Ask your AI:
```plain
What tools are available to you?
```
The response should be similar to:

```plain
I have access to the following tools:
SERPAPI_SEARCH: This tool allows me to perform Google searches and retrieve relevant information based on a specified query.
Current Date and Time: This tool provides the current date and time in various time zones.
```

This confirms your **Agent** and **Composio** are communicating.

6. Ask your AI another question about something you're interested in.
```plain
Please perform a SERPAPI search on unicorns.
```

Inspect the response to see how the agent used the attached tool to perform your search.
The response should include a successful query, and useful information on the subject.
This example response is abbreviated.
```json
{
  "query": "unicorns"
}

{
  "successfull": true,
  "data": {
    "results": {
      "search_metadata": {
        "id": "675226c41a5b5406f78646c9",
        "status": "Success",
        "json_endpoint": "https://serpapi.com/searches/ac6e045fbff6af64/675226c41a5b5406f78646c9.json",
        "created_at": "2024-12-05 22:18:44 UTC",
        "processed_at": "2024-12-05 22:18:44 UTC",
        "google_url": "https://www.google.com/search?q=unicorns&oq=unicorns&sourceid=chrome&ie=UTF-8",
        "raw_html_file": "https://serpapi.com/searches/ac6e045fbff6af64/675226c41a5b5406f78646c9.html",
        "total_time_taken": 1.86
      },
```

You have successfully integrated your Langflow component with Composio.
To add more tools, add another Composio component.