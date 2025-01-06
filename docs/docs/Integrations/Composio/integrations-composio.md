---
title: Integrate Composio with Langflow
slug: /integrations-composio
---

Langflow integrates with [Composio](https://docs.composio.dev/introduction/intro/overview) as a toolset for your **Agent** component.

Instead of juggling multiple integrations and components in your flow, connect the Composio component to an **Agent** component to use all of Composio's supported APIs and actions as **Tools** for your agent.

## Prerequisites

- [A Composio API key](https://app.composio.dev/)
- [An OpenAI API key](https://platform.openai.com/)
- [A Gmail account](https://mail.google.com)

## Connect Langflow to a Composio tool

1. In the Langflow **Workspace**, add an **Agent** component.
2. In the **Workspace**, add the **Composio Tools** component.
3. Connect the **Agent** component's **Tools** port to the **Composio Tools** component's **Tools** port.
4. In the **Composio API Key** field, paste your Composio API key.
Alternatively, add the key as a [global variable](/configuration-global-variables).
5. In the **App Name** field, select the tool you want your agent to have access to.
For this example, select the **GMAIL** tool, which allows your agent to control an email account with the Composio tool.
6. Click **Refresh**.
The component's fields change based on the tool you selected.
The **Gmail** tool requires authentication with Google, so it presents an **Authentication Link** button.
7. Click the link to authenticate.
8. In the Google authentication dialog, enter the credentials for the Gmail account you want to control with Composio, and then click **Authenticate**.
9. Return to Langflow.
10. To update the Composio component, click **Refresh**.
The **Auth Status** field changes to a ✅, which indicates the Langflow component is connected to your Composio account.
11. In the **Actions to use** field, select the action you want the **Agent** to take with the **Gmail** tool.
The **Gmail** tool supports multiple actions, and also supports multiple actions within the same tool.
The default value of **GMAIL_CREATE_EMAIL_DRAFT** is OK for this example.
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

1. **GMAIL_CREATE_EMAIL_DRAFT**: This tool allows me to create a draft email using Gmail's API. I can specify the recipient's email address, subject, body content, and whether the body content is HTML.

2. **CurrentDate-get_current_date**: This tool retrieves the current date and time in a specified timezone.
```

This confirms your **Agent** and **Composio** are communicating.

6. Tell your AI to write a draft email.

```plain
Create a draft email with the subject line "Greetings from Composio"
recipient: "your.email@address.com"
Body content: "Hello from composio!"
```

Inspect the response to see how the agent used the attached tool to write an email.
This example response is abbreviated.

```plain
The draft email has been successfully created with the following details:
Recipient: your.email@address.com
Subject: Greetings from Composio
Body: Hello from composio!
```

```json
{
  "recipient_email": "your.email@address.com",
  "subject": "Greetings from Composio",
  "body": "Hello from composio!",
  "is_html": false
}

{
  "successfull": true,
  "data": {
    "response_data": {
      "id": "r-7515791375860110875",
      "message": {
        "id": "1939d1830046d2cb",
        "threadId": "1939d1830046d2cb",
        "labelIds": [
          "DRAFT"
        ]
      }
    }
  },
  "error": null
}
```

7. To confirm further, navigate to the Gmail account you authenticated with Composio.
Your email is visible in **Drafts**.

You have successfully integrated your Langflow component with Composio.
To add more tools, add another Composio component.