---
title: Authentication
slug: /configuration-authentication
---

The login functionality in Langflow serves to authenticate users and protect sensitive routes in the application.

Starting from version 0.5, Langflow introduces an enhanced login mechanism that is governed by a few environment variables. This allows new secure features.

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

This environment variable holds a secret key used for encrypting the superuser's password. Make sure to set this to a secure, randomly generated string.

```bash
LANGFLOW_SECRET_KEY=randomly_generated_secure_key
```

### LANGFLOW_NEW_USER_IS_ACTIVE

By default, this variable is set to `False`. When enabled, new users are automatically activated and can log in without requiring explicit activation by the superuser.

```bash
LANGFLOW_NEW_USER_IS_ACTIVE=False
```