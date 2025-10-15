# AI Studio Frontend Authentication Testing

This directory contains Docker-based testing setup for the AI Studio frontend authentication fixes, specifically for Keycloak integration issues.

## Quick Start

### 1. Run Complete Test Suite
```bash
./test-authentication.sh
```

### 2. Start Test Environment Only
```bash
./test-authentication.sh start
```

### 3. Stop Test Environment
```bash
./test-authentication.sh stop
```

### 4. View Container Logs
```bash
./test-authentication.sh logs
```

## Test Environment

The test setup creates three containers:

### 1. Keycloak-Enabled Frontend (Port 3001)
- **URL**: http://localhost:3001
- **Authentication**: Keycloak enabled
- **Purpose**: Test the fixed Keycloak authentication flow

**Environment Variables:**
- `VITE_KEYCLOAK_ENABLED=true`
- `VITE_KEYCLOAK_URL=https://genesis.dev-v2.platform.autonomize.dev/genesis-platform/auth/`
- `VITE_KEYCLOAK_REALM=autonomize`
- `VITE_KEYCLOAK_CLIENT_ID=ai-studio-frontend`

### 2. Traditional Auth Frontend (Port 3002)
- **URL**: http://localhost:3002
- **Authentication**: Traditional autologin
- **Purpose**: Test traditional authentication still works

**Environment Variables:**
- `VITE_KEYCLOAK_ENABLED=false`

### 3. Mock Backend (Port 7860)
- **URL**: http://localhost:7860
- **Purpose**: Simulate AI Studio backend API responses
- **Endpoints**: Auto login, user data, version, config, etc.

## Authentication Fixes Tested

### ✅ Autologin Prevention
- **Issue**: Autologin runs even when Keycloak is enabled
- **Fix**: Conditional logic in `AppInitPage/index.tsx`
- **Test**: Verify no autologin calls in Keycloak frontend

### ✅ Centralized Token Access
- **Issue**: Inconsistent token retrieval between Keycloak and traditional auth
- **Fix**: `utils/authHelper.ts` with unified token management
- **Test**: Verify Bearer tokens properly attached to API requests

### ✅ Token Refresh Logic
- **Issue**: API interceptor uses wrong refresh mechanism for Keycloak
- **Fix**: Conditional refresh logic in `controllers/API/api.tsx`
- **Test**: Verify token refresh uses appropriate method

### ✅ Event Handlers
- **Issue**: Missing Keycloak token lifecycle management
- **Fix**: Event handlers in `contexts/authContext.tsx`
- **Test**: Verify token expiration and refresh handling

### ✅ State Synchronization
- **Issue**: Auth store and Keycloak state not synchronized
- **Fix**: `syncKeycloakAuthState()` method in auth store
- **Test**: Verify consistent authentication state

## Testing Checklist

### Browser Testing

1. **Open Keycloak Frontend (Port 3001)**
   - [ ] Page loads without errors
   - [ ] No autologin requests in Network tab
   - [ ] Keycloak configuration visible in `env-config.js`
   - [ ] Console shows Keycloak-related logs
   - [ ] API requests include Bearer tokens after authentication

2. **Open Traditional Frontend (Port 3002)**
   - [ ] Page loads without errors
   - [ ] Autologin request visible in Network tab
   - [ ] Traditional auth works as expected
   - [ ] API requests include Bearer tokens
   - [ ] No Keycloak-related logs in console

3. **API Request Validation**
   - [ ] All API requests include `Authorization: Bearer <token>` header
   - [ ] No 401 Unauthorized errors for authenticated requests
   - [ ] Token refresh works correctly
   - [ ] Logout clears authentication state

### Network Tab Inspection

**Keycloak Frontend (Port 3001):**
- ✅ No `/api/v1/auto_login` requests
- ✅ Bearer tokens in API request headers
- ✅ Keycloak authentication redirects (if needed)

**Traditional Frontend (Port 3002):**
- ✅ `/api/v1/auto_login` request on page load
- ✅ Bearer tokens in API request headers
- ✅ Traditional token refresh requests

## Configuration Files

- `docker-compose.test.yml` - Multi-container test setup
- `mock-backend.conf` - Nginx configuration for mock API
- `test-backend-config.json` - Mock backend configuration
- `nginx.conf.template` - Frontend nginx template
- `test-authentication.sh` - Comprehensive test script

## Debugging

### View Environment Configuration
```bash
# Keycloak frontend config
curl http://localhost:3001/env-config.js

# Traditional frontend config
curl http://localhost:3002/env-config.js
```

### Test API Endpoints
```bash
# Health check
curl http://localhost:7860/health

# Auto login (traditional)
curl http://localhost:7860/api/v1/auto_login

# User data with Bearer token
curl -H "Authorization: Bearer mock-token" http://localhost:7860/api/v1/users/whoami
```

### View Container Logs
```bash
# Frontend logs
docker logs ai-studio-frontend-keycloak-test
docker logs ai-studio-frontend-traditional-test

# Backend logs
docker logs ai-studio-mock-backend
```

## Expected Results

After implementing the authentication fixes:

1. **Keycloak Frontend** should not make autologin requests
2. **Both frontends** should properly attach Bearer tokens to API requests
3. **Token refresh** should use appropriate mechanisms (Keycloak vs traditional)
4. **Authentication state** should be consistent throughout the application
5. **No 401 errors** should occur due to missing or expired tokens

## Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   Keycloak Frontend │    │ Traditional Frontend│    │    Mock Backend     │
│     (Port 3001)     │    │     (Port 3002)     │    │     (Port 7860)     │
│                     │    │                     │    │                     │
│ ✅ Keycloak Enabled │    │ ❌ Keycloak Disabled│    │ 🔧 API Simulation   │
│ ❌ Autologin Disabled│    │ ✅ Autologin Enabled │    │ 📝 Request Logging  │
│ 🔐 Bearer Tokens    │    │ 🔐 Bearer Tokens    │    │ 🌐 CORS Enabled     │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                           │                           ▲
         │                           │                           │
         └───────────────────────────┼───────────────────────────┘
                                     │
                              API Requests with
                              Bearer Tokens
```

This testing setup validates all the authentication fixes implemented in the AI Studio frontend for proper Keycloak integration.