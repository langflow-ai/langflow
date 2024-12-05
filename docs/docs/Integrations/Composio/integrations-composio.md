---
title: Integrate Composio with Langflow
slug: /integrations-composio
---

Langflow integrates with [Composio](https://docs.composio.dev/introduction/intro/overview) as a toolset for your **Agent** component.

## Prerequisites

- [Composio API key created](https://app.composio.dev/)
- [SerpApi API key created](https://serpapi.com/)



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
For this example, we're using **SerpApi**.
6. Click **Refresh**.
The component's fields change based on the tool you selected.
7. In the **API Key** field, paste your SerpApi API key.
Alternatively, add the key as a [global variable](/configuration-global-variables).
8. Ensure the **Composio** component's **User ID** value matches the Langflow component's **Entity ID**.
9. Click **Refresh**.
The **Auth Status** field changes to a ✅, which indicates the Langflow component is connected to your Composio account.

:::important
If you created your Composio components in Langflow before connecting the tool, you have to refresh the tool again for it to incorporate the changes in your account.
:::

10. In the **Actions to use** field, select the search action you want the **Agent** to take with the **SerpApi** tool.
The **SerpApi** integration supports multiple actions.
The default value of **SERPAPI_DUCK_DUCK_GO_SEARCH** is OK for this example.
For more information, see the [Composio documentation](https://docs.composio.dev/patterns/tools/use-tools/use-specific-actions).

## Create a Composio flow

1. In the **Workspace**, add a **Chat Input** and **Chat Output** components to your flow.
2. Connect the components so they look like this.

![Create Composio Flow](/img/composio/composio-create-flow.png)