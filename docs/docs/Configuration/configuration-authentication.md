---
title: Authentication
slug: /configuration-authentication
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

This guide covers Langflow's authentication system and API key management, including how to secure your deployment and manage access to flows and components.

:::warning
Never expose Langflow ports directly to the internet without proper security measures.

Disable `LANGFLOW_AUTO_LOGIN`, use a secure `LANGFLOW_SECRET_KEY`, and ensure your Langflow server is behind a reverse proxy with authentication enabled.
For more information, see [Start a secure Langflow server with authentication](#start-a-secure-langflow-server-with-authentication).
:::

## Authentication configuration values

The section describes the available authentication configuration variables.

You can use the [`.env.example`](https://github.com/langflow-ai/langflow/blob/main/.env.example) file in the Langflow repository as a template for your own `.env` file.

### LANGFLOW_AUTO_LOGIN

When `True`, Langflow automatically logs users in with username `langflow` and password `langflow` without requiring user authentication.
To disable automatic login and enforce user authentication, set this value to `False` in your `.env` file.
By default, this variable is set to `True`.

Langflow **does not** allow users to have simultaneous or shared access to flows.
If `AUTO_LOGIN` is enabled and user management is disabled (`LANGFLOW_NEW_USER_IS_ACTIVE=true`), users can access the same environment, but it is not password protected. If two users access the same flow, Langflow saves only the work of the last user to save.

```bash
LANGFLOW_AUTO_LOGIN=True
```

### LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD

These environment variables are only relevant when `LANGFLOW_AUTO_LOGIN` is set to `False`.
They specify the username and password for the superuser, which is essential for administrative tasks:

```text
LANGFLOW_SUPERUSER=administrator
LANGFLOW_SUPERUSER_PASSWORD=securepassword
```

### LANGFLOW_SECRET_KEY

This environment variable holds a secret key used for encrypting sensitive data like API keys.
Langflow uses the [Fernet](https://pypi.org/project/cryptography/) library for secret key encryption.

```text
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fb
```

:::warning
If no secret key is provided, Langflow automatically generates one. This is not recommended for production environments, especially in multi-instance deployments like Kubernetes, where auto-generated keys can't decrypt data encrypted by other instances.
:::

To generate a `LANGFLOW_SECRET_KEY`, follow these steps:

1. Run the command to generate and copy a secret to the clipboard.

<Tabs>
<TabItem value="unix" label="macOS/Linux">

```bash
# Copy to clipboard (macOS)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | pbcopy

# Copy to clipboard (Linux)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | xclip -selection clipboard

# Or just print
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```
</TabItem>

<TabItem value="windows" label="Windows">

```bash
# Copy to clipboard
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | clip

# Or just print
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```

</TabItem>
</Tabs>

2. Paste the value into your `.env` file:
```text
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fb
```

### LANGFLOW_NEW_USER_IS_ACTIVE

When this option is set to `True`, new users are automatically activated and can log in without requiring explicit activation by the superuser from the **Admin page**.
By default, this variable is set to `False`.

```text
LANGFLOW_NEW_USER_IS_ACTIVE=False
```

## Start a secure Langflow server with authentication

Start a secure Langflow server with authentication enabled and secret key encryption using the variables described in [Authentication configuration values](/configuration-authentication#authentication-configuration-values).

Once you are logged in as a superuser, create a new user on your server.

### Start the Langflow server

1. Create a `.env` file and populate it with values for a secure server.
This server creates a superuser account, requires users to log in before using Langflow, and encrypts secrets with `LANGFLOW_SECRET_KEY`, which is added in the next step.
Create a `.env` file with the following configuration:

```text
LANGFLOW_AUTO_LOGIN=False
LANGFLOW_SUPERUSER=administrator
LANGFLOW_SUPERUSER_PASSWORD=securepassword
LANGFLOW_SECRET_KEY=your_generated_key
LANGFLOW_NEW_USER_IS_ACTIVE=False
```

2. Generate a secret key for encrypting sensitive data.

Generate your secret key using one of the following commands:

<Tabs>
<TabItem value="unix" label="macOS/Linux">

```bash
# Copy to clipboard (macOS)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | pbcopy

# Copy to clipboard (Linux)
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | xclip -selection clipboard

# Or just print
python3 -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```
</TabItem>

<TabItem value="windows" label="Windows">

```bash
# Copy to clipboard
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')" | clip

# Or just print
python -c "from secrets import token_urlsafe; print(f'LANGFLOW_SECRET_KEY={token_urlsafe(32)}')"
```

</TabItem>
</Tabs>

3. Paste your `LANGFLOW_SECRET_KEY` into the `.env` file.

4. Start Langflow with the configuration from your `.env` file.

```text
uv run langflow run --env-file .env
```

5. Verify the server is running. The default location is `http://localhost:7860`.

### Manage users as an administrator

1. To complete your first-time login as a superuser, go to `http://localhost:7860/login`.
2. Log in with your superuser credentials:
* Username: Value of `LANGFLOW_SUPERUSER` (for example, `administrator`)
* Password: Value of `LANGFLOW_SUPERUSER_PASSWORD` (for example, `securepassword`)

:::info
The default values are `langflow` and `langflow`.
:::

3. To manage users on your server, navigate to the `/admin` page at `http://localhost:7860/admin`.
Click your user profile image, and then click **Admin Page**.

As a superuser, you can create users, set permissions, reset passwords, and delete accounts.

4. To create a user, in the Langflow UI, click **New User**, and then complete the following fields:
* **Username**
* **Password** and **Confirm Password**
* Select **Active** and deselect **Superuser** for the new user.
**Active** users can log into the system and access their flows. **Inactive** users cannot log in or see their flows.
A **Superuser** has full administrative privileges.

5. To complete user creation, click **Save**.
Your new user appears in the **Admin Page**.
6. To confirm your new user's functionality, log out of Langflow, and log back in with your new user's credentials.
Attempt to access the `/admin` page. You should be redirected to the `/flows` page, because the new user is not a superuser.

You have started a secure Langflow server with authentication enabled and secret key encryption.