# IBM Db2 Components - Global Variable Usage Guide

## Overview

This guide explains how to properly use Langflow global variables with IBM Db2 components (DB2 Vector Store and DB2 SQL). Understanding the difference between variable types is crucial for security and proper functionality.

## Variable Types in Langflow

Langflow provides two types of global variables:

### 1. **Generic Variables** (Type: Generic)
- Used for **non-sensitive** configuration data
- Values are stored as plain text
- Can be used in any input field
- **Examples:** database names, hostnames, usernames, port numbers, table names

### 2. **Credential Variables** (Type: Credential)
- Used for **sensitive** security credentials
- Values are encrypted and masked in the UI
- Can **only** be used in password/secret fields
- **Examples:** passwords, API keys, tokens, certificates

## Security Design

The validation error you may encounter when trying to use a Credential-typed variable in a non-password field is **intentional and correct behavior**. This is a security feature that prevents:

1. **Accidental exposure** of credentials in logs or error messages
2. **Misuse** of sensitive data in non-secure contexts
3. **Security vulnerabilities** from treating non-sensitive data as sensitive

## Correct Usage for DB2 Components

### Connection Parameters

| Parameter | Variable Type | Reasoning |
|-----------|--------------|-----------|
| **Database Name** | Generic | Database names are not sensitive; they're configuration data |
| **Hostname** | Generic | Hostnames/IPs are network configuration, not secrets |
| **Port** | Generic (or direct input) | Port numbers are public configuration |
| **Username** | Generic | Usernames are identifiers, not secrets (though they should be protected) |
| **Password** | **Credential** | Passwords are sensitive and must be encrypted |

### Example Configuration

#### ✅ Correct: Using Generic Variables

1. **Create Generic Variables** (in Langflow Settings → Global Variables):
   ```
   Name: db2_database
   Type: Generic
   Value: MYDB

   Name: db2_hostname
   Type: Generic
   Value: db2.example.com

   Name: db2_username
   Type: Generic
   Value: db2user
   ```

2. **Create Credential Variable** for password:
   ```
   Name: db2_password
   Type: Credential
   Value: your_secure_password
   ```

3. **Use in Component**:
   - Database Name: `{db2_database}`
   - Hostname: `{db2_hostname}`
   - Username: `{db2_username}`
   - Password: `{db2_password}`

#### ❌ Incorrect: Using Credential Variables for Non-Passwords

```
# This will cause a validation error:
Database Name: {my_credential_variable}  # ERROR: Credential variables not allowed here

# Error message:
"Credential-typed variables cannot be used in non-password fields.
Please use a Generic-typed variable instead."
```

## Why This Matters

### Security Benefits

1. **Proper Encryption**: Only truly sensitive data (passwords) is encrypted
2. **Clear Intent**: Variable types document what is sensitive vs. configuration
3. **Audit Trail**: Security teams can easily identify credential usage
4. **Compliance**: Meets security standards for credential management

### Operational Benefits

1. **Debugging**: Non-sensitive data can be logged for troubleshooting
2. **Flexibility**: Configuration data can be easily changed without security concerns
3. **Performance**: Only necessary data is encrypted/decrypted

## Common Scenarios

### Scenario 1: Multiple Environments

```
# Development
db2_database_dev (Generic) = DEVDB
db2_hostname_dev (Generic) = dev-db2.internal
db2_password_dev (Credential) = dev_password

# Production
db2_database_prod (Generic) = PRODDB
db2_hostname_prod (Generic) = prod-db2.internal
db2_password_prod (Credential) = prod_password
```

### Scenario 2: Shared Configuration

```
# Multiple flows can share the same Generic variables
db2_hostname (Generic) = shared-db2.company.com
db2_port (Generic) = 50000

# But each flow might have different credentials
flow1_db2_password (Credential) = flow1_password
flow2_db2_password (Credential) = flow2_password
```

### Scenario 3: Dynamic Database Selection

```
# Use Generic variables for dynamic database selection
db2_database (Generic) = {selected_database}  # Can be changed at runtime
db2_password (Credential) = {fixed_password}  # Remains secure
```

## Troubleshooting

### Error: "Credential-typed variables cannot be used in non-password fields"

**Solution**: Change the variable type from Credential to Generic

1. Go to Langflow Settings → Global Variables
2. Find the variable (e.g., `db2_database`)
3. Change Type from "Credential" to "Generic"
4. Save changes
5. Refresh your flow

### Error: "Variable not found"

**Solution**: Ensure the variable exists and is spelled correctly

1. Check variable name matches exactly (case-sensitive)
2. Verify variable is created in Global Variables
3. Use correct syntax: `{variable_name}`

### Best Practice: Variable Naming

Use clear, descriptive names that indicate purpose:

```
✅ Good:
- db2_prod_database
- db2_dev_hostname
- db2_app_username
- db2_app_password

❌ Avoid:
- var1
- temp
- test
- password (too generic)
```

## Security Recommendations

1. **Never hardcode passwords** in flows - always use Credential variables
2. **Use Generic variables** for all non-sensitive configuration
3. **Rotate credentials regularly** by updating Credential variables
4. **Limit access** to Global Variables to authorized users only
5. **Audit variable usage** periodically to ensure proper classification
6. **Document your variables** with clear descriptions in Langflow

## Additional Resources

- [Langflow Documentation](https://docs.langflow.org/)
- [IBM Db2 Security Best Practices](https://www.ibm.com/docs/en/db2/11.5?topic=security)
- [Langflow Global Variables Guide](https://docs.langflow.org/configuration-global-variables)

## Support

If you encounter issues or have questions:

1. Check this guide first
2. Review the component's info text (hover over the ℹ️ icon)
3. Consult Langflow documentation
4. Contact your system administrator for credential-related issues

---

**Remember**: The validation error is protecting you from a security misconfiguration. Use Generic variables for configuration data and Credential variables only for passwords and secrets.