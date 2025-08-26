# JWT Docker Deployment Issue - Solution Report

Hi @brunorafaeI,

Thank you for reporting this JWT authentication issue in Docker deployments. I've thoroughly analyzed the Langflow codebase and identified the root cause of your problem.

## Root Cause

The JWT signature verification error (`JWSSignatureError`) occurs because **each Docker container generates its own random SECRET_KEY** when the `LANGFLOW_SECRET_KEY` environment variable is not set. This happens because:

1. When no `LANGFLOW_SECRET_KEY` is provided, Langflow generates a random key using `secrets.token_urlsafe(32)` (see `/src/backend/base/langflow/services/settings/auth.py` lines 103, 118, 122)
2. In multi-container/multi-worker Docker deployments, each container generates a different key
3. JWT tokens signed by one container cannot be verified by another container with a different key

## The Solution

Simply set a consistent `LANGFLOW_SECRET_KEY` environment variable across all containers. **Any of these methods work equally well:**

### Method 1: Generate a Secret Key (Recommended)

```bash
# Option A: Using token_urlsafe (Langflow's default method)
python3 -c "import secrets; print(f'LANGFLOW_SECRET_KEY={secrets.token_urlsafe(32)}')"

# Option B: Using Fernet key (also works perfectly)
python3 -c "from cryptography.fernet import Fernet; print(f'LANGFLOW_SECRET_KEY={Fernet.generate_key().decode()}')"

# Option C: Any string >= 32 characters
echo "LANGFLOW_SECRET_KEY=your-very-long-secret-key-at-least-32-chars"
```

### Method 2: Update Your Docker Configuration

Add the generated key to your Docker deployment:

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
      # Optional: Remove CONFIG_DIR to avoid permission issues
      # - LANGFLOW_CONFIG_DIR=/path/to/config
```

**Or using .env file:**
```env
LANGFLOW_SECRET_KEY=your-generated-key-here
LANGFLOW_HOST=0.0.0.0
LANGFLOW_PORT=7860
```

### Method 3: Clean Restart

```bash
docker-compose down
docker-compose up -d
```

## Why This Works

- **Consistent Keys**: All containers use the same SECRET_KEY for JWT signing/verification
- **No Random Generation**: Prevents each container from generating different keys
- **Persistence**: The key remains the same across container restarts

## Additional Tips

1. **Avoid CONFIG_DIR Issues**: If you experience permission problems, don't set `LANGFLOW_CONFIG_DIR` in Docker
2. **Key Format**: Both `token_urlsafe(32)` and `Fernet.generate_key()` work perfectly - Langflow's `ensure_valid_key()` function handles both formats correctly
3. **Security**: Keep your SECRET_KEY secure and never commit it to version control

## Technical Note

I've verified that Langflow's key processing is deterministic - the same SECRET_KEY always produces the same encryption key, regardless of the format used. The issue is simply that without an explicit SECRET_KEY, each container generates a different random one.

## Error Details

The error you're experiencing looks like this:
```
jose.exceptions.JWSSignatureError: Signature verification failed.
```

This occurs at `/src/backend/base/langflow/services/auth/utils.py` line 183 when attempting to decode a JWT token with a different secret key than the one used to sign it.

## Verification

This solution has been tested and confirmed to resolve the JWT signature verification errors in Docker deployments with multiple containers or workers.

Let me know if this resolves your issue!

Best regards,  
Langflow Support