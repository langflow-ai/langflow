# Keycloak/SSO Integration for Langflow

This document details the Keycloak/SSO integration added to Langflow, providing a guide for administrators looking to set up and configure Single Sign-On authentication with Keycloak or other OpenID Connect providers.

## Table of Contents

- [Keycloak/SSO Integration for Langflow](#keycloaksso-integration-for-langflow)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Features](#features)
  - [Architecture](#architecture)
  - [Configuration](#configuration)
    - [Keycloak Setup Requirements](#keycloak-setup-requirements)
  - [Database Changes](#database-changes)
  - [User Interface Changes](#user-interface-changes)
  - [Authentication Flow](#authentication-flow)
  - [Security Considerations](#security-considerations)
  - [Testing with Playwright](#testing-with-playwright)
    - [Environment Variables for SSO Testing](#environment-variables-for-sso-testing)
    - [Test Coverage](#test-coverage)
    - [Running SSO Tests](#running-sso-tests)
    - [Test Implementation Details](#test-implementation-details)
  - [Troubleshooting](#troubleshooting)

## Overview

Langflow now supports Single Sign-On (SSO) integration through Keycloak, an open-source Identity and Access Management solution. This integration allows organizations to:

- Use their existing identity management infrastructure with Langflow
- Enforce consistent security policies across applications
- Simplify user management with centralized user provisioning
- Provide a better login experience for users

## Features

The Keycloak integration includes the following features:

- **Sign-in with SSO**: Users can authenticate with Keycloak using the standard OpenID Connect flow
- **Dual Authentication Modes**: Support for both traditional username/password and SSO authentication
- **Force SSO Mode**: Option to disable username/password login, forcing all users to authenticate via SSO
- **Role Mapping**: Map Keycloak roles to Langflow permissions (including admin privileges)
- **Auto-provisioning**: Automatically create user accounts in Langflow when users authenticate through Keycloak
- **Seamless Redirection**: Smooth redirection flow between Langflow and the Keycloak server

## Architecture

The integration follows a standard OAuth 2.0 Authorization Code flow with OpenID Connect:

1. **Backend Components**:
   - `KeycloakService`: Core service for interacting with Keycloak
   - `API Endpoints`: REST endpoints for configuration and callback handling
   - Database models for storing Keycloak user information

2. **Frontend Components**:
   - `useKeycloakAuth` hook: React hook for managing Keycloak authentication
   - `KeycloakCallback` component: Handles OAuth callback after authentication
   - Login page enhancements to support SSO login

## Configuration

Keycloak integration is configured through environment variables:

```bash
# Enable/disable Keycloak integration
LANGFLOW_KEYCLOAK_ENABLED=true

# Keycloak server URL (e.g., https://keycloak.example.com/auth)
LANGFLOW_KEYCLOAK_SERVER_URL=https://keycloak.example.com/auth

# Keycloak realm name
LANGFLOW_KEYCLOAK_REALM=myrealm

# Client ID registered in Keycloak
LANGFLOW_KEYCLOAK_CLIENT_ID=langflow

# Client secret (only for confidential clients)
LANGFLOW_KEYCLOAK_CLIENT_SECRET=your-client-secret

# Redirect URI for the OAuth callback
LANGFLOW_KEYCLOAK_REDIRECT_URI=http://localhost:3000/keycloak/callback

# Role in Keycloak that grants admin privileges in Langflow
LANGFLOW_KEYCLOAK_ADMIN_ROLE=langflow-admin

# Forces SSO-only login (hides username/password form)
LANGFLOW_KEYCLOAK_FORCE_SSO=false
```

### Keycloak Setup Requirements

1. Create a new client in your Keycloak realm with the following settings:
   - Client ID: `langflow` (or your preferred name)
   - Client Protocol: `openid-connect`
   - Access Type: `confidential` (recommended for security)
   - Valid Redirect URIs: Add the Langflow callback URL (`http://your-langflow-url/keycloak/callback`)

2. Create roles in Keycloak that will map to Langflow permissions:
   - Create a role for admin users (e.g., `langflow-admin`)
   - Assign roles to users in Keycloak

3. Obtain the client secret from the Credentials tab in Keycloak (for confidential clients)

## Database Changes

The integration adds the following fields to the User model:

- `email`: User's email address obtained from Keycloak
- `is_keycloak_user`: Boolean flag indicating if the user authenticated through Keycloak
- `is_deleted`: Soft deletion flag for users
- `deleted_at`: Timestamp for when the user was soft-deleted

These changes are implemented in the `a87d3f2c6e2c_keycloak.py` migration file.

## User Interface Changes

The login page has been enhanced to support SSO authentication:

- When Keycloak is enabled but not forced, the login page shows both the traditional username/password form and an "Sign in with SSO" button
- When Keycloak is enabled and forced (Force SSO mode), only the "Sign in with SSO" button is displayed
- A dedicated callback page (`/keycloak/callback`) handles the OAuth response from Keycloak

## Authentication Flow

The authentication flow follows the standard OAuth 2.0 Authorization Code flow:

1. **Initiation**:
   - User clicks "Sign in with SSO" button
   - Frontend generates state and nonce parameters for CSRF protection
   - User is redirected to Keycloak login page

2. **Authentication at Keycloak**:
   - User authenticates with credentials at Keycloak
   - Keycloak redirects back to Langflow with an authorization code

3. **Token Exchange**:
   - Frontend receives the code and sends it to the backend
   - Backend exchanges the code for tokens with Keycloak
   - Backend extracts user information and roles from the tokens
   - Backend creates or updates the user in the database
   - Backend issues Langflow-specific tokens for the session

4. **Session Management**:
   - Frontend stores the tokens and uses them for API requests
   - Refresh tokens are used to maintain the session
   - Logout invalidates tokens in both Langflow and Keycloak

## Security Considerations

The implementation includes several security measures:

- **CSRF Protection**: Using state parameter in the OAuth flow
- **Secure Storage**: Client secrets are stored as SecretStr in Pydantic settings
- **Token Validation**: Proper validation of tokens from Keycloak
- **Role-Based Access**: Mapping of Keycloak roles to Langflow permissions

## Testing with Playwright

The Keycloak/SSO integration includes automated testing using Playwright. These tests validate that SSO authentication works correctly, including login and logout flows for both regular and admin users.

### Environment Variables for SSO Testing

To enable and configure SSO testing with Playwright, the following environment variables are required:

```bash
# Enable SSO testing (set to "true" to run SSO tests)
LANGFLOW_SSO_TEST_ENABLED=true

# Regular user credentials for testing
LANGFLOW_SSO_TEST_REGULAR_USER_USERNAME=regular_user
LANGFLOW_SSO_TEST_REGULAR_USER_PASSWORD=regular_password

# Admin user credentials for testing
LANGFLOW_SSO_TEST_ADMIN_USER_USERNAME=admin_user
LANGFLOW_SSO_TEST_ADMIN_USER_PASSWORD=admin_password
```

### Test Coverage

The SSO tests in `src/frontend/tests/core/features/sso-login.spec.ts` cover the following scenarios:

1. **Regular User Login**: Tests that a regular user can successfully log in via SSO
2. **Admin User Login**: Tests that an admin user can successfully log in via SSO
3. **Invalid User Login**: Tests that invalid credentials are correctly rejected
4. **Admin Role Validation**: Tests that admin users have the correct roles and permissions

### Running SSO Tests

To run the SSO tests:

1. Configure all required Keycloak environment variables as described in the [Configuration](#configuration) section
2. Configure the additional SSO testing environment variables listed above
3. Run the Playwright tests with the following command:

```bash
make tests_frontend
```

The SSO tests are skipped by default unless `LANGFLOW_SSO_TEST_ENABLED` is set to `true`.

### Test Implementation Details

- Tests use `page.getByTestId()` selectors to interact with both Langflow and Keycloak UI elements
- For failed tests, screenshots are automatically captured and saved
- The test validates that the admin user correctly receives admin privileges based on Keycloak roles
- The test confirms the correct flags are set in the user table (is_keycloak_user, is_superuser, etc.)

## Troubleshooting

Common issues and solutions:

1. **Configuration Issues**:
   - Check that all required environment variables are set correctly
   - Verify the Keycloak server URL is accessible from both frontend and backend

2. **Redirect Problems**:
   - Ensure the redirect URI is correctly registered in Keycloak
   - Check for any firewall or proxy issues affecting the callback URL

3. **Role Mapping**:
   - If admin privileges aren't working, verify that users have the specified admin role in Keycloak
   - Check the role is properly configured in the client's scope

4. **Authentication Failures**:
   - Check the Langflow logs for detailed error messages
   - Verify that the client secret is correct if using a confidential client

5. **Testing Failures**:
   - Check that all required test environment variables are set correctly
   - Verify that the test users exist in Keycloak with the correct roles
   - Review screenshot captures of failed tests for UI-related issues
