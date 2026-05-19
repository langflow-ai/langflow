# 🎯 Code Quality Checklist

> **Purpose:** Use this checklist before submitting your code for review. Address every item to achieve a perfect quality score.
>
> **Applies to:** Any language or framework (Python, TypeScript, JavaScript, Go, Java, C#, Rust, etc.)
>
> **Language:** All review documents (REVIEW_PR_*.md) **MUST be written entirely in English**. This ensures consistency, accessibility for all contributors, and compatibility with automated tooling.
>
> **Companion document:** `DEVELOPMENT_RULE.md` contains the full explanation of each principle with examples. This document focuses on **how to verify** compliance during review.

---

## 📊 Scoring System

| Category | Weight | Description |
|----------|--------|-------------|
| 🔴 **CRITICAL** | Blocker | Failure = immediate PR rejection |
| 🟠 **IMPORTANT** | High | Must be fixed before merge |
| 🟡 **RECOMMENDED** | Medium | Significant quality improvement |
| 🟢 **NICE TO HAVE** | Low | Polish and refinement |

---

## 📤 Output Format — Optimized for GitHub PR Comments

> ⚠️ **The review output is posted as a GitHub comment.** Follow these rules strictly when writing the final review document. Violating any of them produces a broken or noisy comment on GitHub.

### Hard rules (NEVER do these)

- ❌ **NEVER use `#N` to label findings** (e.g., `#1`, `#2`, `#3`). GitHub auto-links `#N` to PR/issue number `N` in the repo, creating false references to unrelated PRs. This is the #1 source of noise in posted reviews.
- ❌ **NEVER use `GH-N`, `gh-N`, or bare issue/PR numbers** for the same reason.
- ❌ **NEVER `@mention` users** unless the user explicitly asked you to ping someone — `@username` sends a notification.
- ❌ **NEVER include `Fixes #N`, `Closes #N`, `Resolves #N`** keywords — they auto-close issues when merged.
- ❌ **NEVER paste full file contents** — link with `path/to/file.ts:42` and quote only the relevant lines.
- ❌ **NEVER include the full checklist** verbatim in the output. The checklist is an internal tool. The output is the *findings* the checklist produced.
- ❌ **NEVER use absolute local paths** (`/Users/...`, `/home/...`). Use repo-relative paths only (`src/foo/bar.ts:42`).
- ❌ **NEVER include emojis in section headers** if the user asked for a "clean" or "professional" output. (Default: emojis OK in severity badges only.)

### Required label format for findings

Use one of these labeling schemes — **never `#N`**:

| Scheme | Example | When to use |
|--------|---------|-------------|
| **Severity-prefixed** (preferred) | `B1`, `B2`, `I1`, `I2`, `R1`, `R2` | Default. `B`=Blocker, `I`=Important, `R`=Recommended, `N`=Nice-to-have |
| **Plain numeric** | `1.`, `2.`, `3.` | Short reviews with < 5 findings, no severity grouping |
| **Finding-prefixed** | `F1`, `F2`, `F3` | Mixed-severity flat list |

When cross-referencing a finding elsewhere in the document, use the same label (e.g., "Test suggestions post-split (B1):" — **not** "(#1)").

### Required structure

The posted comment MUST follow this skeleton:

```markdown
## Code Review Summary

<2-4 sentence verdict: ship / changes-requested / blocked, and the headline reason>

**Verdict:** <Approve | Approve with comments | Request changes | Block>
**Findings:** <N blockers, M important, K recommended>

---

## ⛔ Blockers (resolve before merge)

### B1 — <Short title>
**File:** `path/to/file.ts:42-58`
**Issue:** <1-3 sentence problem statement>
**Why it matters:** <impact / blast radius>
**Suggested fix:** <concrete action>

<details>
<summary>Code reference</summary>

```ts
// quote only the 3-10 most relevant lines
```
</details>

### B2 — <Short title>
...

---

## ⚠️ Important (preferably this PR)

### I1 — <Short title>
...

---

## 💡 Recommended (can ship as a follow-up)

### R1 — <Short title>
...

---

## ✅ Action checklist for the author

**Blockers (resolve before merge):**
- [ ] **B1** — <one-line restatement>
- [ ] **B2** — <one-line restatement>

**Important (preferably this PR):**
- [ ] **I1** — <one-line restatement>

**Recommended (can ship as a follow-up PR):**
- [ ] **R1** — <one-line restatement>

**Test suggestions (post-B1 split):**
- [ ] <test 1>
- [ ] <test 2>
```

### Length and density

- **Target length:** 300-800 lines of markdown for a typical PR. Hard cap: 1500 lines. GitHub truncates very long comments.
- **One finding = one section.** Don't merge two unrelated issues into a single bullet.
- **Quote sparingly.** 3-10 lines per `<details>` block. If the reader needs more, they open the file.
- **Use `<details>` / `<summary>`** for: code quotes longer than 5 lines, long rationale, grep output, command transcripts. Keeps the comment scannable.
- **Use code fences with language tags** (` ```ts `, ` ```py `, ` ```bash `) for syntax highlighting.

### Link format

- ✅ `path/to/file.ts:42` — repo-relative, GitHub renders as plain text but humans can copy-navigate.
- ✅ `[file.ts:42](path/to/file.ts#L42)` — only when posting to a known repo URL where line anchors resolve.
- ❌ `/Users/criszl/...` — leaks local path.
- ❌ `#42` referring to a line number — GitHub will think it's PR #42.

### Copy-paste safety check before posting

Before declaring the review done, verify the rendered output:

- [ ] No `#N` patterns anywhere except inside fenced code blocks
- [ ] No `@username` mentions (unless explicitly requested)
- [ ] No `Fixes/Closes/Resolves #N` keywords
- [ ] No absolute local paths
- [ ] All finding labels follow the chosen scheme consistently (no mixing `#1` with `B1`)
- [ ] Total length under the cap; long quotes are inside `<details>`
- [ ] Renders cleanly in GitHub's markdown preview (no broken tables, unclosed code fences, or stray HTML)

---

## 🔴 CRITICAL: Security Review Mindset (Apply to Every PR)

> **Before running through any checklist item, apply this mindset to the entire PR.**
> The checklist catches known patterns. This mindset catches everything the checklist doesn't.

### The Reviewer's Core Question

For every significant block of code in the PR, ask:

> **"What assumption is the author making here — and is that assumption verified, or just hoped for?"**

Unverified assumptions are where vulnerabilities live. They do not look like bugs. They look like reasonable code.

### The Five Questions to Ask on Every PR

| # | Question | What to look for |
|---|----------|-----------------|
| 1 | **What is this code trusting without verifying?** | Inputs, tokens, signatures, IDs, headers, flags from outside the system |
| 2 | **What is the authoritative source for this behavior?** | Is the implementation based on official docs/SDK, or on assumption/tutorial? |
| 3 | **What happens in every failure path?** | Exceptions swallowed? Failed checks that silently pass? Errors leaking internals? |
| 4 | **Who controls each value, and could they lie?** | Client-sent fields, URL params, headers — all forgeable unless verified server-side |
| 5 | **What is the blast radius if this is wrong?** | Data exposure? Privilege escalation? Forged events? Resource exhaustion? |

### How to Raise a Security Finding

When you find a violation, the comment must include:

1. **What the assumption is** — "This assumes the body is the signed content"
2. **Why it's wrong or unverified** — "Mercado Pago signs a specific constructed string, not the raw body"
3. **What the blast radius is** — "Anyone can forge a payment webhook and credit arbitrary accounts"
4. **What the fix is** — "Read the official Mercado Pago notification docs and implement the `x-signature` verification exactly"

---

## 🔴 CRITICAL: Comprehension Audit (Apply to Every PR)

> **A PR where the author cannot defend every significant block is a PR you must block.**
>
> LLM-assisted development makes it trivial to ship code that compiles, passes tests, and looks clean — but that no human on the team actually understands. That is **comprehension debt**, and it cannot be repaid by future tooling. The reviewer is the last line of defense before this debt enters the codebase.

### What to Verify

For every non-trivial block in the diff:

- [ ] The author can summarize the change in 1-3 sentences in plain language, without scrolling.
- [ ] The author can answer "why this approach over the obvious alternative?" — and the answer is captured durably (in a test name, a `Why:` comment, the PR's `## Design Decisions` section, or an ADR), not just in the author's head.
- [ ] The author can name which test would fail if a given block were removed.
- [ ] The author can articulate the failure mode if the inputs were malformed or the dependency went down.
- [ ] No block in the diff is "the AI wrote it, I trust it." Every line is something the author can defend.

### How to Raise a Comprehension Finding

If a block fails the comprehension audit, the comment should:

1. **Quote the block** (or link to the file:line).
2. **Ask the author to explain** the *why*, not the *what*: "Why this dispatch table instead of the existing strategy pattern in `payment_strategies.py`?"
3. **Block the PR** until either: (a) the author defends the choice and captures the rationale durably, or (b) the author rewrites the block with full understanding.

This is not gatekeeping. This is preventing comprehension debt from being merged into the codebase, where it accumulates invisibly until production breaks at 2 a.m. and nobody knows why.

### Red Flags During Review

| Red flag | What it usually means |
|----------|----------------------|
| Author cannot summarize the diff in 1-3 sentences without scrolling | They do not own the change — they hosted an AI session that produced it |
| Generic test names: `test_create_user_works`, `test_handles_error` | Intent was not encoded — future maintainers cannot reconstruct it |
| Code uses patterns inconsistent with the rest of the codebase, with no explanation | Either a deliberate departure (capture the reason) or an AI-introduced inconsistency (revert) |
| PR description says "AI-generated" with no design rationale | The author skipped the comprehension step — block until they catch up |
| `Why:` comments missing from non-obvious blocks | Architectural intent was not captured — it will be lost the moment the author's memory fades |
| The author argues "the tests pass, what more do you want?" | The tests prove the *what*. The audit is about the *why*. They are different things |

### Anti-Pattern: "Future AI Will Clean It Up"

If you see — or hear — any version of "the naming is confusing but Copilot will figure it out later" / "let's not write the comment, the LLM will infer the intent next time" / "we'll refactor in a follow-up", **block the PR**. LLMs cannot reconstruct intent that was never captured. The comprehension debt compounds; future tooling does not absorb it, it generates new assumptions on top of the unrecovered ones.

---

## 🔴 CRITICAL: Security & PII (Check First)

### PII in Logs - ZERO TOLERANCE

> ⚠️ **This is the #1 priority.** Any PII logging is an immediate rejection.

- [ ] **No email addresses in logs** (`user.email`, `body.email`, `request.email`, any `*email*`)
- [ ] **No user names in logs** (`user.first_name`, `user.last_name`, `user.full_name`, `user.name`)
- [ ] **No phone numbers in logs** (`user.phone`, `user.phone_number`)
- [ ] **No addresses in logs** (`user.address`, `user.location`)
- [ ] **No PII in webhook messages** (Discord, Slack, Teams, etc.)
- [ ] **No `print()` / `console.log()` with user data** (these go to production logs)
- [ ] **No PII in any logging call** (`logger.*()`, `logging.*()`, `log.*()`, `Log.*()`)

**✅ Approved identifiers for logs:**
```
user.auth_id     (primary - always prefer this)
user.user_id     (acceptable)
user.stripe_id   (acceptable for payment context)
user.id          (acceptable if it's an internal ID)
```

**Examples across languages:**

```python
# ❌ VIOLATIONS (Python)
logger.info(f"User {user.email} logged in")
logging.warning(f"Failed for {body.email}")
print(f"Contact sent: {data}")  # if data contains email

# ✅ CORRECT (Python)
logger.info(f"User auth_id={user.auth_id} logged in")
logger.warning("Failed login", extra={"auth_id": user.auth_id})
```

```typescript
// ❌ VIOLATIONS (TypeScript/JavaScript)
console.log(`User ${user.email} logged in`);
logger.warn(`Failed for ${body.email}`);

// ✅ CORRECT (TypeScript/JavaScript)
console.log(`User auth_id=${user.authId} logged in`);
logger.warn('Failed login', { authId: user.authId });
```

```java
// ❌ VIOLATIONS (Java)
logger.info("User {} logged in", user.getEmail());
System.out.println("Contact: " + user.getFullName());

// ✅ CORRECT (Java)
logger.info("User authId={} logged in", user.getAuthId());
```

```go
// ❌ VIOLATIONS (Go)
log.Printf("User %s logged in", user.Email)

// ✅ CORRECT (Go)
log.Printf("User authId=%s logged in", user.AuthID)
```

```csharp
// ❌ VIOLATIONS (C#)
_logger.LogInformation($"User {user.Email} logged in");

// ✅ CORRECT (C#)
_logger.LogInformation("User authId={AuthId} logged in", user.AuthId);
```

---

### General Security

- [ ] All user inputs are sanitized and validated at system boundaries
- [ ] No secrets/credentials in code (use env vars or secret managers)
- [ ] No internal details exposed in error messages to end users
- [ ] External/untrusted data is never trusted without validation
- [ ] SQL queries use parameterized statements (no string concatenation)
- [ ] No hardcoded API keys, tokens, or passwords
- [ ] Sensitive data is not stored in plain text
- [ ] HTTPS/TLS used for all external communication
- [ ] Rate limiting implemented on all public-facing endpoints
- [ ] Passwords stored with strong adaptive hashing (bcrypt, Argon2, scrypt) — never MD5/SHA-1
- [ ] Sensitive data at rest (PII, credentials, payment info) is encrypted

---

## 🔴 CRITICAL: AI / Chatbot / LLM Security (Check When Feature Uses AI)

> ⚠️ **If the feature includes any LLM, chatbot, or AI agent, ALL items below are BLOCKERS.**
> These rules align with OWASP Top 10 for LLM Applications 2025.

- [ ] **AI/chatbot layer has NO direct database access** — all data flows through a service/repository layer that enforces its own access control
- [ ] AI agent has access only to tools explicitly required for its stated purpose
- [ ] Authorization is enforced **in downstream functions** (code), NOT delegated to the AI's own judgment
- [ ] Database user/role used by AI-accessible services has **read-only permissions** unless write access is explicitly justified
- [ ] User input is validated and sanitized **before** being forwarded to the LLM
- [ ] System prompt and user input are separated at the architecture level (not string concatenation)
- [ ] Rate limiting is implemented per user/session
- [ ] Known prompt injection patterns are detected and blocked
- [ ] LLM output is treated as **untrusted** — not rendered as raw HTML without sanitization
- [ ] Output is scanned/filtered before use (SQL fragments, shell commands, PII patterns)
- [ ] If AI-generated code is executed, it runs in a **sandboxed environment** — never `eval()` / `exec()`
- [ ] **No secrets, credentials, or connection strings in the system prompt**
- [ ] System prompt is NOT used as an authorization boundary
- [ ] **Irreversible agentic actions require human confirmation**
- [ ] Every tool call made by the AI agent is audited (logged with parameters and result)
- [ ] Execution time limits and token consumption limits are set on AI agent runs
- [ ] Repeated validation failures from the same source are logged and alerted (>5 failures in 10 minutes = probe attempt)

**Grep to check for naive prompt building:**
```bash
# Unsafe string concatenation with user input and system prompts
grep -rn "systemPrompt\s*+\s*userInput\|prompt.*\+.*req\.\|f\"{system_prompt}.*{user" \
  --include="*.ts" --include="*.py" --include="*.js"
```

---

## 🔴 CRITICAL: Third-Party Integration Security

> ⚠️ **Any PR that integrates with an external service MUST pass ALL checks below.**
> Implementing a generic pattern instead of the provider's exact specification is a security bug.

- [ ] **Reviewer verified the implementation against the provider's official documentation**
- [ ] **Signature/authentication format matches exactly what the provider specifies**
- [ ] **Timestamp validation is implemented** to reject replayed requests
- [ ] **Timing-safe comparison used** for signature comparison — never `===`, `==`, or string comparison
- [ ] **Raw request body is passed to the HMAC function** — not a re-serialized version
- [ ] **Signature is verified BEFORE any payload field is read**
- [ ] **Failed signature verification throws / returns false** — no silent pass on exception
- [ ] **Webhook secret stored in environment variable** — not in code
- [ ] **Integration tested with real payloads** from the provider's sandbox

**Quick grep for integration security smells:**
```bash
# Signature compared with === (timing attack)
grep -rn "signature.*===\|=== .*signature\|hmac.*===\|=== .*hmac" --include="*.ts" --include="*.py" --include="*.js"

# Catching exceptions in verification functions (silent pass)
grep -rn "catch" --include="*.ts" --include="*.py" --include="*.js" -A2 | grep -B1 "return true\|return { valid\|isValid.*true"

# Hardcoded webhook secrets
grep -rn "webhook.*secret\|WEBHOOK_SECRET\|signing.*secret" --include="*.ts" --include="*.py" --include="*.js" | grep -v "process.env\|os.environ\|config\."
```

---

## 🔴 CRITICAL: AI-Generated Code in High-Risk Areas

> ⚠️ **Treat AI-generated code in security-critical paths as untrusted input.**
>
> LLMs are trained on public repositories that contain decades of insecure patterns: hardcoded credentials, naive HMAC comparisons, missing input validation, `eval`-on-user-input. The model cannot distinguish secure patterns from insecure ones by prevalence alone — it produces what it saw most. The vulnerability lives in the **assumption embedded in the code**, not in the syntax, and it survives standard test coverage.

### High-Risk Areas

Apply the extra-scrutiny lens below when AI-generated code appears in:

- Authentication, session, and token handling
- Authorization checks and ownership filters (any "this user can access this resource" decision)
- Payment and financial transaction code
- Webhook signature verification, HMAC, JWT
- Cryptographic operations (signing, hashing, key derivation, encryption)
- Service boundaries and trust boundaries
- AI/LLM input/output guardrails (the guardrails themselves)
- File upload handling, deserialization (pickle, YAML, etc.)
- SQL query construction (verify the ORM is not bypassed by raw fragments)
- Anything touching secrets, credentials, or PII

### Mandatory Checks for AI-Generated Code in High-Risk Areas

When the PR includes AI-generated code in any high-risk area, in addition to the standard security checklist:

- [ ] **Every external API call** the AI generated has been verified against the **provider's official documentation** — not blog posts, not Stack Overflow, not the AI's claim about how the API works.
- [ ] **Every signature/HMAC/JWT verification** has been compared, line by line, against the provider's reference implementation or official SDK.
- [ ] **Every input validation** covers the case set the **spec** requires, not just the cases the AI happened to think of.
- [ ] **Every error path** has been traced manually: does it leak details? Does a failed check silently succeed (e.g., `except: return True`)?
- [ ] **Every assumption** embedded in a comment, default value, or constant has been challenged: is this actually true, or did the AI guess?
- [ ] **No `eval`, `exec`, raw `innerHTML`, `dangerouslySetInnerHTML`, or unsafe deserialization** in the diff — regardless of how innocuous the use case appears.
- [ ] **A senior engineer (not the author, not the AI) has reviewed the critical-path block** with this lens applied.

### What This Lens Does NOT Apply To

Trivial CRUD on non-sensitive data, internal tooling not exposed to users, prototypes behind feature flags not yet enabled in production. The lens is targeted, not universal — applying it to everything devalues it.

### How to Raise an AI-Untrusted-Code Finding

```
[ Finding template ]

Location: <file:line>
Block: <quote or summary>
Concern: This block is in a high-risk path (<auth | payments | signatures | ...>) and was AI-generated. The following assumption needs verification against <official documentation source>:

  Assumption in the code: "<quote or paraphrase>"
  Where to verify: <link to provider docs or reference implementation>
  Risk if assumption is wrong: <data exposure | privilege escalation | forged events | ...>

Required action: Verify against the authoritative source, then either confirm in a `Why:` comment or refactor.
```

---

## 🔴 CRITICAL: AI Runtime Resilience (when feature calls an LLM in production)

> ⚠️ **A call to an LLM is a network call to an unreliable, slow, non-deterministic external service. Treating it as a function call is a production incident waiting to happen.**

If the PR introduces or modifies code that calls an LLM at runtime, ALL items below are blockers. See `DEVELOPMENT_RULE.md → "AI as a Runtime Dependency"` for the full ruleset.

- [ ] **Explicit timeout** on every AI call — never the SDK default.
- [ ] **Circuit breaker** with explicit thresholds (e.g., open after 5 failures in 30s).
- [ ] **Fallback path** is implemented AND has a test that exercises it (kill the LLM endpoint, run the feature, confirm graceful degradation).
- [ ] **Asynchronous by default** unless the latency budget explicitly justifies a sync call.
- [ ] **Idempotency** for state-changing operations (idempotency keys or safe-to-retry semantics).
- [ ] **Cost ceiling** defined: tokens per request, requests per user/day, daily cap, with alerts.
- [ ] **Kill switch** implemented (config flag or feature flag that disables the AI path without a redeploy).
- [ ] **Observability** emits the mandatory fields: `operation`, `request_id`, `model`, `prompt_token_count`, `completion_token_count`, `duration_ms`, `outcome`, `error_class`.
- [ ] **SLO documented** in the PR description (P95 latency, success rate, fallback rate).
- [ ] **No full prompts/completions logged verbatim** — they leak PII and secrets. Redact, sample, or hash.
- [ ] **No retry-forever loops** — bounded retries with exponential backoff and a dead-letter for failures.

**Quick grep for AI runtime smells:**
```bash
# AI calls without explicit timeout
grep -rn "anthropic\|openai\|completion\|chat\.create\|messages\.create" --include="*.py" --include="*.ts" \
  | grep -v "timeout\|deadline"

# Logging full prompts/completions
grep -rn "log.*prompt\|log.*completion\|logger.*messages" --include="*.py" --include="*.ts"

# Sync LLM call inside an HTTP handler / route
grep -rn -B2 "anthropic\|openai" --include="*.py" --include="*.ts" \
  | grep -E "router\.|@app\.|@router|def.*request|async def.*req"
```

---

## 🔴 CRITICAL: DRY Principle

> ⚠️ **Before adding ANY new code, verify it doesn't duplicate existing functionality.**

- [ ] **Types/Models:** No duplicate type definitions (search existing types first)
- [ ] **Classes:** No duplicate class implementations
- [ ] **Functions:** No duplicate logic (5+ lines appearing 2+ times = extract)
- [ ] **Constants:** No duplicate constant definitions
- [ ] **Validation:** No duplicate validation logic
- [ ] **API calls:** No duplicate HTTP client implementations

**Self-check questions:**
1. Did I search the codebase for similar functionality?
2. Is there an existing utility/helper that does this?
3. Can I extend existing code instead of creating new?

---

## 🔴 CRITICAL: File Structure Limits

> ⚠️ **These are HARD LIMITS. Exceeding them = immediate PR rejection.**

### Hard Limits Per File

| Metric | Maximum Allowed | Flexibility |
|--------|-----------------|-------------|
| Lines of code (excluding imports, types, docs) | **500 lines** | Up to 600–700 OK **only if** all other rules (SRP, separation by responsibility, no mixed prefixes) are fully satisfied |
| Functions with DIFFERENT responsibilities | **5 functions** | No flexibility |
| Functions with SAME responsibility (same prefix) | **10 functions** | No flexibility |
| Main classes per file | **1 class** | Small related classes (exceptions, DTOs) OK up to 5 |
| Cyclomatic complexity per function (new code) | **10** | No flexibility — refactor before merging |
| Cyclomatic complexity per function (legacy code being touched) | **15** | Acceptable only if your change does NOT increase the complexity |
| Maximum nesting depth per function | **4 levels** | No flexibility |

> ⚠️ **A 650-line file that passes all SRP and separation checks is acceptable. A 400-line file with mixed responsibilities is NOT.**
> **Equally: a 30-line function with cyclomatic complexity 14 is NOT acceptable. Linear 80-line code is fine; tangled 30-line code is not.**

- [ ] **No file exceeds 500 lines** (600–700 acceptable only if all other structural rules pass)
- [ ] **No file has more than 5 functions with DIFFERENT responsibilities**
- [ ] **No file has more than 10 functions even with same responsibility**
- [ ] **No file has more than 1 main class** (exceptions/DTOs grouped are OK)
- [ ] **No function exceeds cyclomatic complexity 10** (15 for legacy code being touched, only if the change does NOT increase complexity)
- [ ] **No nesting depth exceeds 4 levels** in any function

### Mandatory Separation by Responsibility

Functions MUST be grouped by responsibility category. **Functions with DIFFERENT prefixes MUST NOT coexist in the same file.**

| Responsibility | Function Prefixes | Must Be In Separate File |
|----------------|-------------------|--------------------------|
| **Validation** | `validate*`, `check*`, `is_valid*`, `assert*` | `validation` file |
| **Formatting/Serialization** | `format*`, `build*`, `serialize*`, `to_*` | `formatting` or `serialization` file |
| **Parsing** | `parse*`, `extract*`, `from_*` | `parsing` file |
| **External Communication** | `fetch*`, `send*`, `call*`, `request*` | `client` or `api` file |
| **Data Persistence** | `save*`, `load*`, `find*`, `delete*`, `query*` | `repository` file |

- [ ] **No mixed responsibilities in same file** (e.g., `validate*` AND `format*` = VIOLATION)
- [ ] **All validation functions in dedicated validation file**
- [ ] **All formatting functions in dedicated formatting file**
- [ ] **All data access functions in dedicated repository file**

### Coesion — Avoid Over-Engineering

- [ ] **No files with only 1-2 trivial functions** (< 20 lines total)
- [ ] **Private helpers (`_func`) stay in the file that uses them**
- [ ] **One-liner utilities are not extracted to separate files**

### File Structure Checklist

- [ ] Types/models are in dedicated `*_types` or `*_models` file
- [ ] Constants are in dedicated `*_constants` file
- [ ] Each file can be described in ONE sentence without "and" or "or"
- [ ] No generic file names: `utils`, `helpers`, `misc`, `common`, `shared` (standalone)
- [ ] No `index` files as main logic containers

---

## 🟠 IMPORTANT: SOLID Principles Verification

> Full principle explanations with code examples are in `DEVELOPMENT_RULE.md`.
> Below are the **reviewer verification criteria** — what to look for during review.

### SRP — How to Spot Violations

- [ ] Each file has ONE clear responsibility
- [ ] Each function does ONE thing
- [ ] Each class has ONE reason to change
- [ ] No function names with "and", "or", "then", or vague "process"
- [ ] No monolithic files that "do everything"

**✅ Good names:**
```
validateEmail()      → validates
formatCurrency()     → formats
fetchUserById()      → fetches
parseResponse()      → parses
```

**❌ Bad names (multiple responsibilities):**
```
validateAndFormatUser()    → two responsibilities
processOrder()             → vague, likely multiple
handleEverything()         → obvious violation
doStuff()                  → meaningless
```

### OCP — How to Spot Violations

- [ ] No functions with growing `if/elif/else` or `switch` chains for type/category handling
- [ ] New feature requests should not require modifying existing, tested functions
- [ ] Polymorphism or strategy pattern used where 3+ variants exist and more are expected

**Red flags:**
```
# 🚩 Every new payment type requires touching this function
if type == "credit": ...
elif type == "debit": ...
elif type == "pix": ...        # Added this sprint
elif type == "boleto": ...     # Added last sprint
```

### LSP — How to Spot Violations

- [ ] No subclass throws `NotImplementedError` on an inherited method
- [ ] No subclass silently ignores a method (empty body where parent does work)
- [ ] No subclass narrows accepted inputs compared to parent
- [ ] No subclass adds side effects the parent doesn't have
- [ ] Replacing parent with child in any caller would not break behavior

### ISP — How to Spot Violations

- [ ] No class has methods that are empty or return dummy values just to satisfy an interface
- [ ] No interface has 7+ methods where most implementors use only 2-3
- [ ] A change in one interface method does not force changes in classes that don't use it

**Red flags:**
```
# 🚩 Implementor forced to provide useless methods
class PdfExporter(Exporter):
    def export_to_csv(self): pass       # Doesn't apply
    def export_to_excel(self): pass     # Doesn't apply
    def export_to_pdf(self): ...        # Only relevant method
```

### DIP — How to Spot Violations

- [ ] High-level modules do not directly instantiate low-level modules
- [ ] Constructors receive abstractions (interfaces), not concrete classes
- [ ] Swapping an implementation (e.g., MySQL → PostgreSQL) does not require changing business logic

---

## 🟠 IMPORTANT: Pragmatic Principles Verification

### YAGNI — How to Spot Violations

> *Don't implement anything until it is actually needed.*

- [ ] No code that solves future/imaginary requirements not in the current task
- [ ] No abstract base classes with only one implementation (and no near-term plan for a second)
- [ ] No configuration parameters nobody requested
- [ ] No caching before a performance problem is measured
- [ ] No generic "plugin/event bus" architecture when only one plugin/event exists

**The reviewer's question:** *"Is this code solving a problem that exists RIGHT NOW?"*

### Law of Demeter — How to Spot Violations

> *An object should only talk to its immediate friends.*

- [ ] No call chains deeper than one dot from a direct dependency (`a.b.c.method()`)
- [ ] No function that reaches through an object's internal structure to access nested data
- [ ] Callers ask for what they need, not dig through structures to get it

**Red flags:**
```
# 🚩 Caller knows the internal structure of order → customer → address
order.customer.address.zip_code

# ✅ Encapsulated
order.get_customer_zip()
```

**Grep to detect:**
```bash
# Find chains of 3+ dots (potential Law of Demeter violations)
grep -rn "\w\.\w\+\.\w\+\.\w\+" --include="*.py" --include="*.ts" --include="*.js" \
  | grep -v "import\|require\|from\|test\|spec\|mock\|node_modules"
```

### KISS — How to Spot Violations

- [ ] No factory/strategy/builder pattern where a simple function suffices
- [ ] No generics where a concrete type is clear and stable
- [ ] No unnecessary abstraction layers (class wrapping a single function with no added value)

---

## 🟠 IMPORTANT: Architecture & Layer Separation

### Required Module Structure

```
feature/
├── {feature}_service        # Orchestration only (≤500 lines, ≤5 functions)
├── {feature}_types          # All type definitions
├── {feature}_constants      # All constants and enums
├── helpers/
│   ├── validation           # ONLY validate*, check*, is_valid* functions
│   ├── formatting           # ONLY format*, build*, serialize* functions
│   └── parsing              # ONLY parse*, extract* functions (if needed)
├── services/
│   └── {external}_client    # ONLY fetch*, send*, call* functions
├── repositories/
│   └── {feature}_repository # ONLY save*, load*, find*, query* functions
└── handlers/
    └── {feature}_handler    # ONLY request/event handling
```

### Layer Separation

- [ ] Domain logic is independent from frameworks/infrastructure
- [ ] Clear boundaries between modules and layers
- [ ] No business logic in controllers/handlers/routes
- [ ] No HTTP/DB concerns in service/domain layer
- [ ] No framework imports in pure business logic

**Layer responsibilities:**

| Layer | CAN | CANNOT |
|-------|-----|--------|
| **Handler/Controller** | Receive request, delegate, return response | Contain business logic, call DB directly |
| **Service/Domain** | Business rules, orchestration | Know about HTTP, execute queries directly |
| **Repository** | Execute queries, map data | Make business decisions, call external APIs |
| **Helper** | Transform data, validate, format | Have side effects, do I/O, maintain state |

---

## 🟠 IMPORTANT: Code Quality

### Clean Code

- [ ] **Immutability:** Use `const`, `readonly`, `final`, `val` where possible
- [ ] **Strong typing:** No `any`, `object`, `dynamic`, `Object` loose types
- [ ] **Early returns:** Guard clauses to reduce nesting
- [ ] **No magic values:** Extract numbers/strings to named constants
- [ ] **Dependency injection:** Where appropriate for testability
- [ ] **No global state:** Avoid singletons and global variables

### Naming

- [ ] Names reveal intent (self-documenting)
- [ ] Names are consistent with codebase conventions
- [ ] Boolean variables/functions use `is`, `has`, `can`, `should` prefix
- [ ] Functions use verbs: `get`, `set`, `create`, `update`, `delete`, `validate`
- [ ] No abbreviations unless universally understood (`id`, `url`, `api`)

---

## 🟠 IMPORTANT: Error Handling

- [ ] Expected errors are handled explicitly
- [ ] No silent failures (empty catch blocks)
- [ ] No generic exceptions (`Exception`, `Error`, `object`)
- [ ] Errors include meaningful context
- [ ] Errors are part of the API contract
- [ ] Inputs validated at system boundaries (fail fast)
- [ ] Clear distinction between recoverable errors and fatal exceptions

**Examples:**

```python
# ❌ BAD
try:
    result = do_something()
except:  # Generic, silent
    pass

# ✅ GOOD
try:
    result = do_something()
except ValidationError as e:
    logger.warning("Validation failed", extra={"error": str(e), "auth_id": user.auth_id})
    raise DomainError(f"Invalid input: {e.field}") from e
```

```typescript
// ❌ BAD
try {
  const result = await doSomething();
} catch (e) {
  // Silent failure
}

// ✅ GOOD
try {
  const result = await doSomething();
} catch (error) {
  if (error instanceof ValidationError) {
    logger.warn('Validation failed', { error: error.message, authId: user.authId });
    throw new DomainError(`Invalid input: ${error.field}`);
  }
  throw error;
}
```

---

## 🟡 RECOMMENDED: Observability

### Logging

- [ ] Structured logging at key decision points
- [ ] Appropriate log levels (`debug`, `info`, `warn`, `error`)
- [ ] Logs include: operation name, relevant IDs, outcome, duration (if relevant)
- [ ] **NO sensitive data in logs** (passwords, tokens, PII)
- [ ] No redundant logs duplicating obvious information
- [ ] No logs in no-op/stub implementations

**Good log structure:**

```python
# Python
logger.info("Order created", extra={
    "operation": "create_order",
    "auth_id": user.auth_id,
    "order_id": order.id,
    "duration_ms": elapsed_ms
})
```

```typescript
// TypeScript
logger.info('Order created', {
  operation: 'createOrder',
  authId: user.authId,
  orderId: order.id,
  durationMs: elapsedMs
});
```

---

## 🟡 RECOMMENDED: Comments

- [ ] No comments explaining WHAT (code should be self-explanatory)
- [ ] Comments only explain WHY (non-obvious decisions, trade-offs)
- [ ] No commented-out code (use version control)
- [ ] No TODO comments without ticket references
- [ ] No redundant comments restating the code

---

## 🟢 TESTING

> **Full testing rules are in `TESTING_RULE.md`.** When reviewing tests, apply ALL principles from that document.

### Coverage Requirements

- [ ] Unit tests for all core/business logic
- [ ] Success cases covered
- [ ] Error cases covered
- [ ] Edge cases covered (null, empty, boundary values)
- [ ] Invalid inputs covered

### Test Quality

- [ ] Clear test names: `should_[expected]_when_[condition]`
- [ ] Independent tests (no shared state between tests)
- [ ] Deterministic tests (no flaky tests)
- [ ] External dependencies mocked/faked (DB, APIs, filesystem, time)
- [ ] Tests validate behavior, not implementation details
- [ ] Clear structure: Arrange-Act-Assert or Given-When-Then

### 🔴 Tests MUST Also Challenge the Code — Not Only Confirm It

> **Happy path tests are the foundation — but they are NOT enough by themselves.**

- [ ] **Both** happy path AND adversarial tests exist
- [ ] **Edge cases and boundary values** — null, empty, zero, max values, one past the limit
- [ ] **Invalid and unexpected inputs** — wrong types, malformed data, missing fields
- [ ] **Error states and failure modes** — what happens when things go wrong?
- [ ] **What should NOT happen** — e.g., "should NOT render delete button for read-only users"
- [ ] **Error messages and error types are verified** — not just that "it fails"

**What to ask during review:**
1. "Are there BOTH happy path AND adversarial tests?"
2. "Would these tests catch a regression if someone broke the logic?"
3. "Are there edge cases or failure modes that aren't being tested?"
4. "If I remove a line of business logic, will at least one test fail?"

### Coverage Validation

- [ ] **Coverage was run and output shown** — for ALL created tests (backend AND frontend)
- [ ] **Coverage ≥ 75% minimum** (target 80%) on all tested source code
- [ ] **Coverage report was actually executed**, not just claimed as "looks good"
- [ ] **All created tests pass — zero failures**

---

## 🟢 LEGACY CODE AWARENESS

- [ ] **Do NOT prolong bad patterns** - even if surrounding code is bad, write good code
- [ ] **Do NOT copy-paste from legacy code** without reviewing quality
- [ ] **Flag legacy patterns** you encounter for future cleanup
- [ ] **Isolate new code** from legacy where possible
- [ ] **Document** any necessary interaction with legacy systems

---

## 📋 Pre-Submission Checklist

Before creating your PR, verify:

```
🔴 CRITICAL (Blockers)
[ ] No PII in any logs, prints, or webhook messages
[ ] No secrets/credentials in code
[ ] No duplicate types, classes, or logic (DRY)
[ ] No file exceeds 500 lines (600–700 only if all other rules pass)
[ ] No file has more than 5 functions with DIFFERENT responsibilities
[ ] No file has more than 10 functions even with same responsibility
[ ] No file has more than 1 main class (grouped exceptions/DTOs are OK)
[ ] No mixed responsibility prefixes in same file (validate* AND format* = VIOLATION)
[ ] No function exceeds cyclomatic complexity 10 (15 for legacy untouched-by-this-PR code)
[ ] No nesting depth exceeds 4 levels in any function

🔴 CRITICAL — Comprehension Audit (Blockers)
[ ] I can summarize each significant block in 1-3 sentences without re-reading the diff
[ ] I can answer "why this approach over the obvious alternative?" for every non-obvious choice
[ ] Every non-obvious design decision is captured durably (test name, Why: comment, PR ## Design Decisions, or ADR)
[ ] No "the AI wrote it, I trust it" code in the diff — every line is defensible
[ ] No "future AI will refactor this" assumption baked in anywhere

🔴 CRITICAL — AI-Generated Code in High-Risk Areas (Blockers, when applicable)
[ ] Every external API call verified against the provider's official documentation (not the AI's claim)
[ ] Every signature/HMAC/JWT verification compared line-by-line with the reference implementation
[ ] Every input validation covers what the SPEC requires, not just what the AI thought of
[ ] Every error path traced manually — no silent success on a failed check
[ ] No eval/exec/innerHTML/dangerouslySetInnerHTML/unsafe deserialization
[ ] A senior engineer (not the author, not the AI) reviewed the critical-path block

🔴 CRITICAL — AI/Chatbot Features Only (Blockers)
[ ] External integration follows the provider's official spec exactly
[ ] Signature comparison uses timing-safe function (not ===)
[ ] Timestamp/replay attack protection implemented
[ ] Signature verified BEFORE reading any payload field
[ ] Webhook secret in environment variable, not in code
[ ] AI/chatbot layer has NO direct database access
[ ] AI agent uses only tools/permissions explicitly required for its purpose
[ ] User input is validated and sanitized before reaching the LLM
[ ] System prompt contains NO secrets, credentials, or connection strings
[ ] LLM output is treated as untrusted (sanitized before render, never eval'd)
[ ] Irreversible agentic actions require human confirmation
[ ] DB user used by AI services has minimum required permissions
[ ] Authorization enforced in code (downstream functions), NOT delegated to AI judgment

🔴 CRITICAL — AI Runtime Resilience (Blockers, when feature calls an LLM in production)
[ ] Explicit timeout on every AI call (no SDK defaults)
[ ] Circuit breaker with explicit thresholds
[ ] Fallback path implemented AND tested under failure
[ ] Asynchronous by default unless latency budget explicitly justifies sync
[ ] Idempotency for state-changing operations
[ ] Cost ceiling defined with alerts
[ ] Kill switch implemented (no-redeploy disable)
[ ] Mandatory observability fields emitted (operation, request_id, model, tokens, duration, outcome)
[ ] SLO documented in PR description
[ ] No full prompts/completions logged verbatim

🟠 IMPORTANT (Must fix)
[ ] Each file/function has single responsibility (SRP)
[ ] No growing if/elif chains for type handling (OCP)
[ ] No subclass that breaks parent's contract (LSP)
[ ] No interface forcing useless implementations (ISP)
[ ] High-level modules depend on abstractions, not concretions (DIP)
[ ] No speculative code for future requirements (YAGNI)
[ ] No deep call chains reaching through object internals (Law of Demeter)
[ ] Proper error handling (no silent failures)
[ ] Strong typing (no any/object types)
[ ] Inputs validated at boundaries
[ ] Types in dedicated types file
[ ] Constants in dedicated constants file

🟡 RECOMMENDED (Should fix)
[ ] Appropriate logging at key points
[ ] No unnecessary comments
[ ] No over-engineering (no files with 1-2 trivial functions)

🟢 TESTING (see TESTING_RULE.md)
[ ] Unit tests for core logic
[ ] Tests cover success, error, and edge cases
[ ] Tests have BOTH happy path AND adversarial tests
[ ] Adversarial tests included: edge cases, invalid inputs, boundary values, error states
[ ] If feature calls an LLM: AI runtime failure-mode tests (timeout, malformed output, circuit-open, kill switch)
[ ] Coverage ran and shown — ≥75% minimum (target 80%) for ALL created tests
[ ] All created tests pass — zero failures
[ ] Not prolonging legacy bad patterns
```

---

## 🏆 Perfect Score Criteria

To achieve a **perfect review score**, your code must:

1. ✅ **Zero PII in logs** - Verified by searching for email, name, phone patterns
2. ✅ **Zero security issues** - No hardcoded secrets, proper input validation
3. ✅ **Zero DRY violations** - No duplicate logic, types, or classes
4. ✅ **Zero file structure violations** - ≤500 lines (600–700 only if all other rules pass), ≤5 functions (different responsibilities), ≤10 functions (same responsibility), ≤1 main class per file
5. ✅ **Zero mixed responsibilities** - No different function prefixes in same file
6. ✅ **Zero over-engineering** - No unnecessary file fragmentation
7. ✅ **Zero SOLID violations** - SRP, OCP, LSP, ISP, DIP all verified
8. ✅ **Zero pragmatic principle violations** - YAGNI, KISS, Law of Demeter respected
9. ✅ **Clean architecture** - Proper layer separation
10. ✅ **Proper error handling** - Explicit, meaningful, no silent failures
11. ✅ **Strong typing** - No loose types
12. ✅ **Appropriate tests** - Core logic covered with BOTH happy path AND adversarial tests
13. ✅ **Coverage validated** - Coverage ran and shown, ≥75% (target 80%) for all created tests
14. ✅ **AI security compliant** *(when applicable)* - All AI guardrails verified
15. ✅ **Cyclomatic complexity gate passed** - No function above CC 10 (15 for legacy untouched), nesting ≤ 4
16. ✅ **Comprehension Audit passed** - Author can defend every block; non-obvious decisions captured durably; no "AI wrote it, I trust it"
17. ✅ **AI-untrusted-input lens applied** *(when AI-generated code is in critical paths)* - Every assumption verified against the authoritative source
18. ✅ **AI runtime resilience verified** *(when feature calls an LLM in production)* - Timeout, circuit breaker, fallback (tested), idempotency, cost ceiling, kill switch, observability, SLO

---

---

# 🌐 Platform Agnosticism — Reviewer Checklist

> **Full rules in `PLATFORM_AGNOSTIC_RULE.md`.** Code that "looks portable" routinely is not — the assumptions are subtle. The reviewer is the last line of defense before a POSIX-only assumption ships to a Windows user.

## Read-the-Diff Checklist

For every PR, ask:

- [ ] **Paths**: Is every path constructed via `Path` / `path.join`? Any string concatenation with `/` or `\`?
- [ ] **Encoding**: Does every `open()` / `read_text()` / `readFileSync()` specify encoding?
- [ ] **Shell**: Any `shell=True`? Any string-form subprocess command? Any literal `rm`, `cp`, `mv`, `ls`, `grep`, `cat`?
- [ ] **Interpreter**: Any hardcoded `python3`, `node`, `bash` as the executable? Should it be `sys.executable` / `process.execPath`?
- [ ] **Temp / config dirs**: Any literal `/tmp`, `/var/`, `~/.config`, `C:\`-style path?
- [ ] **Line endings**: Any `text.split("\n")` or hardcoded `"\n".join` written to text files?
- [ ] **External tools**: Any reliance on `git`, `make`, `curl`, etc. without `shutil.which` check or documented dependency?
- [ ] **Time**: Any `datetime.now()` without `timezone.utc`?
- [ ] **CI**: Does the CI configuration cover every supported platform? Was a matrix entry quietly removed?

## Grep Recipes for Common Violations

````bash
# Hardcoded POSIX temp paths
grep -rnE '"/tmp/|"/var/|"~/\.config' --include="*.py" --include="*.ts" --include="*.js" --include="*.go" \
  | grep -v test/ | grep -v node_modules

# String concatenation forming paths
grep -rnE '["\x27][a-zA-Z_./-]+/["\x27]\s*\+' --include="*.py" --include="*.ts" --include="*.js"

# open() without encoding (Python)
grep -rnE 'open\([^)]*\)' --include="*.py" | grep -v "encoding=" | grep -v test_

# subprocess with shell=True
grep -rn "shell=True" --include="*.py"

# Hardcoded shell utilities in subprocess / system calls
grep -rnE '(os\.system|subprocess\.(run|call|Popen))\([^)]*["\x27](rm|cp|mv|ls|grep|cat|chmod) ' --include="*.py"

# Hardcoded interpreter
grep -rnE 'subprocess\.[a-z]+\(\s*\[?\s*["\x27]python3?["\x27]' --include="*.py"

# datetime.now() without UTC
grep -rn "datetime.now()" --include="*.py" | grep -v "timezone.utc" | grep -v test_

# split("\n") on text — likely will miss CRLF
grep -rnE '\.split\(["\x27]\\n["\x27]\)' --include="*.py" --include="*.ts" --include="*.js" | grep -v test_

# Forbidden POSIX-only constructs
grep -rn "os.fork\b\|os.posix_spawn\b" --include="*.py"
````

## Red Flags That Often Hide Portability Bugs

- A new file with `import os` but no `import pathlib`. Suspect string-based path manipulation.
- A test that has `@pytest.mark.skipif(sys.platform == "win32")` without an explanation of the alternative coverage.
- Any helper named `run_command`, `shell_exec`, `exec_bash` — almost certainly hardcoded shell semantics.
- A `try/except OSError: pass` around a filesystem operation — the OS-specific failure mode is being silently swallowed.
- A diff that touches CI configuration alongside production code — verify the matrix wasn't trimmed.
- A `Dockerfile` change without a corresponding `.dockerignore` review.

## When Approving Platform-Specific Code

If the PR introduces genuinely OS-specific code (filesystem watchers, GUI hooks, GPU APIs), verify:

- [ ] The OS-specific code is isolated behind a clear abstraction (Protocol / interface)
- [ ] Runtime selection happens via `sys.platform` / `process.platform` — not import-time
- [ ] Each branch has a test that runs on its target OS in the CI matrix
- [ ] The feature documentation lists the platform-specific implementations

If any of those are missing → request changes.

---

## 🔍 Quick Grep Commands

Run these to catch common issues:

```bash
# Find potential PII in logs (adjust patterns for your codebase)
grep -rn "email" --include="*.py" --include="*.ts" --include="*.js" | grep -E "(log|print|console)"
grep -rn "first_name\|last_name\|full_name" --include="*.py" --include="*.ts" --include="*.js"

# Find any/object types (TypeScript)
grep -rn ": any" --include="*.ts" --include="*.tsx"
grep -rn ": object" --include="*.ts" --include="*.tsx"

# Find empty catch blocks
grep -rn "catch.*{" -A1 --include="*.py" --include="*.ts" --include="*.js" | grep -E "pass|//|{}"

# Find TODO without ticket
grep -rn "TODO" --include="*.py" --include="*.ts" --include="*.js" | grep -v "TODO.*#\|TODO.*TICKET\|TODO.*JIRA"

# Find console.log (should not be in production code)
grep -rn "console.log" --include="*.ts" --include="*.tsx" --include="*.js"

# Find print statements (Python)
grep -rn "print(" --include="*.py"

# Count lines per file (find violations of 500 line limit)
find . -name "*.py" -o -name "*.ts" -o -name "*.js" | xargs wc -l | sort -n | tail -20

# Count functions per file (Python)
for f in $(find . -name "*.py"); do count=$(grep -c "^def \|^    def " "$f" 2>/dev/null); if [ "$count" -gt 5 ]; then echo "$count functions: $f"; fi; done

# Cyclomatic complexity check (Python — radon)
radon cc -s -a -nc .
# (Show all functions ranked C or worse — anything ≥ CC 11 needs refactor)

# Cyclomatic complexity check (TypeScript / JavaScript via ESLint)
# Add to .eslintrc:  "rules": { "complexity": ["error", 10] }
npx eslint . --rule '{"complexity": ["error", 10]}' --no-eslintrc

# Cyclomatic complexity check (Go)
gocyclo -over 10 .

# Find deeply nested blocks (4+ levels of indentation — Python/TS)
grep -rn "                    " --include="*.py" --include="*.ts" --include="*.js" \
  | grep -v "test\|spec\|mock"

# Find Law of Demeter violations (chains of 3+ dots)
grep -rn "\w\.\w\+\.\w\+\.\w\+" --include="*.py" --include="*.ts" --include="*.js" \
  | grep -v "import\|require\|from\|test\|spec\|mock\|node_modules"

# Find potential YAGNI: abstract classes with single implementation
grep -rn "class.*ABC\|abstract class\|interface " --include="*.py" --include="*.ts" -l | while read f; do
  class=$(grep -oP "class\s+\K\w+" "$f" | head -1)
  count=$(grep -rn "$class" --include="*.py" --include="*.ts" | grep -v "import\|#\|//\|test\|spec" | wc -l)
  if [ "$count" -le 2 ]; then echo "Possible YAGNI: $class in $f (only $count references)"; fi
done

# Direct DB access in AI/chat handlers
grep -rn "db\.\|repository\.\|query(" --include="*.ts" --include="*.py" \
  | grep -iE "(chat|llm|ai|bot|agent|prompt)"

# eval/exec on AI output
grep -rn "eval(\|exec(" --include="*.ts" --include="*.py" --include="*.js"

# Raw LLM output rendered without sanitization
grep -rn "innerHTML\|dangerouslySetInnerHTML\|render.*llm\|render.*ai" \
  --include="*.tsx" --include="*.jsx" --include="*.html"

# Secrets in system prompts
grep -rn "system_prompt\|SYSTEM_PROMPT" --include="*.ts" --include="*.py" \
  | grep -iE "(password|secret|key|token|conn|database)"
```

---

## 📝 Framework-Specific Guidelines

### React / Frontend

```
featureName/
├── feature-name.tsx              # Orchestrates the feature (NOT index.tsx)
├── feature-name.types.ts         # Types for this context only
├── feature-name.constants.ts     # Constants for this context only
├── hooks/                        # One responsibility per hook
│   ├── use-feature-data.ts       # Responsibility: fetch/manage data
│   └── use-feature-actions.ts    # Responsibility: handle user actions
├── helpers/                      # Pure functions (no React dependencies)
│   ├── validation.ts             # ONLY validate* functions
│   └── formatting.ts             # ONLY format* functions
└── components/                   # Presentational sub-components
    ├── feature-header.tsx
    └── feature-list-item.tsx
```

**Anti-patterns to avoid:**
- ❌ `index.tsx` as main component file
- ❌ Component that fetches, transforms, validates, AND renders
- ❌ Business logic inside render
- ❌ Giant `useEffect` doing multiple things
- ❌ `validate*` and `format*` functions in same file

---

### Python / Backend

```
feature/
├── feature_service.py            # Orchestrates domain logic (≤500 lines)
├── feature_types.py              # Domain models (Pydantic, dataclasses)
├── feature_constants.py          # Domain constants
├── helpers/
│   ├── validation.py             # ONLY validate*, check*, is_valid* functions
│   └── formatting.py             # ONLY format*, build*, serialize* functions
├── repositories/
│   └── feature_repository.py     # ONLY save*, load*, find*, query* functions
└── handlers/
    └── feature_handler.py        # ONLY request handling
```

---

### NestJS / Node Backend

```
feature/
├── feature.module.ts             # Wires dependencies
├── feature.controller.ts         # HTTP layer (≤500 lines)
├── feature.service.ts            # Domain logic (≤500 lines)
├── feature.types.ts              # DTOs, domain interfaces
├── feature.constants.ts          # Domain constants
├── helpers/
│   ├── validation.helper.ts      # ONLY validate* functions
│   └── formatting.helper.ts      # ONLY format*, build* functions
└── repositories/
    └── feature.repository.ts     # ONLY data access functions
```

---

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# !!!                    DO NOT COMMIT                          !!!
# !!!                                                           !!!
# !!! This file is a local development guide only.              !!!
# !!! It must NEVER be committed to the repository.             !!!
# !!! Do NOT include it in any commit, branch, or pull request. !!!
# !!!                                                           !!!
# !!! AI agents (Claude, Copilot, etc.) must NEVER run          !!!
# !!! git commit, git add, or git push on ANY file.             !!!
# !!! Only the human developer may commit and push changes.     !!!
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
