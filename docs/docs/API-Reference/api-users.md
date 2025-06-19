---
title: Users endpoints
slug: /api-users
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

Use the `/users` endpoint to manage user accounts in Langflow.

The `user_id` value is specifically for Langflow's user system, which is stored in the Langflow database and managed at the `/users` API endpoint.
The `user_id` primary key in the Langflow database is mapped to the `id` value in the API.

## Add user

Create a new user account with a username and password.

This creates a new UUID for the user's `id`, which is mapped to `user_id` in the Langflow database.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X POST \
  "$LANGFLOW_URL/api/v1/users/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser2",
    "password": "securepassword123"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "id": "10c1c6a2-ab8a-4748-8700-0e4832fd5ce8",
  "username": "newuser2",
  "profile_image": null,
  "store_api_key": null,
  "is_active": false,
  "is_superuser": false,
  "create_at": "2025-05-29T16:02:20.132436",
  "updated_at": "2025-05-29T16:02:20.132442",
  "last_login_at": null,
  "optins": {
    "github_starred": false,
    "dialog_dismissed": false,
    "discord_clicked": false
  }
}
```

  </TabItem>
</Tabs>

## Get current user

Retrieve information about the currently authenticated user.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/users/whoami" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

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

  </TabItem>
</Tabs>

## List all users

Get a paginated list of all users in the system.
Only superusers can use this endpoint (`is_superuser: true`).

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X GET \
  "$LANGFLOW_URL/api/v1/users/?skip=0&limit=10" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "total_count": 3,
  "users": [
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
      "optins": {
        "github_starred": false,
        "dialog_dismissed": true,
        "discord_clicked": false,
        "mcp_dialog_dismissed": true
      }
    },
    {
      "id": "c48a1f68-cc7e-491a-a507-a1a627708470",
      "username": "newuser",
      "profile_image": null,
      "store_api_key": null,
      "is_active": false,
      "is_superuser": false,
      "create_at": "2025-05-29T16:00:33.483386",
      "updated_at": "2025-05-29T16:00:33.483392",
      "last_login_at": null,
      "optins": {
        "github_starred": false,
        "dialog_dismissed": false,
        "discord_clicked": false
      }
    },
    {
      "id": "10c1c6a2-ab8a-4748-8700-0e4832fd5ce8",
      "username": "newuser2",
      "profile_image": null,
      "store_api_key": null,
      "is_active": false,
      "is_superuser": false,
      "create_at": "2025-05-29T16:02:20.132436",
      "updated_at": "2025-05-29T16:02:20.132442",
      "last_login_at": null,
      "optins": {
        "github_starred": false,
        "dialog_dismissed": false,
        "discord_clicked": false
      }
    }
  ]
}
```

  </TabItem>
</Tabs>

## Update user

Modify an existing user's information with a PATCH request.

This example makes the user `10c1c6a2-ab8a-4748-8700-0e4832fd5ce8` an active superuser.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/users/10c1c6a2-ab8a-4748-8700-0e4832fd5ce8" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "is_active": true,
    "is_superuser": true
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "id": "10c1c6a2-ab8a-4748-8700-0e4832fd5ce8",
  "username": "newuser2",
  "profile_image": null,
  "store_api_key": null,
  "is_active": true,
  "is_superuser": true,
  "create_at": "2025-05-29T16:02:20.132436",
  "updated_at": "2025-05-29T16:19:03.514527Z",
  "last_login_at": null,
  "optins": {
    "github_starred": false,
    "dialog_dismissed": false,
    "discord_clicked": false
  }
}
```

  </TabItem>
</Tabs>

## Reset password

Change a user's password to a new secure value.

You can't change another user's password.

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X PATCH \
  "$LANGFLOW_URL/api/v1/users/10c1c6a2-ab8a-4748-8700-0e4832fd5ce8/reset-password" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY" \
  -d '{
    "password": "newsecurepassword123"
  }'
```

  </TabItem>
  <TabItem value="result" label="Result">

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
  "optins": {
    "github_starred": false,
    "dialog_dismissed": true,
    "discord_clicked": false
  }
}
```

  </TabItem>
</Tabs>

## Delete user

Remove a user account from the system.

Only superusers can use this endpoint (`is_superuser: true`).

<Tabs>
  <TabItem value="curl" label="curl" default>

```bash
curl -X DELETE \
  "$LANGFLOW_URL/api/v1/users/10c1c6a2-ab8a-4748-8700-0e4832fd5ce8" \
  -H "accept: application/json" \
  -H "x-api-key: $LANGFLOW_API_KEY"
```

  </TabItem>
  <TabItem value="result" label="Result">

```json
{
  "detail": "User deleted"
}
```

  </TabItem>
</Tabs>