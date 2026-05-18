---
name: frontend-code-review
description: "Review frontend code (.tsx, .ts, .js files) for quality, performance, and correctness against Langflow's frontend conventions. Supports pending-change reviews and file-targeted reviews."
---

# Frontend Code Review

## When to use this skill

Use this skill whenever the user asks to **review, analyze, or improve** frontend code (`.tsx`, `.ts`, `.js` files) under the `src/frontend/` directory. Supports the following review modes:

1. **Pending-change review** -- inspect staged or working-tree files slated for commit and flag checklist violations before submission.
2. **File-targeted review** -- review the specific file(s) the user names and report the relevant checklist findings.

Do NOT use this skill when:

- The request is about backend code (`.py` files under `src/backend/`).
- The user is not asking for a review/analysis/improvement of frontend code.
- The scope is outside `src/frontend/` (unless the user explicitly asks to review frontend-related changes elsewhere).

## How to use this skill

Follow these steps when using this skill:

1. **Identify the review mode** (pending-change vs file-targeted) based on the user's input. Keep the scope tight: review only what the user provided or explicitly referenced.
2. Follow the rules defined in the **Checklist** to perform the review. If no checklist rule matches, apply **General Review Rules** as a fallback.
3. Compose the final output strictly following the **Required Output Format**.

Notes when using this skill:

- Always include actionable fixes or suggestions (including possible code snippets).
- Use `File:Line` references when a file path and line numbers are available; otherwise, use the most specific identifier you can.
- The Langflow frontend uses React 19, TypeScript 5.4, Vite 7 with SWC, Zustand for state management, TanStack React Query for server state, @xyflow/react v12 for graph visualization, Radix UI + shadcn-ui components, Tailwind CSS v3, and Biome for linting/formatting.

## Checklist

- **Code quality**: For any reviewed file, follow [references/code-quality.md](references/code-quality.md) to check styling conventions, TypeScript usage, Biome compliance, and component patterns.
- **Performance**: If the review scope involves React components, hooks, Zustand stores, React Query usage, or @xyflow/react node rendering, follow [references/performance.md](references/performance.md) to check for re-render issues, memoization, and data flow patterns.
- **Business logic**: If the review scope involves custom nodes (GenericNode), flow state, API calls, the component system, global variables, or the inspection panel, follow [references/business-logic.md](references/business-logic.md) to check for Langflow-specific correctness.

## General Review Rules

### 1. Security Review

Check for:
- XSS vulnerabilities (dangerouslySetInnerHTML, unescaped user input)
- Sensitive data exposure in client-side code
- Insecure direct object references in API calls
- Hardcoded secrets, tokens, or API keys

### 2. Accessibility Review

Check for:
- Missing aria labels on interactive elements
- Keyboard navigation support
- Proper use of semantic HTML elements
- Color contrast issues in custom styling

### 3. Code Quality Review

Check for:
- Code duplication (DRY violations — extract at 3+ identical usages)
- Functions/components doing too much (SRP violations — if you need "and" to describe it, split it)
- Deep nesting or complex conditionals (prefer early returns and guard clauses)
- Magic numbers/strings without named constants
- Poor naming: generic names (`data`, `result`, `temp`), missing verb prefixes on functions, missing `is`/`has`/`can`/`should` prefixes on booleans
- Missing error handling or error boundaries
- Incomplete TypeScript type coverage (no `any`, no `as any` casts)
- Comments that explain WHAT instead of WHY
- Commented-out code (use version control)
- Boolean parameters that switch component behavior (use two components instead)
- Mutable patterns where `const` or immutable alternatives exist
- Production files exceeding ~500 lines (red flag at 600+)
- `console.log` in production code (Biome flags this)

### 4. Testing Impact Review

Check for:
- Changes to data-testid attributes that may break E2E tests
- Modified component interfaces that require test updates
- New interactive elements missing data-testid attributes

### 5. Pre-Commit Verification

For pending-change reviews, verify:
- `npm run format` (Biome formatter) — zero diffs
- `npm run lint` (Biome linter) — zero errors
- `npm test` (Jest) — zero failures

## Required Output Format

When this skill is invoked, the response must exactly follow one of the two templates:

### Template A (any findings)

```markdown
# Code Review

Found <N> urgent issues that need to be fixed:

## 1. <brief description of issue>

FilePath: <path> line <line>
<relevant code snippet or pointer>


### Suggested fix

<brief description of suggested fix with code example>

---

... (repeat for each urgent issue) ...

Found <M> suggestions for improvement:

## 1. <brief description of suggestion>

FilePath: <path> line <line>
<relevant code snippet or pointer>


### Suggested fix

<brief description of suggested fix with code example>

---

... (repeat for each suggestion) ...
```

- If there are no urgent issues, omit that section. If there are no suggestions, omit that section.
- If the issue count exceeds 10, summarize as "10+ urgent issues" or "10+ suggestions" and output only the first 10 items.
- Do not compress the blank lines between sections; keep them as-is for readability.
- If Template A is used (there are issues to fix) and at least one issue requires code changes, append a brief follow-up question after the structured output asking whether the user wants the suggested fixes applied. For example: "Would you like me to apply the suggested fixes to address these issues?"

### Template B (no issues)

```markdown
## Code Review

No issues found.
```
