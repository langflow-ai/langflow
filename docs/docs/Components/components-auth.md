---
title: Access Control
slug: /components-auth
---

# Authentication and Authorization in Langflow

The authentication and authorization components in Langflow are designed to secure your workflows by validating user credentials, checking permissions, and controlling access to resources. These components ensure that only authorized users can perform specific actions on designated resources.

They handle critical security tasks like verifying tokens, confirming permissions, and managing access control, ensuring smooth and secure operations within your workflows.

## **JWT Validator**

This component verifies JSON Web Tokens (JWT) using JSON Web Key Sets (JWKs) and extracts the user's identifier. It performs a thorough validation process, including signature checks, expiration date verification, and key validation via the specified JWKs endpoint.

To optimize performance, the component automatically fetches and caches the JWKs from the provided URL, handling key rotations efficiently and reducing unnecessary HTTP requests. It supports the RS256 algorithm and retrieves the subject claim (`sub`) as the user identifier.

### **Inputs**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| jwt_token  | JWT Token    | The JWT token to validate. Must follow RFC 7519 standards.                  |

### **Configuration**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| jwks_url   | JWKs URL     | The URL of the JWKs endpoint (e.g., `https://your-domain/.well-known/jwks.json`). |

### **Outputs**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| user_id    | User ID      | The extracted user ID from the validated token (`sub` claim).               |

## **Permissions Check**

This component evaluates whether a user has permission to perform a specific action on a resource. It integrates with Permit.io's Policy Decision Point (PDP) to enforce fine-grained access control based on your defined policies.

It supports context-aware authorization by optionally including tenant information, enabling real-time policy evaluations for multi-tenant environments.

### **Inputs**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| user       | User         | The user identifier to check permissions for.                              |
| action     | Action       | The action being performed (e.g., `read`, `write`, `delete`, `create`).     |
| resource   | Resource     | The resource identifier being acted upon.                                  |
| tenant     | Tenant       | Optional tenant identifier for multi-tenant scenarios.                     |

### **Configuration**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| pdp_url    | PDP URL      | The URL of the Policy Decision Point (found in your Permit.io dashboard).   |
| api_key    | API Key      | Your Permit.io API key for authentication.                                  |

### **Outputs**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| allowed    | Allowed      | A boolean value indicating whether the action is permitted (`true` or `false`). |

## **Data Protection**

This component retrieves and filters the list of resources a user is allowed to access. It can either fetch all permissions for a given resource type or filter a specific set of resource IDs based on the user's permissions.

The component supports bulk permission checks and uses caching to enhance performance when evaluating multiple resources.

### **Inputs**
| Name          | Display Name | Description                                                                 |
|---------------|--------------|-----------------------------------------------------------------------------|
| user_id       | User ID      | The user identifier to retrieve permissions for.                           |
| action        | Action       | The action to filter permissions by (e.g., `read`, `write`).                |
| resource_type | Resource Type| The type of resource to check permissions for (e.g., `document`, `project`).|
| filter_ids    | Filter IDs   | Optional list of specific resource IDs to check permissions for.            |

### **Configuration**
| Name       | Display Name | Description                                                                 |
|------------|--------------|-----------------------------------------------------------------------------|
| pdp_url    | PDP URL      | The URL of the Policy Decision Point.                                       |
| api_key    | API Key      | Your Permit.io API key for authentication.                                  |

### **Outputs**
| Name          | Display Name | Description                                                                 |
|---------------|--------------|-----------------------------------------------------------------------------|
| allowed_ids   | Allowed IDs  | A list of resource IDs that the user is authorized to access for the specified action. |

## How These Components Work Together

These components implement the four security perimeters for LLM applications:

1. **Prompt Filtering**: Use JWT Validator to authenticate users and filter inputs
2. **RAG Data Protection**: Use Data Protection to control access to RAG data
3. **Secure External Access**: Use Permissions Check for API and external service access
4. **Response Enforcement**: Use Data Protection to filter sensitive information from responses

Each component can be used individually or combined to create comprehensive security flows.

When setting up these components, ensure your Permit.io policies are properly configured, and your JWKs endpoint is accessible. The components are designed to handle errors gracefully, providing clear messages for issues such as invalid tokens, network problems, or denied permissions.