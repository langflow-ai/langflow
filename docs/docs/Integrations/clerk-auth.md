---
title: Clerk Authentication
slug: /clerk-auth
---


This page summarizes how Langflow handles access token refreshes in different authentication modes and what state changes occur when using Clerk.

## Refresh scenarios when Clerk authentication is disabled

When `CLERK_AUTH_ENABLED` is `false`, Langflow relies on its internal authentication. Tokens are refreshed in these situations:

1. **Protected routes** – the `ProtectedRoute` component periodically calls the `/refresh` endpoint using the `useRefreshAccessToken` hook.
2. **API requests** – the API interceptor automatically triggers the same hook when a request fails with a `401` or `403` error.

Both cases invoke the `useRefreshAccessToken` hook which posts to `/refresh` and updates the refresh token cookie.
The default interval used by `ProtectedRoute` is defined by `LANGFLOW_ACCESS_TOKEN_EXPIRE_SECONDS` (54&nbsp;minutes by default) or the value of the `ACCESS_TOKEN_EXPIRE_SECONDS` environment variable.

## State updates when using Clerk

When `CLERK_AUTH_ENABLED` is `true`, token refresh from the frontend is skipped. After signing in with Clerk, `ClerkAuthAdapter` logs the user in to the backend and calls `login()` from the authentication context, which updates several states:

| State location | Value after Clerk token update |
|----------------|--------------------------------|
| `access_token_lf` cookie | Clerk session token |
| `refresh_token_lf` cookie | Backend refresh token |
| `auto_login_lf` cookie | `"login"` |
| Local storage `access_token_lf` | Clerk session token |
| `authStore.accessToken` | Clerk session token |
| `authStore.isAuthenticated` | `true` |
| `authContext.userData` | populated from `/users/whoami` |

With Clerk enabled the periodic refresh is disabled and all further state changes rely on Clerk sessions.
