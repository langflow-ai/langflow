# Custom Test Fixtures

## Overview

Langflow extends Playwright's default `test` and `expect` with a custom fixture in `src/frontend/tests/fixtures.ts`. This fixture adds **automatic error detection** that fails tests when unexpected API errors or flow execution errors occur.

## Why Custom Fixtures Exist

Without the custom fixture, a test could pass even though:
- The backend returned a 500 Internal Server Error (test only checked for UI text)
- A flow build silently failed with a Python exception (test only checked button state)
- An API call returned 404 because the resource was deleted (test didn't check the response)

The custom fixture catches these silent failures by monitoring ALL `/api/` responses during the test.

## Import Rule

**Always import from `../../fixtures`, never from `@playwright/test`:**

```typescript
// Right — includes error detection
import { expect, test } from "../../fixtures";

// Wrong — NO error detection, silent failures possible
import { expect, test } from "@playwright/test";
```

## What the Fixture Detects

### HTTP Error Responses

The fixture intercepts all responses from `/api/` endpoints and fails the test if:

| Status Code | Meaning | Why it Fails |
|-------------|---------|-------------|
| 400 | Bad Request | Client sent invalid data — likely a bug in the frontend |
| 404 | Not Found | Resource doesn't exist — likely a stale ID or missing setup |
| 422 | Validation Error | Pydantic validation failed — likely a schema mismatch |
| 500 | Internal Server Error | Backend crash — always a bug |

### Flow Execution Errors

For streaming responses (build, chat), the fixture parses the event stream and fails if:
- JSON payload contains `"error": true`
- Response body contains Python exception patterns (`Traceback`, `Error`, etc.)
- The stream indicates a component build failure

## Allowing Expected Errors

Some tests intentionally trigger errors (testing error handling, validation feedback, etc.). Use `page.allowFlowErrors()` to prevent the fixture from failing on flow execution errors:

```typescript
test("should show error message on invalid component config", { tag: ["@release"] }, async ({ page }) => {
  page.allowFlowErrors();  // Allow flow errors for THIS test only

  await awaitBootstrapTest(page);
  // ... test that triggers an error ...

  await expect(page.getByText(/error/i)).toBeVisible();
});
```

**Note**: `allowFlowErrors()` only suppresses flow execution errors. HTTP 500 errors will still fail the test — those indicate a backend crash, not expected behavior.

## Error Reporting

When the fixture detects an error, it adds it to an internal list. After the test function completes, the fixture checks the list and fails with a descriptive message:

```
Test failed due to unexpected API errors:
  - POST /api/v1/build/abc123/flow → 500 Internal Server Error
  - Flow execution error: Traceback (most recent call last)...
```

This makes it easy to identify the root cause without adding manual response checks to every test.

## Timeout Behavior

The fixture reads response bodies with a 2-second timeout. If the body can't be read within 2 seconds (e.g., streaming response still in progress), it skips body parsing for that response. This prevents the fixture from blocking indefinitely on long-running streams.

## Global Teardown

`src/frontend/tests/globalTeardown.ts` runs after all tests complete and removes the temporary test database. This ensures a clean state for the next test run.
