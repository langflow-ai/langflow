---
title: API keys
slug: /configuration-api-keys
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';
import Icon from "@site/src/components/icon";

You can use Langflow API keys to interact with Langflow programmatically.

The API key has the same permissions and access as you do when you launch Langflow. This means your API key can only access your own flows, components, and data. You cannot access other users' resources with your own Langflow API keys.
An API key represents the user who created it. If you create a key as a superuser, then that key will have superuser privileges.
Anyone who has that key can authorize superuser actions through the Langflow API, including user management and flow management.

In Langflow versions 1.5 and later, most API requests require a Langflow API key, even when `AUTO_LOGIN=true`.

The only exceptions are the MCP endpoints: `/v1/mcp`, `/v1/mcp-projects`, and `/v2/mcp`.
These endpoints don't require authentication, regardless of the `AUTO_LOGIN` setting.

<details>
<summary>Auto-login and API key authentication in earlier Langflow versions</summary>

If you are running a Langflow version earlier than 1.5, if `AUTO_LOGIN=true`, Langflow automatically logs users in as a superuser without requiring authentication, and API requests can be made without a Langflow API key.

If you set `SKIP_AUTH_AUTO_LOGIN=true`, authentication will be skipped entirely, and API requests will not require a Langflow API key, regardless of the `AUTO_LOGIN` setting.

</details>

## Generate a Langflow API key

You can generate a Langflow API key with the UI or the CLI.

The UI-generated key is appropriate for most cases. The CLI-generated key is needed when your Langflow server is running in `--backend-only` mode.

<Tabs>
  <TabItem value="Langflow UI" label="Langflow UI" default>

1. Click your user icon, and then select **Settings**.
2. Click **Langflow API Keys**, and then click **Add New**.
3. Name your key, and then click **Create API Key**.
4. Copy the API key and store it in a secure location.

  </TabItem>

  <TabItem value="Langflow CLI" label="Langflow CLI">

If you're serving your flow with `--backend-only=true`, you can't create API keys in the UI, because the frontend is not running.

Depending on your authentication settings, note the following requirements for creating API keys with the Langflow CLI:

* If `AUTO_LOGIN` is `FALSE`, you must be logged in as a superuser.
* If `AUTO LOGIN` is `TRUE`, you're already logged in as superuser.

To create an API key for a user from the CLI, do the following:

1. In your `.env` file, set `AUTO_LOGIN=FALSE`, and set superuser credentials for your server.

    ```text
    LANGFLOW_AUTO_LOGIN=False
    LANGFLOW_SUPERUSER=administrator
    LANGFLOW_SUPERUSER_PASSWORD=securepassword
    ```

2. To confirm your superuser status, call [`GET /users/whoami`](/api-users#get-current-user), and then check that the response contains `"is_superuser": true`:

    ```bash
    curl -X GET \
      "$LANGFLOW_URL/api/v1/users/whoami" \
      -H "accept: application/json" \
      -H "x-api-key: $LANGFLOW_API_KEY"
    ```

    <details closed>
    <summary>Result</summary>

    ```json
    {
      "id": "07e5b864-e367-4f52-b647-a48035ae7e5e",
      "username": "langflow",
      "profile_image": null,
      "store_api_key": null,
      "is_active": true,
      "is_superuser": true,
      "create_at": "2025-05-08T17:59:07.855965",
      "updated_at": "2025-05-29T15:06:56.157860",
      "last_login_at": "2025-05-29T15:06:56.157016",
    }
    ```

    </details>

2. Create an API key:

    ```shell
    uv run langflow api-key
    ```
  </TabItem>
</Tabs>

## Authenticate requests with the Langflow API key

Include your API key in API requests to authenticate requests to Langflow.

API keys allow access only to the flows and components of the specific user to whom the key was issued.

<Tabs>
  <TabItem value="HTTP header" label="HTTP header" default>

To use the API key when making API requests, include the API key in the HTTP header:

```shell
curl -X POST \
  "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID?stream=false" \
  -H 'Content-Type: application/json' \
  -H 'x-api-key: LANGFLOW_API_KEY' \
  -d '{"inputs": {"text":""}, "tweaks": {}}'
```

  </TabItem>
  <TabItem value="Query parameter" label="Query parameter">

To pass the API key as a query parameter:

```shell
curl -X POST \
  "http://LANGFLOW_SERVER_ADDRESS/api/v1/run/FLOW_ID?x-api-key=LANGFLOW_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"inputs": {"text":""}, "tweaks": {}}'
```
  </TabItem>
</Tabs>

## Generate a Langflow secret key

Langflow uses the [Fernet](https://pypi.org/project/cryptography/) library for encrypting sensitive data.

If no `LANGFLOW_SECRET_KEY` is provided, Langflow automatically generates one.

For more information, see [Authentication](/configuration-authentication#langflow_secret_key).

## Revoke an API key

To revoke an API key, delete it from the list of keys in the **Settings** menu.

1. Click your user icon, and then select **Settings**.
2. Click **Langflow API**.
3. Select the keys you want to delete, and then click <Icon name="Trash2" aria-hidden="true"/> **Delete**.

This action immediately invalidates the key and prevents it from being used again.

## Add component API keys to Langflow

These are credentials for external services like OpenAI. They can be added to Langflow with the `.env` file or in the Langflow UI.

Component API keys that are set in the UI override those that are set in the environment variables.

### Add component API keys with the .env file

To add component API keys to your `.env` file:

```text
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GOOGLE_API_KEY=...
```

### Add component API keys with the Langflow UI

To add component API keys as **Global variables** with the Langflow UI:

1. Click your user icon, and then select **Settings**.
2. Click **Langflow API**.
3. Add new API keys as **Credential** type variables.
4. Apply them to specific component fields.

Component values set directly in a flow override values set in the UI **and** environment variables.

For more information, see [Global variables](/configuration-global-variables).