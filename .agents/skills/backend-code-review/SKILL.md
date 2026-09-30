---
name: backend-code-review
description: Review backend code for quality, security, maintainability, and best practices based on established checklist rules. Use when the user requests a review, analysis, or improvement of backend files (e.g., `.py`) under the `src/backend/` directory. Do NOT use for frontend files (e.g., `.tsx`, `.ts`, `.js`). Supports pending-change review, code snippets review, and file-focused review.
---

# Backend Code Review

## When to use this skill

Use this skill whenever the user asks to **review, analyze, or improve** backend code (e.g., `.py`) under the `src/backend/` directory. Supports the following review modes:

- **Pending-change review**: when the user asks to review current changes (inspect staged/working-tree files slated for commit to get the changes).
- **Code snippets review**: when the user pastes code snippets (e.g., a function/class/module excerpt) into the chat and asks for a review.
- **File-focused review**: when the user points to specific files and asks for a review of those files (one file or a small, explicit set of files, e.g., `src/backend/base/langflow/api/v1/flows.py`).

Do NOT use this skill when:

- The request is about frontend code or UI (e.g., `.tsx`, `.ts`, `.js`, `src/frontend/`).
- The user is not asking for a review/analysis/improvement of backend code.
- The scope is not under `src/backend/` (unless the user explicitly asks to review backend-related changes outside `src/backend/`).

## How to use this skill

Follow these steps when using this skill:

1. **Identify the review mode** (pending-change vs snippet vs file-focused) based on the user's input. Keep the scope tight: review only what the user provided or explicitly referenced.
2. Follow the rules defined in **Checklist** to perform the review. If no Checklist rule matches, apply **General Review Rules** as a fallback to perform the best-effort review.
3. Compose the final output strictly following the **Required Output Format**.

Notes when using this skill:
- Always include actionable fixes or suggestions (including possible code snippets).
- Use best-effort `File:Line` references when a file path and line numbers are available; otherwise, use the most specific identifier you can.

## Checklist

- db schema design: if the review scope includes code/files under `src/backend/base/langflow/services/database/models/` or Alembic migrations under `src/backend/base/langflow/alembic/versions/`, follow [references/db-schema-rule.md](references/db-schema-rule.md) to perform the review
- architecture: if the review scope involves route/service/model layering, dependency direction, or moving responsibilities across modules, follow [references/architecture-rule.md](references/architecture-rule.md) to perform the review
- service abstraction: if the review scope contains table/model operations (e.g., `select(...)`, `session.execute(...)`, joins, CRUD) and is not already inside a service under `src/backend/base/langflow/services/`, follow [references/repositories-rule.md](references/repositories-rule.md) to perform the review
- sqlalchemy patterns: if the review scope involves SQLAlchemy/SQLModel session/query usage, db transaction/crud usage, `session_scope()` usage, or raw SQL usage, follow [references/sqlalchemy-rule.md](references/sqlalchemy-rule.md) to perform the review

## General Review Rules

### 1. Security Review

Check for:
- SQL injection vulnerabilities (especially raw `text()` queries with string interpolation). Consequence: attacker can read/modify/delete any data in the database.
- Server-Side Request Forgery (SSRF) in component HTTP calls. Consequence: attacker uses the server to scan internal networks or access cloud metadata endpoints.
- Command injection (especially in subprocess or shell-executing components). Consequence: attacker gains shell access to the server.
- Insecure deserialization (pickle, yaml.load without SafeLoader). Consequence: arbitrary code execution on the server.
- Hardcoded secrets/credentials. Consequence: secrets leak via git history and are impossible to fully revoke.
- Improper authentication/authorization (missing `CurrentActiveUser` dependency). Consequence: unauthenticated users can access protected endpoints.
- Insecure direct object references (missing `user_id` scoping on queries). Consequence: user A can read/modify user B's flows, variables, API keys.
- Path traversal in file storage operations. Consequence: attacker reads arbitrary server files (e.g., `/etc/passwd`, `.env`).

### 2. Performance Review

Check for:
- N+1 queries (especially in loops calling `session.execute()`). Consequence: 100 flows = 101 DB queries instead of 2; page load goes from 50ms to 5s.
- Missing database indexes on frequently queried columns. Consequence: full table scans on large datasets; queries degrade from O(log n) to O(n).
- Memory leaks (unbounded caches, retained references in long-lived services). Consequence: server OOM after hours of operation; pods restart in production.
- Blocking operations in async code (`time.sleep()`, synchronous I/O, CPU-bound work without `run_in_executor`). Consequence: entire event loop stalls; all concurrent requests hang until the blocking call completes.
- Missing caching opportunities for expensive computations. Consequence: repeated computation of the same result on every request.
- Large result sets loaded entirely into memory without pagination. Consequence: memory spike + slow response when user has 10K+ flows.

### 3. Code Quality Review

Check for:
- Code forward compatibility with Python 3.10-3.13
- Code duplication (DRY violations — extract when the *exact same business rule* is duplicated in 3+ places)
- Functions doing too much (SRP violations — if you need "and" to describe it, split it)
- Deep nesting / complex conditionals (prefer early returns and guard clauses)
- Magic numbers/strings (extract to named constants or enums)
- Poor naming: unclear abbreviations, misleading names, generic names (`data`, `result`, `obj`, `temp`). Functions should use verbs (`get`, `create`, `validate`). Booleans should use prefixes (`is_`, `has_`, `can_`, `should_`).
- Missing error handling (bare `except`, swallowed exceptions, silent failures)
- Incomplete type coverage (use strong typing, avoid `Any` where a concrete type is known)
- Use Python 3.10+ union syntax (`X | Y` not `Union[X, Y]`, `X | None` not `Optional[X]`)
- Use `TYPE_CHECKING` guard for imports only needed for type annotations (prevents circular imports)
- Use `Annotated[Type, Depends(...)]` with project aliases (`CurrentActiveUser`, `DbSession`, `DbSessionReadOnly`) for FastAPI DI
- Google-style docstrings (enforced by Ruff): `Args:`, `Returns:`, `Raises:` sections for public functions
- Violations of SOLID principles
- YAGNI violations (code that anticipates future needs without a present requirement)
- Line length exceeding 120 characters (project Ruff config)
- Comments that explain WHAT instead of WHY (comments should only explain reasoning, not restate code)
- Commented-out code (use version control instead)
- Boolean parameters that switch function behavior (split into two named functions instead)
- Mutable shared state where immutable alternatives exist (prefer returning new objects over mutation)

### 4. File Structure Review

Check for:
- Production files exceeding ~500 lines of code (excluding imports, types, and docstrings). Files above 600 lines are a red flag and should be split by responsibility. Why: Files above 500 lines have statistically higher defect rates and take longer to review. They signal multiple responsibilities (SRP violation). In Langflow, services like `DatabaseService` that grow beyond this limit should have their CRUD operations extracted to dedicated modules.
- Test files exceeding ~1000 lines. Split by logical grouping if exceeded.
- No more than 5 functions with different responsibilities in a single file (per AGENTS-example.md).
- Each file has a single reason to exist and a single reason to change (SRP).
- No generic file names: `utils.py`, `helpers.py`, `misc.py`, `common.py` as standalone files. Why: A file named `utils.py` becomes a dumping ground for unrelated functions. Within months it has 50+ functions covering formatting, validation, parsing, and HTTP calls — violating SRP. Each function group should be in a file named after its responsibility (`formatting.py`, `validation.py`).

### 5. Testing Review

Check for:
- Missing test coverage for new code paths
- Tests that don't test behavior (testing implementation details)
- Flaky test patterns (time-dependent, order-dependent, external-service-dependent)
- Proper use of `pytest.mark.asyncio` for async tests
- Excessive mocking (prefer real integrations per project conventions)
- Coverage target: 80% (minimum acceptable: 75%)
- Test anti-patterns: The Liar (passes but doesn't verify claimed behavior), The Mirror (asserts exactly what code does), The Giant (50+ lines setup), The Mockery (tests only mock setup), The Inspector (coupled to implementation), The Chain Gang (depends on execution order), The Flaky (inconsistent results)

**Happy path tests are the foundation but are NOT enough.** Tests MUST also challenge the code to find real defects:

- **Unexpected inputs**: `None`, `""`, `[]`, `{}`, `0`, `-1`, `UUID("00000000-0000-0000-0000-000000000000")`
- **Boundary values**: max length strings, exactly at the limit, one past the limit, zero items, max items
- **Malformed data**: missing required fields, extra unexpected fields, wrong types, invalid formats
- **Error states**: what happens when the database is down? When an external API returns 500? When the user doesn't exist?
- **What should NOT happen**: verify that user A CANNOT access user B's flows. Verify that a deleted flow returns 404. Verify that invalid `endpoint_name` is rejected with 422.
- **Error messages and types**: not just that it fails, but that it fails with the RIGHT exception and the RIGHT message
- **Concurrency**: what happens when two requests try to update the same flow simultaneously?

**Write tests based on REQUIREMENTS/SPEC, not on what the source code currently does.** This is how you catch bugs where the code diverges from expected behavior.

**When a test fails:** first ask if the CODE is wrong, not the test. Do NOT silently change a failing assertion to match the current code without understanding WHY.

### 6. Observability Review

Check for:
- Use the async logger from `lfx.log.logger` with `a`-prefixed methods (`adebug`, `ainfo`, `awarning`, `aerror`, `aexception`). Never use `print()` or stdlib `logging`.
- Log at key decision points and boundaries, not inside tight loops
- Include: operation name, relevant IDs, outcome (success/failure), duration if relevant
- Correct log levels: ERROR (broken, needs attention), WARN (degraded but recoverable), INFO (significant events), DEBUG (diagnostic, off in prod)
- **ZERO PII TOLERANCE**: Never log email addresses, user names, phone numbers, tokens, passwords. Only approved identifiers: `user_id`, `flow_id`, `session_id`
- No `print()` statements — these go to production logs
- Use `{e!s}` for string representation of exceptions in log messages

### 7. Pre-Commit Verification

For pending-change reviews, verify the author has run:
- `make format_backend` (Ruff formatter) — inconsistent formatting creates noisy diffs that hide real changes in code review. Format first, review second.
- `make lint` (MyPy type checking) — type errors caught at lint time are 10x cheaper to fix than runtime crashes in production. Langflow services use duck typing via `Service` base class; MyPy catches mismatches early.
- `make unit_tests` (pytest) — a failing test means the change breaks existing behavior. Never merge with failing tests; investigate whether the code or the test is wrong.

## Required Output Format

When this skill is invoked, the response must exactly follow one of the two templates:

### Template A (any findings)

```markdown
# Code Review Summary

Found <X> critical issues need to be fixed:

## 🔴 Critical (Must Fix)

### 1. <brief description of the issue>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the issue>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each critical issue) ...

Found <Y> suggestions for improvement:

## 🟡 Suggestions (Should Consider)

### 1. <brief description of the suggestion>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<detailed explanation and references of the suggestion>

#### Suggested Fix

1. <brief description of suggested fix>
2. <code example> (optional, omit if not applicable)

---
... (repeat for each suggestion) ...

Found <Z> optional nits:

## 🟢 Nits (Optional)
### 1. <brief description of the nit>

FilePath: <path> line <line>
<relevant code snippet or pointer>

#### Explanation

<explanation and references of the optional nit>

#### Suggested Fix

- <minor suggestions>

---
... (repeat for each nits) ...

## ✅ What's Good

- <Positive feedback on good patterns>
```

- If there are no critical issues or suggestions or optional nits or good points, just omit that section.
- If the issue number is more than 10, summarize as "Found 10+ critical issues/suggestions/optional nits" and only output the first 10 items.
- Don't compress the blank lines between sections; keep them as-is for readability.
- If there is any issue that requires code changes, append a brief follow-up question to ask whether the user wants to apply the fix(es) after the structured output. For example: "Would you like me to use the Suggested fix(es) to address these issues?"

### Template B (no issues)

```markdown
## Code Review Summary
✅ No issues found.
```
