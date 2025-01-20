---
title: Authentication
slug: /configuration-authentication
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

The login functionality in Langflow serves to authenticate users and protect sensitive routes in the application.

## Create a superuser and new users in Langflow

Learn how to create a new superuser, log in to Langflow, and add new users.

1. Create a `.env` file and open it in your preferred editor.

2. Add the following environment variables to your file.

```bash
LANGFLOW_AUTO_LOGIN=False
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=securepassword
LANGFLOW_SECRET_KEY=randomly_generated_secure_key
LANGFLOW_NEW_USER_IS_ACTIVE=False
```

For more information, see [Authentication configuration values](#values).

:::tip
The Langflow project includes a [`.env.example`](https://github.com/langflow-ai/langflow/blob/main/.env.example) file to help you get started.
You can copy the contents of this file into your own `.env` file and replace the example values with your own preferred settings.
:::

3. Save your `.env` file.
4. Run Langflow with the configured environment variables.

```bash
python -m langflow run --env-file .env
```

5. Sign in with your username `admin` and password `securepassword`.
6. To open the **Admin Page**, click your user profile image, and then select **Admin Page**.
   You can also go to `http://127.0.0.1:7861/admin`.
7. To add a new user, click **New User**, and then add the **Username** and **Password**.
8. To activate the new user, select **Active**.
   The user can only sign in if you select them as **Active**.
9. To give the user `superuser` privileges, click **Superuser**.
10. Click **Save**.
11. To confirm your new user has been created, sign out of Langflow, and then sign back in using your new **Username** and **Password**.

## Manage Superuser with the Langflow CLI

Langflow provides a command-line utility for interactively creating superusers:

1. Enter the CLI command:

```bash
langflow superuser
```

2. Langflow prompts you for a **Username** and **Password**:

```
langflow superuser
Username: new_superuser_1
Password:
Default folder created successfully.
Superuser created successfully.
```

3. To confirm your new superuser was created successfully, go to the **Admin Page** at `http://127.0.0.1:7861/admin`.

## Authentication configuration values {#values}

The following table lists the available authentication configuration variables, their descriptions, and default values:

| Variable                      | Description                           | Default |
| ----------------------------- | ------------------------------------- | ------- |
| `LANGFLOW_AUTO_LOGIN`         | Enables automatic login               | `True`  |
| `LANGFLOW_SUPERUSER`          | Superuser username                    | -       |
| `LANGFLOW_SUPERUSER_PASSWORD` | Superuser password                    | -       |
| `LANGFLOW_SECRET_KEY`         | Key for encrypting superuser password | -       |
| `LANGFLOW_NEW_USER_IS_ACTIVE` | Automatically activates new users     | `False` |

### LANGFLOW_AUTO_LOGIN

By default, this variable is set to `True`. When enabled, Langflow operates as it did in versions prior to 0.5, including automatic login without requiring explicit user authentication.

To disable automatic login and enforce user authentication:

```shell
LANGFLOW_AUTO_LOGIN=False
```

### LANGFLOW_SUPERUSER and LANGFLOW_SUPERUSER_PASSWORD

These environment variables are only relevant when LANGFLOW_AUTO_LOGIN is set to False. They specify the username and password for the superuser, which is essential for administrative tasks.
To create a superuser manually:

```bash
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=securepassword
```

### LANGFLOW_SECRET_KEY

This environment variable holds a secret key used for encrypting sensitive data like API keys.

```bash
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fb
```

Langflow uses the [Fernet](https://pypi.org/project/cryptography/) library for secret key encryption.

### Create a LANGFLOW_SECRET_KEY

The `LANGFLOW_SECRET_KEY` is used for encrypting sensitive data. It must be:
- At least 32 bytes long
- URL-safe base64 encoded

1. To create a `LANGFLOW_SECRET_KEY`, run the following command:

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

The command generates a secure key like `dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fbg`.
Treat the generated secure key as you would an application access token. Do not commit the key to code and keep it in a safe place.

2. Create a `.env` file with the following configuration, and include your generated secret key value.
```bash
LANGFLOW_AUTO_LOGIN=False
LANGFLOW_SUPERUSER=admin
LANGFLOW_SUPERUSER_PASSWORD=securepassword
LANGFLOW_SECRET_KEY=dBuuuB_FHLvU8T9eUNlxQF9ppqRxwWpXXQ42kM2_fbg  # Your generated key
LANGFLOW_NEW_USER_IS_ACTIVE=False
```

3. Start Langflow with the values from your `.env` file.
```bash
uv run langflow run --env-file .env
```

The generated secret key value is now used to encrypt your global variables.

If no key is provided, Langflow will automatically generate a secure key. This is not recommended for production environments, because in a multi-instance deployment like Kubernetes, auto-generated keys won't be able to decrypt data encrypted by other instances. Instead, you should explicitly set the `LANGFLOW_SECRET_KEY` environment variable in the deployment configuration to be the same across all instances.

### LANGFLOW_NEW_USER_IS_ACTIVE

By default, this variable is set to `False`. When enabled, new users are automatically activated and can log in without requiring explicit activation by the superuser.

```bash
LANGFLOW_NEW_USER_IS_ACTIVE=False
```