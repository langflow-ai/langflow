---
title: Security best practices
sidebar_position: 1
slug: /configuration-security-best-practices
---

This guide outlines security best practices for deploying and managing Langflow.

## Secret key protection

The secret key is critical for encrypting sensitive data in Langflow. Follow these guidelines:

1. Always use a custom secret key in production:

   ```bash
   LANGFLOW_SECRET_KEY=your-secure-secret-key
   ```

2. Store the secret key securely:

   - Use environment variables or secure secret management systems
   - Never commit the secret key to version control
   - Regularly rotate the secret key

3. Default secret key locations:
   - macOS: `~/Library/Caches/langflow/secret_key`
   - Linux: `~/.cache/langflow/secret_key`
   - Windows: `%USERPROFILE%\AppData\Local\langflow\secret_key`

## API keys and credentials

1. Store API keys and credentials as encrypted global variables
2. Use the Credential type for sensitive information
3. Implement proper access controls for users who can view/edit credentials
4. Regularly audit and rotate API keys

## Database file protection

1. Store the database in a secure location:

   ```bash
   LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true
   LANGFLOW_CONFIG_DIR=/secure/path/to/config
   ```

2. Default database locations:
   - macOS/Linux: `PYTHON_LOCATION/site-packages/langflow/langflow.db`
   - Windows: `PYTHON_LOCATION\Lib\site-packages\langflow\langflow.db`
