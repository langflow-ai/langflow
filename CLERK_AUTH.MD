# 🔐 Authentication Flow in Langflow

This document outlines the supported authentication methods in Langflow, their flow, and the fallback logic.

---

## 🚦 Auth Precedence (in `get_current_user`)

Langflow supports 3 authentication paths, checked in order:

1. **Clerk JWT Authentication** (if enabled)
2. **Legacy Auth via OAuth2 Password (username/password)**
3. **API Key Authentication** (via query/header)
4. **AUTO_LOGIN** mode (fallback, dev mode)

---

## ✅ 1. Clerk Authentication Flow (if `CLERK_AUTH_ENABLED=true`)

- Frontend sends the JWT token in the `Authorization: Bearer <token>` header or via `access_token_lf` cookie.
- Backend performs:
  1. Parse JWT header → extract `kid`
  2. Fetch Clerk JWKs (or cached)
  3. Validate JWT signature (RS256) using public key
  4. Extract claims (`sub`, `email`, `username`)
  5. Look up user in DB via `sub` (or fallback to `email`)
  6. If not found or inactive → 401 Unauthorized

> **Note:** Clerk `sub` maps to your `username` in DB (or you can extend to auto-create).

---

## 🧩 2. Legacy Login Flow (when user logs in via `/api/v1/login`)

- Backend expects:
  - JSON body: `{ "username": "admin", "password": "pass" }`
- It verifies:
  - `username` exists in DB
  - password matches (via `pwd_context.verify`)
  - user is active
- If valid:
  - Generates JWT access/refresh tokens
  - Returns them to frontend

This is the default path **if Clerk is not enabled**.

---

## 🔑 3. API Key Authentication (x-api-key header/query)

Used for scripts or service-to-service access:

- API key is sent via:
  - Header: `x-api-key`
  - OR Query: `?x-api-key=...`
- Backend checks:
  - Validity of key in `api_keys` table
  - Corresponding user is active
- On success: Returns `UserRead` model

---

## ⚙️ 4. AUTO_LOGIN Mode (`AUTO_LOGIN=true` in `.env`)

Mainly for **local/dev environments**.

- Skips auth if:
  - No token or API key is provided
- Automatically logs in the first superuser defined in `SUPERUSER` setting

> ⚠️ **Deprecated in production** – emits warnings in >= v1.5.

---

## 🧠 Summary Table

| Mode          | Token Input       | Validated Against | Requires DB User | Notes |
|---------------|-------------------|-------------------|------------------|-------|
| Clerk         | Bearer JWT        | Clerk JWKs        | ✅ yes           | Most secure, external |
| Legacy        | username/password | Internal DB       | ✅ yes           | Fallback or standalone |
| API Key       | Header/Query      | DB API key        | ✅ yes           | Good for programmatic use |
| AUTO_LOGIN    | None              | Configured user   | ✅ yes           | For dev/test only |

---

## 🔐 Configuration Overview

`.env` variables that affect auth:

```env
CLERK_AUTH_ENABLED=true
CLERK_SECRET_KEY=...
AUTO_LOGIN=false
SUPERUSER=admin
