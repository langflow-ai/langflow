---
title: Security best practices
sidebar_position: 1
slug: /configuration-security-best-practices
---

This guide outlines security best practices for deploying and managing Langflow.

## Secret Key Protection

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

## API Keys and Credentials

1. Store API keys and credentials as encrypted global variables
2. Use the Credential type for sensitive information
3. Implement proper access controls for users who can view/edit credentials
4. Regularly audit and rotate API keys

## Database File Protection

1. Store the database in a secure location:

   ```bash
   LANGFLOW_SAVE_DB_IN_CONFIG_DIR=true
   LANGFLOW_CONFIG_DIR=/secure/path/to/config
   ```

2. Default database locations:
   - macOS/Linux: `PYTHON_LOCATION/site-packages/langflow/langflow.db`
   - Windows: `PYTHON_LOCATION\Lib\site-packages\langflow\langflow.db`

## Database Best Practices

1. Regular backups

   - Implement automated backup procedures
   - Store backups in secure, encrypted storage
   - Test backup restoration periodically

2. Access Control
   - Limit database access to necessary services/users
   - Use strong authentication for database access
   - Monitor and audit database access

## Deployment Security

1. Use HTTPS in production
2. Implement proper authentication
3. Regular security updates and patches
4. Monitor system logs
5. Use secure deployment practices:
   - Container security
   - Network security
   - Access control

## Audit and Compliance

1. Regular security audits
2. Compliance monitoring
3. Incident response planning
4. Security documentation

## Development Security

1. Secure coding practices
2. Code review procedures
3. Dependency management
4. Security testing

Remember to adapt these practices to your specific deployment requirements and compliance needs.
