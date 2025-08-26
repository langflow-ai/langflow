# JWT Docker Deployment Issue - Complete Solution Report

Hi @brunorafaeI,

Thank you for reporting this JWT authentication issue. Based on the conversation thread and my analysis of the Langflow codebase, I've identified the complete picture of your problem and the proper solution.

## Root Cause Analysis

The JWT signature verification error (`JWSSignatureError`) in Docker deployments has TWO interconnected causes:

### 1. Missing/Inconsistent SECRET_KEY
When `LANGFLOW_SECRET_KEY` is not set, each Docker container generates its own random key using `secrets.token_urlsafe(32)` (see `/src/backend/base/langflow/services/settings/auth.py` lines 103, 118, 122). This causes JWT tokens signed by one container to fail verification in another.

### 2. AUTO_LOGIN Strict Validation (v1.5+)
Starting in Langflow v1.5, the AUTO_LOGIN feature requires a valid API key. Without `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true`, the system enforces strict JWT/API key validation, which exposes the SECRET_KEY inconsistency issue more prominently.

## Why SKIP_AUTH_AUTO_LOGIN "Fixed" It

Setting `LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true` bypasses the strict API key requirement for AUTO_LOGIN, allowing fallback to username-based authentication. This masks the JWT signature errors but doesn't fix the underlying SECRET_KEY problem.

**Important**: This is a temporary workaround. As @jordanrfrazier noted, this option will be **removed in v1.6**, so you need a proper solution.

## The Proper Solution

### Step 1: Generate a Consistent SECRET_KEY

```bash
# Option A: Using token_urlsafe (Langflow's default method)
python3 -c "import secrets; print(f'LANGFLOW_SECRET_KEY={secrets.token_urlsafe(32)}')"

# Option B: Using Fernet key (also works perfectly)
python3 -c "from cryptography.fernet import Fernet; print(f'LANGFLOW_SECRET_KEY={Fernet.generate_key().decode()}')"

# Option C: Any string >= 32 characters
echo "LANGFLOW_SECRET_KEY=your-very-long-secret-key-at-least-32-chars"
```

### Step 2: Set Environment Variables Correctly

**docker-compose.yml:**
```yaml
services:
  langflow:
    image: langflowai/langflow:latest
    ports:
      - "7860:7860"
    environment:
      - LANGFLOW_HOST=0.0.0.0
      - LANGFLOW_PORT=7860
      - LANGFLOW_SECRET_KEY=<your-generated-key-here>
      - LANGFLOW_AUTO_LOGIN=true  # or false for production
      # For now (until v1.6):
      - LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true  # Remove this after fixing SECRET_KEY
      # Optional: Remove CONFIG_DIR to avoid permission issues
      # - LANGFLOW_CONFIG_DIR=/path/to/config
```

### Step 3: Verify Configuration

Connect to your container and verify:
```bash
docker exec -it <container-name> /bin/bash
env | grep LANGFLOW_SECRET_KEY
env | grep -i secret  # Check for conflicting variables
```

Make sure:
- `LANGFLOW_SECRET_KEY` is set and consistent
- No conflicting variables like `JWT_SECRET_KEY`, `SECRET_KEY`, or `FERNET_KEY`
- No `.env` file overriding your settings

### Step 4: Clean Restart

```bash
docker-compose down
docker-compose up -d
```

## Migration Path for v1.6

Since `LANGFLOW_SKIP_AUTH_AUTO_LOGIN` will be removed in v1.6:

1. **Development**: Set a consistent `LANGFLOW_SECRET_KEY` now
2. **Production**: Consider setting `LANGFLOW_AUTO_LOGIN=false` and implementing proper authentication
3. **Test**: Remove `LANGFLOW_SKIP_AUTH_AUTO_LOGIN` and verify everything works

## Technical Details

### How the Authentication Flow Works:
1. With `AUTO_LOGIN=true` and no API key provided:
   - If `skip_auth_auto_login=true`: Falls back to username lookup (pre-v1.5 behavior)
   - If `skip_auth_auto_login=false`: Returns HTTP 403 error (v1.5+ behavior)

2. JWT tokens are signed/verified using `LANGFLOW_SECRET_KEY`:
   - Same key across containers = tokens work everywhere
   - Different keys = signature verification fails

### Key Processing:
The `ensure_valid_key()` function in `/src/backend/base/langflow/services/auth/utils.py` is deterministic:
- Keys >= 32 chars: Adds padding if needed
- Keys < 32 chars: Uses as seed for consistent key generation
- Both `token_urlsafe(32)` and `Fernet.generate_key()` work equally well

## Summary

Your immediate fix (`LANGFLOW_SKIP_AUTH_AUTO_LOGIN=true`) works but is temporary. The proper solution is to:
1. Set a consistent `LANGFLOW_SECRET_KEY` across all containers
2. Plan to remove `LANGFLOW_SKIP_AUTH_AUTO_LOGIN` before v1.6
3. Consider proper authentication for production environments

This ensures your deployment will continue working in future Langflow versions.

Let me know if you need any clarification!

Best regards,  
Langflow Support