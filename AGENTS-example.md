# Langflow Development Guide (Example)

> **This is an EXAMPLE file.** Use at your own risk.
> It is provided as a reference template for development standards and coding conventions.
> Adapt it to your project's needs before adopting. No guarantees are made about its completeness or suitability for any specific use case.

> Language-agnostic. Framework-agnostic.

---

## Table of Contents

1. [Core Philosophy](#1-core-philosophy)
2. [Design Principles](#2-design-principles)
3. [Code Quality](#3-code-quality)
4. [Architecture](#4-architecture)
5. [File Structure](#5-file-structure)
6. [Error Handling](#6-error-handling)
7. [Security](#7-security)
8. [Observability](#8-observability)
9. [Testing](#9-testing)
10. [Code Review](#10-code-review)
11. [Documentation](#11-documentation)
12. [Pre-Delivery Checklist](#12-pre-delivery-checklist)

---

## 1. Core Philosophy

### Trade-off Priority (when conflicts arise)

1. **Correctness** — Code does what it should
2. **Simplicity and readability** — Code is easy to understand
3. **Testability** — Code is easy to test
4. **Performance** — Code is fast enough
5. **Abstraction and reuse** — Code is DRY

### Ground Rules

- Read and understand existing code before modifying it.
- Follow the project's existing patterns and conventions.
- If a requirement is ambiguous, ask before writing code.
- Prefer incremental delivery: core logic first, then edge cases, then refinements.
- Do not overengineer. Build for today's requirements, not hypothetical future ones.

---

## 2. Design Principles

### SOLID

| Principle | Rule | Common Mistake |
|-----------|------|----------------|
| **SRP** — Single Responsibility | Each class/function/file has ONE reason to change. If you need "and" or "or" to describe it, split it. | Interpreting SRP as "one function per class." SRP means one *axis of change*. |
| **OCP** — Open/Closed | Add new behavior by writing new code, not modifying existing code. Use polymorphism or strategy patterns where change is expected. | Over-engineering with premature abstractions. Apply OCP where you have *evidence* of changing requirements. |
| **LSP** — Liskov Substitution | Subclasses must honor the contract of their parent. Prefer composition over inheritance when "is-a" is not strict. | Overriding a method to throw `NotImplementedError` or do nothing. |
| **ISP** — Interface Segregation | Define small, role-specific interfaces. Clients depend only on methods they use. | Creating one "service" interface with 15+ methods. |
| **DIP** — Dependency Inversion | Depend on abstractions at module boundaries, not concrete implementations. Domain logic must never import from infrastructure. | Confusing DIP with "just use dependency injection." DIP is about inverting the *direction of source-code dependency*. |

### DRY — Don't Repeat Yourself

- Extract shared logic when the *exact same business rule* is duplicated in 3+ places (Rule of Three).
- Single source of truth for configuration, constants, and schema definitions.
- **Prefer duplication over wrong abstraction.** Two pieces of code that look similar but serve different business purposes are NOT duplication — merging them creates accidental coupling.
- "Wrong abstraction" means: premature generalization, unclear purpose, or coupling unrelated concerns.

### KISS — Keep It Simple

- Choose the simplest implementation that satisfies current requirements.
- Prefer standard library solutions over custom implementations.
- A plain function call beats metaprogramming. A dictionary beats a class when all you need is data grouping.
- Do not add design patterns, abstractions, or frameworks "just in case."

### YAGNI — You Aren't Gonna Need It

- Implement features only when there is a concrete, current requirement.
- Do not build generic/extensible frameworks before you have at least two concrete use cases.
- Delete speculative code and unused feature flags regularly.
- Three similar lines of code is better than a premature abstraction.

---

## 3. Code Quality

### Naming

- Use clear, meaningful, intention-revealing names. The name should answer *why* it exists and *what* it does.
- Functions use verbs: `get`, `create`, `update`, `delete`, `validate`, `format`, `parse`.
- Booleans use prefixes: `is`, `has`, `can`, `should`.
- No abbreviations unless universally understood (`id`, `url`, `api`).
- No generic names: `data`, `result`, `obj`, `thing`, `temp`, `misc`, `utils`.
- No names with "and", "or", "then" — that signals multiple responsibilities.

### Strong Typing

- Use strong typing everywhere. Avoid `any`, `object`, `dynamic`, `Object`.
- Use typed parameters and return types for all public functions.
- Never cast to `any` just to make something compile.

### Immutability

- Default to immutable. Use `const`, `readonly`, `final`, `frozen`, `tuple`, `frozenset`.
- Return new objects from transformation functions instead of mutating inputs.
- Never expose mutable internal collections. Return copies or read-only views.
- Mutable local variables inside a function are fine — mutable *shared state* is the danger.

### Early Returns and Guard Clauses

- Validate preconditions at the top of functions and return/throw early.
- Reduce nesting by inverting conditions and returning early.
- Keep the "happy path" at the lowest indentation level.

### No Magic Values

- Extract repeated numbers and strings to named constants.
- Use descriptive variable names instead of inline literals.

### Comments

- Do not comment obvious code. Prefer self-explanatory code through good naming.
- Comments explain **WHY**, never **WHAT**.
- No commented-out code — use version control.
- No TODO comments without ticket references.

### Functions

- Keep functions short with a single level of abstraction.
- One function does one thing. If it does two things, split it.
- Do not use boolean parameters that switch behavior — split into two named functions.
- Eliminate dead code and unused imports on every change.

---

## 4. Architecture

### Separation of Concerns

- Separate domain, application, and infrastructure concerns.
- Domain/business logic must have zero imports from frameworks, databases, or HTTP layers.
- Keep side effects (I/O, logging, metrics) at the edges. Business logic should be pure.
- Use DTOs or value objects at layer boundaries — never pass ORM models or HTTP request objects into business logic.

### Layer Rules

| Layer | CAN | CANNOT |
|-------|-----|--------|
| **Handler/Controller** | Receive input, delegate to service, return output | Contain business logic, call DB directly |
| **Service/Orchestrator** | Coordinate operations, apply business rules | Know about HTTP/transport, execute SQL directly |
| **Repository/Data Access** | Execute queries, map data | Make business decisions, call external APIs |
| **Helper** | Transform data, validate, format | Have side effects, do I/O, maintain state |
| **External Client** | Communicate with external services | Contain business logic, access database |

### Dependency Injection

- Inject dependencies through constructors or method parameters. Make all dependencies explicit.
- Inject I/O boundaries (database, HTTP clients, filesystem, clock) so they are swappable in tests.
- Keep the composition root at the application entry point, separate from business logic.
- If a class needs more than ~4 injected dependencies, it is doing too much — split it.
- Only inject things that have *side effects* or *vary between environments*. Do not inject pure utility functions.

### DDD (When Justified)

- Apply DDD concepts only if the domain complexity clearly justifies it.
- Keep domain logic independent from frameworks and infrastructure.
- Use Entities, Value Objects, and Aggregates only when they add real value.
- Model errors and invariants as part of the domain.

---

## 5. File Structure

### Limits Per File (Production Code)

| Metric | Guideline |
|--------|-----------|
| Lines of code (excluding imports, types, docs) | **~500 lines** (up to ~530 OK; 600+ is a red flag) |
| Functions with DIFFERENT responsibilities | **5 functions max** |
| Functions with SAME responsibility (same prefix) | **10 functions max** |
| Main classes per file | **1 class** |
| Small related classes (exceptions, DTOs, enums) | **5 classes** (if all same type) |

### Single Responsibility Per File

Every file MUST have **one reason to exist** and **one reason to change**.

**The Test:** Can you describe this file's purpose in ONE sentence WITHOUT using "and" or "or"?

### Separation by Responsibility

Functions MUST be grouped by responsibility category. **Functions with DIFFERENT prefixes MUST NOT coexist in the same file.**

| Responsibility | Function Prefixes | Separate File |
|----------------|-------------------|---------------|
| **Types/Models** | Type definitions, interfaces, classes without logic | `{feature}_types` |
| **Constants** | `MAX_*`, `DEFAULT_*`, enums | `{feature}_constants` |
| **Validation** | `validate*`, `check*`, `is_valid*` | `validation` |
| **Formatting** | `format*`, `build*`, `serialize*`, `to_*` | `formatting` |
| **Parsing** | `parse*`, `extract*`, `from_*` | `parsing` |
| **External calls** | `fetch*`, `send*`, `call*`, `request*` | `{service}_client` |
| **Data access** | `save*`, `load*`, `find*`, `delete*`, `query*` | `{feature}_repository` |
| **Orchestration** | Main entry points, coordination | `{feature}_service` |
| **Handlers** | Endpoints, controllers, views | `{feature}_handler` |

### Avoid Over-Engineering

- Do NOT create a separate file for 1-2 trivial functions with less than 20 lines total.
- Private helpers (`_func`) stay in the file that uses them.
- One-liner utilities are not extracted to separate files.
- Split when you have clear, reusable responsibilities. Keep together when separation adds complexity without benefit.

### File Naming

- **NEVER** use generic names: `utils`, `helpers`, `misc`, `common`, `shared` as standalone files.
- Follow the project's existing naming convention.

### Module Structure

```
feature/
├── {feature}_service          # Orchestration
├── {feature}_types            # Type definitions
├── {feature}_constants        # Constants and enums
├── helpers/
│   ├── validation             # ONLY validation functions
│   ├── formatting             # ONLY formatting functions
│   └── parsing                # ONLY parsing functions
├── services/
│   └── {external}_client      # ONLY external API communication
├── repositories/
│   └── {feature}_repository   # ONLY data persistence
└── handlers/
    └── {feature}_handler      # ONLY request handling
```

---

## 6. Error Handling

- Handle expected errors explicitly. No silent failures.
- Do not use generic exceptions (`Exception`, `Error`, `object`). Use domain-relevant error types.
- Return or throw errors with meaningful context (what failed, what input caused it, how to fix it).
- Errors are part of the API contract.
- Validate inputs at system boundaries. Fail fast on invalid data.
- Distinguish between recoverable errors and fatal exceptions.
- Never silently coerce or fix invalid input — reject with a clear message.

```python
# BAD
try:
    result = do_something()
except:
    pass

# GOOD
try:
    result = do_something()
except ValidationError as e:
    logger.warning("Validation failed", extra={"error": str(e), "field": e.field})
    raise DomainError(f"Invalid input: {e.field}") from e
```

---

## 7. Security

- Sanitize and validate all user and external inputs at the boundary.
- Never trust data from outside the system boundary.
- Use allowlists, not denylists. Reject by default, accept only known-good patterns.
- Use schema validation libraries (Pydantic, zod, JSON Schema) — do not hand-roll validation for complex structures.
- Keep secrets out of code. Use environment variables or secret managers.
- No hardcoded API keys, tokens, or passwords.
- SQL queries use parameterized statements — no string concatenation.
- Do not expose internal details in error messages to end users.
- Validate on the server side always — client-side validation is a UX convenience, not a security measure.
- Use fake/anonymized data in tests — never real user data.

---

## 8. Observability

### Logging

- Use structured logging (key-value / JSON), not formatted strings.
- Log at key decision points and boundaries, not inside tight loops.
- Include: operation name, relevant IDs, outcome (success/failure), duration if relevant.
- Use consistent field names across the entire codebase.

### Log Levels

| Level | When to Use |
|-------|-------------|
| **ERROR** | Something is broken and needs human attention |
| **WARN** | Degraded but self-recoverable |
| **INFO** | Significant business events |
| **DEBUG** | Diagnostic detail, off in production |

### PII in Logs — ZERO TOLERANCE

- **NEVER** log: email addresses, user names, phone numbers, physical addresses, tokens, passwords.
- **Approved identifiers**: `auth_id`, `user_id`, `internal_id`.
- No `print()` / `console.log()` with user data — these go to production logs.

---

## 9. Testing

> **Test code is production code.** It receives the same care, review, and quality standards.

### Core Principles

- Write unit tests for all core logic.
- Follow Arrange-Act-Assert (AAA) structure. ONE act per test, ONE logical assertion per test.
- Tests MUST be independent, deterministic, and not depend on execution order.
- Mock or fake all external dependencies (DB, APIs, filesystem, time, randomness).
- Name tests clearly: `should_[expected]_when_[condition]`.

### Tests MUST Also Challenge the Code — Not Only Confirm It

**Happy path tests are the foundation** — they validate the code works under normal conditions. Always start with these.

**But happy path tests ALONE are not enough.** You MUST also write adversarial tests that actively try to break the code and find defects:

- Unexpected input types: `None`, `""`, `[]`, `{}`, `0`, `-1`
- Boundary values: max int, max length, exactly at the limit, one past the limit
- Malformed data: missing fields, extra fields, wrong types, invalid formats
- Error states: what happens when dependencies fail?
- What should NOT happen: verify that forbidden states are correctly rejected
- Error messages and types: not just that it fails, but *how* it fails

**Write tests based on REQUIREMENTS/SPEC, not on what the source code currently does.** This is how you catch bugs where the code diverges from expected behavior.

**When a test fails:** first ask if the CODE is wrong, not the test. Do NOT silently change a failing assertion to match the current code without understanding WHY.

### Test File Rules

| Metric | Guideline |
|--------|-----------|
| Lines per file | **~1000 lines** guideline — above this, consider splitting, but not required if covering a single module |
| Tests per file | No hard limit — split only when covering **unrelated behaviors** |
| Setup (Arrange) | **~20 lines max** per test (extract to helpers/factories if exceeded) |

**Split test files based on LOGICAL SEPARATION, not arbitrary line counts.** One file per module/service is perfectly fine, even at 800+ lines.

### Coverage

- **Target: 80%. Minimum acceptable: 75%.** Below 75% the task is not complete.
- Focus on **branch coverage** (both sides of `if/else`, all `catch` blocks), not just line coverage.
- High coverage with no assertions is worthless. Every test MUST have at least one meaningful assertion.
- Coverage must be **run and shown** at the end for ALL created tests (backend AND frontend).

```bash
# Python
pytest tests/your_tests.py --cov=src/module_under_test --cov-report=term-missing --cov-branch -v

# JavaScript/TypeScript (Jest)
npx jest tests/your_tests.test.ts --coverage --collectCoverageFrom="src/module/**/*.{ts,tsx}"

# JavaScript/TypeScript (Vitest)
npx vitest run tests/your_tests.test.ts --coverage
```

### All Created Tests MUST Pass

- Every test you create or modify MUST pass. Zero failures. Zero exceptions.
- Never disable, skip, or delete a test to hide a failure.
- Never leave a test "to fix later" — fix it NOW.
- If coverage is below 75%: write more tests, re-run, repeat until the minimum is met.

### What NOT to Test

- Simple getters, setters, trivial mappers — not worth testing.
- Implementation details (method call order, internal state) — test behavior instead.
- Do not inflate coverage with meaningless assertions.

### Anti-Patterns (Forbidden)

| Pattern | Problem |
|---------|---------|
| **The Liar** | Test passes but doesn't verify the behavior it claims to test |
| **The Mirror** | Test reads the source code and asserts exactly what the code does — finds zero bugs |
| **The Giant** | 50+ lines of setup, multiple acts, dozens of assertions — should be 5+ separate tests |
| **The Mockery** | So many mocks that the test only tests the mock setup |
| **The Inspector** | Coupled to implementation details, breaks on any refactor |
| **The Chain Gang** | Tests depend on execution order or share mutable state |
| **The Flaky** | Sometimes passes, sometimes fails with no code changes |

---

## 10. Code Review

### Priority (blockers first)

1. **Security & PII** — No PII in logs, no hardcoded secrets, input validation
2. **DRY** — No duplicate types, classes, functions, or logic
3. **File Structure** — Limits respected, responsibilities separated
4. **Architecture** — Single responsibility, proper layer separation
5. **Code Quality** — SOLID, strong typing, error handling
6. **Testing** — Both happy path AND adversarial tests, coverage met
7. **Observability** — Structured logging, no PII

### Review Questions for Tests

1. "Are there BOTH happy path AND adversarial tests?"
2. "Would these tests catch a regression if someone broke the logic?"
3. "Are there edge cases or failure modes that aren't being tested?"
4. "If I remove a line of business logic, will at least one test fail?"

### Legacy Code

- Do NOT prolong bad patterns — even if surrounding code is bad, write good code.
- Do NOT copy-paste from legacy code without reviewing quality.
- Isolate new code from legacy where possible.

---

## 11. Documentation

### When to Document

- Generate feature documentation after implementation is complete.
- Documentation lives alongside code in the repository (Markdown).
- Use ubiquitous language — same terms in docs, code, and communication.

### Documentation Levels (C4 Model)

| Level | Audience | Content |
|-------|----------|---------|
| **Context (L1)** | Product / Stakeholders | System in its environment |
| **Container (L2)** | Both | Applications, databases, queues |
| **Component (L3)** | Engineering | Internal service details |

### Required Sections for Feature Docs

1. **Overview** — Summary, business context, bounded context
2. **Ubiquitous Language Glossary** — Domain terms with code references
3. **Domain Model** — Aggregates, entities, value objects, events
4. **Behavior Specifications** — Gherkin scenarios (happy path, edge cases, errors)
5. **Architecture Decision Records** — Context, decision, consequences
6. **Technical Specification** — Dependencies, API contracts, error codes
7. **Observability** — Metrics, logs, dashboards
8. **Deployment & Rollback** — Feature flags, migrations, rollback plan

---

## 12. Pre-Delivery Checklist

**BEFORE delivering ANY code, verify ALL items.**

### Critical (Blockers)

- [ ] No PII in any logs, prints, or webhook messages
- [ ] No secrets or credentials in code
- [ ] No duplicate types, classes, or logic (DRY)
- [ ] No file exceeds ~500 lines (production code) or ~1000 lines (test code)
- [ ] No mixed responsibility prefixes in same file
- [ ] All user inputs validated at system boundaries

### Important (Must Fix)

- [ ] Each file/function has single responsibility
- [ ] Proper error handling (no silent failures, meaningful errors)
- [ ] Strong typing (no `any`, `object`, `dynamic`)
- [ ] Types in dedicated types file, constants in dedicated constants file
- [ ] Domain logic independent from frameworks/infrastructure

### Testing (Mandatory)

- [ ] Unit tests for all core logic
- [ ] Both happy path AND adversarial tests exist
- [ ] All created/modified tests pass — zero failures
- [ ] Coverage report ran and output shown (backend AND frontend)
- [ ] Coverage >= 75% minimum (target 80%)
- [ ] No test anti-patterns (Liar, Mirror, Giant, Mockery, Inspector)

### Quality (Should Fix)

- [ ] Structured logging at key decision points
- [ ] Comments explain WHY, not WHAT
- [ ] No over-engineering (no files with 1-2 trivial functions)
- [ ] No legacy bad patterns prolonged

### Pre-Commit

- [ ] Linter ran on all changed files — zero errors
- [ ] Formatter ran on all changed files — zero diffs
- [ ] Type checker ran (if applicable) — zero errors

---

> **This guide applies to every line of code in the Langflow project.**
> **When in doubt, choose simplicity. When trade-offs arise, follow the priority order in Section 1.**
> **Build for correctness first. Optimize later. Test always.**
