---
title: Security best practices
slug: /configuration-security-best-practices
---

This guide outlines security best practices for deploying and managing Langflow.

## Secret key protection

The secret key is critical for encrypting sensitive data in Langflow. Follow these guidelines:

- Always use a custom secret key in production:

  ```bash
  LANGFLOW_SECRET_KEY=your-secure-secret-key
  ```

- Store the secret key securely:

  - Use environment variables or secure secret management systems.
  - Never commit the secret key to version control.
  - Regularly rotate the secret key.

- Use the default secret key locations:
  - macOS: `~/Library/Caches/langflow/secret_key`
  - Linux: `~/.cache/langflow/secret_key`
  - Windows: `%USERPROFILE%\AppData\Local\langflow\secret_key`

## API keys and credentials

- Store API keys and credentials as encrypted global variables.
- Use the Credential type for sensitive information.
- Implement proper access controls for users who can view/edit credentials.
- Regularly audit and rotate API keys.

## Database file protection

- Store the database in a secure location:

   ```bash
   LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true
   LANGFLOW_CONFIG_DIR=/secure/path/to/config
   ```

- Use the default database locations:
   - macOS/Linux: `PYTHON_LOCATION/site-packages/langflow/langflow.db`
   - Windows: `PYTHON_LOCATION\Lib\site-packages\langflow\langflow.db`
