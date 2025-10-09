# Security Fix for API Key Cross-Account Access Vulnerability

## Issue #10202: Token Cross-Account Security Vulnerability

### Problem Description

A critical security vulnerability was discovered where an API token created by one user could be used to execute flows belonging to a different user. This violated the fundamental security principle that tokens should be scoped to a single user account.

**Severity:** High - Allows unauthorized cross-account access

**Reporter:** @denis2015d25-hub

### Root Cause Analysis

The vulnerability existed in the `get_flow_by_id_or_endpoint_name()` function in `/src/backend/base/langflow/helpers/flow.py`. 

**Before the fix:**
```python
async def get_flow_by_id_or_endpoint_name(flow_id_or_name: str, user_id: str | UUID | None = None) -> FlowRead | None:
    async with session_scope() as session:
        try:
            flow_id = UUID(flow_id_or_name)
            flow = await session.get(Flow, flow_id)  # ❌ No user_id check!
        except ValueError:
            # Only checked user_id for endpoint names, not UUIDs
            stmt = select(Flow).where(Flow.endpoint_name == endpoint_name)
            if user_id:
                stmt = stmt.where(Flow.user_id == uuid_user_id)
            flow = (await session.exec(stmt)).first()
```

**The Problem:**
1. When a flow was requested by UUID (the most common case), the function would retrieve the flow WITHOUT checking if the authenticated user owned it
2. User validation was only performed when accessing flows by endpoint name
3. This allowed any authenticated user with a valid API key to execute ANY flow in the system, regardless of ownership

### Reproduction Steps

1. Create User Account A
2. Generate an API key for User A
3. Create User Account B  
4. Create a flow in User B's account
5. Use User A's API key to execute User B's flow via `/api/v1/run/{flow_id}` endpoint
6. **Result:** The flow executes successfully (❌ SECURITY ISSUE)
7. **Expected:** The request should be rejected with 403 or 404 error

### The Fix

#### 1. Core Function Fix (`helpers/flow.py`)

Updated `get_flow_by_id_or_endpoint_name()` to ALWAYS validate user ownership:

```python
async def get_flow_by_id_or_endpoint_name(flow_id_or_name: str, user_id: str | UUID | None = None) -> FlowRead | None:
    async with session_scope() as session:
        endpoint_name = None
        try:
            flow_id = UUID(flow_id_or_name)
            # ✅ SECURITY FIX: Check user_id for UUID-based lookups
            if user_id:
                uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
                stmt = select(Flow).where(Flow.id == flow_id, Flow.user_id == uuid_user_id)
                flow = (await session.exec(stmt)).first()
            else:
                flow = await session.get(Flow, flow_id)
        except ValueError:
            endpoint_name = flow_id_or_name
            stmt = select(Flow).where(Flow.endpoint_name == endpoint_name)
            if user_id:
                uuid_user_id = UUID(user_id) if isinstance(user_id, str) else user_id
                stmt = stmt.where(Flow.user_id == uuid_user_id)
            flow = (await session.exec(stmt)).first()
        if flow is None:
            raise HTTPException(status_code=404, detail=f"Flow identifier {flow_id_or_name} not found")
        return FlowRead.model_validate(flow, from_attributes=True)
```

**Key Changes:**
- When `user_id` is provided and flow is accessed by UUID, we now use a SQL query with both `Flow.id` and `Flow.user_id` filters
- This ensures users can only access flows they own
- Returns 404 if flow doesn't exist OR user doesn't have access (standard security practice to avoid information leakage)

#### 2. Endpoint Updates (`api/v1/endpoints.py`)

Updated the `/run/{flow_id_or_name}` endpoint to pass the authenticated user's ID:

```python
@router.post("/run/{flow_id_or_name}", response_model=None, response_model_exclude_none=True)
async def simplified_run_flow(
    *,
    background_tasks: BackgroundTasks,
    flow_id_or_name: str,  # ✅ Changed from dependency injection
    input_request: SimplifiedAPIRequest | None = None,
    stream: bool = False,
    api_key_user: Annotated[UserRead, Depends(api_key_security)],
    context: dict | None = None,
    http_request: Request,
):
    # ... 
    
    # ✅ SECURITY FIX: Retrieve flow with user ownership validation
    flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, str(api_key_user.id))
    
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flow not found")
    # ...
```

#### 3. Webhook Endpoint Updates

Updated the webhook endpoint to also validate ownership:

```python
@router.post("/webhook/{flow_id_or_name}", ...)
async def webhook_run_flow(
    flow_id_or_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
):
    # Get user with existing webhook authentication logic
    webhook_user = await get_webhook_user(flow_id_or_name, request)
    
    # ✅ SECURITY FIX: Retrieve flow with user ownership validation
    flow = await get_flow_by_id_or_endpoint_name(flow_id_or_name, str(webhook_user.id))
    # ...
```

### Testing

#### Test Coverage Added

Created comprehensive test file: `/src/backend/tests/unit/test_api_key_cross_account_security.py`

**Test Cases:**
1. ✅ `test_cross_account_api_key_should_not_run_flow` - Verifies cross-account access is blocked
2. ✅ `test_same_account_api_key_should_run_own_flow` - Ensures legitimate use cases still work
3. ✅ `test_cross_account_get_flow_should_not_work` - Validates flow retrieval is also protected

#### Running the Tests

```bash
# Run the security tests
pytest src/backend/tests/unit/test_api_key_cross_account_security.py -v

# Run all API key related tests
pytest src/backend/tests/unit/test_api_key*.py -v

# Run integration tests
pytest src/backend/tests/integration/test_misc.py -v -k "api_key"
```

### Security Implications

**Before Fix:**
- ❌ Any user with a valid API key could access ANY flow in the system
- ❌ No isolation between user accounts
- ❌ Potential data breach - users could access other users' private flows and data
- ❌ Potential abuse - malicious users could execute expensive operations on other users' flows

**After Fix:**
- ✅ API keys are properly scoped to user accounts
- ✅ Users can only access their own flows
- ✅ Proper 404 response prevents information leakage about other users' flows
- ✅ Maintains backward compatibility for legitimate use cases

### Impact on Existing Functionality

**No Breaking Changes:**
- Users with valid API keys can still access their own flows
- All existing legitimate workflows continue to function
- Performance impact is minimal (single additional WHERE clause in SQL query)

**Enhanced Security:**
- Prevents unauthorized cross-account access
- Aligns with security best practices
- Maintains principle of least privilege

### Migration Notes

**For Users:**
- No action required
- Existing API keys will continue to work for your own flows
- You will no longer be able to access other users' flows (which you shouldn't have been able to in the first place)

**For Administrators:**
- Consider auditing logs for any suspicious cross-account access attempts
- No database migrations required
- No configuration changes needed

### Additional Security Considerations

**Related Security Measures Already in Place:**
1. Webhook authentication validates flow ownership (in `get_webhook_user()`)
2. OpenAI API endpoint already passes user_id correctly
3. JWT token validation ensures API keys belong to valid users

**Future Enhancements:**
1. Consider adding audit logging for failed access attempts
2. Add rate limiting per user to prevent abuse
3. Consider adding account-level permissions for team/shared flows

### Verification Checklist

- [x] Core vulnerability patched in `get_flow_by_id_or_endpoint_name()`
- [x] All flow execution endpoints updated to pass user_id
- [x] Webhook endpoints secured with user validation
- [x] Test cases added to prevent regression
- [x] No breaking changes to legitimate functionality
- [x] Documentation updated

### Credits

**Issue Reported By:** @denis2015d25-hub  
**Fixed By:** Security Team  
**Issue:** #10202  
**Date:** October 2025  
**Langflow Version:** 1.6.2+

---

## Summary

This fix addresses a critical security vulnerability where API keys could be used to access flows across different user accounts. The solution adds proper user ownership validation at the database query level, ensuring that users can only access flows they own. The fix maintains backward compatibility while significantly improving the security posture of the application.

**Status:** ✅ FIXED - Ready for review and deployment
