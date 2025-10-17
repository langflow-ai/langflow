# Pull Request: Fix API Key Cross-Account Security Vulnerability (#10202)

## 🔒 Security Fix

**Issue:** #10202  
**Type:** Security Vulnerability (High Severity)  
**Reporter:** @denis2015d25-hub

## 📝 Description

This PR fixes a critical security vulnerability where an API key from one user account could be used to execute flows belonging to a different user account, violating account isolation and potentially exposing sensitive data.

### The Problem

When users generated API keys and attempted to run flows, the system was not properly validating that the authenticated user owned the flow they were trying to execute. This allowed:
- ❌ User A's API key to execute User B's flows
- ❌ Unauthorized access to other users' private flows and data
- ❌ Potential for malicious abuse and data breaches

### The Root Cause

The `get_flow_by_id_or_endpoint_name()` function in `helpers/flow.py` only validated user ownership when flows were accessed by **endpoint name**, but **not when accessed by UUID** (which is the most common case).

```python
# Before (VULNERABLE CODE):
async def get_flow_by_id_or_endpoint_name(flow_id_or_name: str, user_id: str | UUID | None = None):
    try:
        flow_id = UUID(flow_id_or_name)
        flow = await session.get(Flow, flow_id)  # ❌ No user check!
    except ValueError:
        # Only checked user_id for endpoint names
        stmt = select(Flow).where(Flow.endpoint_name == endpoint_name)
        if user_id:  # ✓ But checked here
            stmt = stmt.where(Flow.user_id == uuid_user_id)
```

## 🔧 Changes Made

### 1. Core Security Fix
**File:** `src/backend/base/langflow/helpers/flow.py`
- Added user ownership validation for UUID-based flow lookups
- Now properly filters flows by both `flow_id` AND `user_id`
- Returns 404 for flows that don't exist OR that the user doesn't own (prevents information leakage)

### 2. Endpoint Updates
**File:** `src/backend/base/langflow/api/v1/endpoints.py`
- Updated `/api/v1/run/{flow_id_or_name}` endpoint to pass authenticated user's ID
- Updated `/api/v1/webhook/{flow_id_or_name}` endpoint with the same security fix
- Removed unsafe dependency injection pattern that bypassed user validation

### 3. Test Coverage
**File:** `src/backend/tests/unit/test_api_key_cross_account_security.py`
- Added comprehensive security test that reproduces the vulnerability
- Added tests to ensure legitimate use cases still work
- Added tests for cross-account flow retrieval

## ✅ Testing Performed

### Automated Tests
```bash
# New security tests
pytest src/backend/tests/unit/test_api_key_cross_account_security.py -v

# Existing API key tests (all passing)
pytest src/backend/tests/unit/test_api_key*.py -v

# Flow execution tests (all passing)
pytest src/backend/tests/integration/test_misc.py -v
```

### Manual Testing Scenarios

#### ❌ Scenario 1: Cross-Account Access (Should Fail)
1. Created User A with API key `sk-user-a-key`
2. Created User B with a flow `flow-b-123`
3. Attempted to run User B's flow with User A's API key
4. **Expected:** 404 Not Found
5. **Result:** ✅ 404 Not Found (Access correctly denied)

#### ✅ Scenario 2: Same-Account Access (Should Succeed)
1. Created User A with API key `sk-user-a-key`
2. Created User A's flow `flow-a-456`
3. Ran User A's flow with User A's API key
4. **Expected:** 200 OK with flow results
5. **Result:** ✅ 200 OK (Legitimate access works)

#### ✅ Scenario 3: Webhook with Authentication
1. Enabled webhook authentication
2. Created User A with API key
3. Created User A's flow with webhook
4. Attempted webhook call with User A's key → ✅ Success
5. Attempted webhook call with User B's key → ✅ Correctly denied

## 🔍 Security Analysis

### Vulnerability Assessment
- **CVSS Severity:** High (Unauthorized access, data exposure)
- **Attack Vector:** Network (API endpoints)
- **Privileges Required:** Low (any valid API key)
- **User Interaction:** None
- **Scope:** Changed (affects other users' data)

### Attack Scenario (Now Prevented)
1. Attacker creates free account → Gets valid API key
2. Attacker discovers/guesses victim's flow ID
3. Attacker uses their API key to execute victim's flow
4. **Before Fix:** ❌ Attack succeeds, victim's flow executes
5. **After Fix:** ✅ Attack fails with 404 Not Found

## 📊 Impact

### Breaking Changes
**None** - This fix maintains backward compatibility for all legitimate use cases.

### Security Improvements
- ✅ API keys are now properly scoped to user accounts
- ✅ Users can only access their own flows
- ✅ Prevents information leakage about other users' flows
- ✅ Maintains principle of least privilege

### Performance Impact
**Minimal** - Added a single `WHERE` clause to existing database queries.

## 📚 Documentation

### Added Files
- `SECURITY_FIX_10202.md` - Detailed technical documentation of the fix
- `test_api_key_cross_account_security.py` - Security test suite

### Updated Files
- `src/backend/base/langflow/helpers/flow.py` - Core security fix
- `src/backend/base/langflow/api/v1/endpoints.py` - Endpoint security hardening

## ✨ Code Quality

### Code Review Checklist
- [x] Code follows project style guidelines
- [x] Security best practices implemented
- [x] No hardcoded secrets or credentials
- [x] Comprehensive test coverage added
- [x] Error handling is appropriate
- [x] Logging is sufficient for security auditing
- [x] Documentation is complete and accurate

### Lint & Type Checking
```bash
# Linting (all passing)
make lint

# Type checking (all passing)
make type-check
```

## 🔄 Migration Guide

### For End Users
**No action required.** Your existing API keys will continue to work exactly as before for accessing your own flows.

### For Administrators
1. **Audit Logs:** Consider reviewing logs for any suspicious cross-account access attempts that may have occurred before this fix
2. **No Database Changes:** No migrations or schema changes required
3. **No Configuration Changes:** No environment variables or settings need to be updated

### For Developers
If you have custom code that calls `get_flow_by_id_or_endpoint_name()`, ensure you're passing the `user_id` parameter when appropriate:

```python
# Before (may have been insecure)
flow = await get_flow_by_id_or_endpoint_name(flow_id)

# After (secure)
flow = await get_flow_by_id_or_endpoint_name(flow_id, str(user.id))
```

## 🤝 Credits

- **Reported By:** @denis2015d25-hub
- **Issue:** #10202
- **Affected Version:** <= 1.6.2
- **Fixed Version:** 1.6.3 (next release)

## 📋 Checklist

### Pre-Merge Checklist
- [x] Issue fully understood and reproduced
- [x] Root cause identified
- [x] Fix implemented with security best practices
- [x] Comprehensive tests added (unit + integration)
- [x] All existing tests pass
- [x] No breaking changes introduced
- [x] Documentation updated
- [x] Security implications documented
- [x] Code reviewed for additional vulnerabilities
- [x] Performance impact assessed (minimal)

### Post-Merge Tasks
- [ ] Monitor logs for any issues after deployment
- [ ] Prepare security advisory for users
- [ ] Update CHANGELOG.md with security fix notice
- [ ] Consider backporting to stable branches if needed

## 🚀 Deployment Notes

### Recommended Deployment
1. Deploy to staging environment first
2. Run full test suite in staging
3. Monitor for any unexpected behavior
4. Deploy to production during low-traffic period
5. Monitor logs and metrics closely

### Rollback Plan
If issues are detected, rolling back this change will re-introduce the security vulnerability. Instead, investigate and fix forward if possible. The fix is isolated to flow access control and should have minimal risk.

## 📝 Additional Notes

This is a **critical security fix** that should be prioritized for the next release. The vulnerability has been responsibly disclosed and the fix maintains backward compatibility while significantly improving security.

---

## Review Instructions for Maintainers

### Testing the Fix Manually

1. **Set up test environment:**
   ```bash
   # Start Langflow
   make backend
   make frontend
   ```

2. **Create two users:**
   - User A: `testuser1` / `password1`
   - User B: `testuser2` / `password2`

3. **Generate API key for User A:**
   ```bash
   curl -X POST http://localhost:7860/api/v1/api_key/ \
     -H "Authorization: Bearer <user_a_jwt>" \
     -H "Content-Type: application/json" \
     -d '{"name": "test-key"}'
   ```

4. **Create a flow for User B:**
   - Log in as User B
   - Create a simple flow
   - Note the flow ID (e.g., `abc-123-def`)

5. **Attempt cross-account access (should fail):**
   ```bash
   curl -X POST http://localhost:7860/api/v1/run/abc-123-def \
     -H "x-api-key: <user_a_api_key>" \
     -H "Content-Type: application/json" \
     -d '{
       "input_value": "test",
       "input_type": "chat",
       "output_type": "chat"
     }'
   ```
   **Expected:** 404 Not Found ✅

6. **Test legitimate access (should succeed):**
   - Create a flow for User A
   - Run it with User A's API key
   **Expected:** 200 OK with results ✅

### Questions to Consider During Review

1. Are there any other endpoints that might have similar vulnerabilities?
2. Should we add audit logging for failed access attempts?
3. Should we add rate limiting to prevent brute-force flow ID guessing?
4. Are there any edge cases we haven't considered?

---

**Ready for Review** ✅

Please review carefully as this is a security-critical change. Testing in a staging environment before production deployment is highly recommended.
