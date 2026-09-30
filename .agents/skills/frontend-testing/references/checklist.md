# Test Generation Checklist

Verify each item before submitting test code for Langflow frontend.

## Pre-Writing

- [ ] Read the source file completely before writing any tests
- [ ] Identify all exported functions, components, hooks, and types
- [ ] Identify all conditional branches (if/else, ternary, switch, early returns, `&&`/`||` short-circuits)
- [ ] Identify all dependencies that need mocking
- [ ] Check `jest.setup.js` for pre-existing global mocks to avoid duplication
- [ ] Check if there is an existing test file to extend (rather than creating a new one)

## File Structure

- [ ] File is in `__tests__/` directory or co-located with source
- [ ] File name follows `ComponentName.test.tsx` or `util-name.test.ts` convention
- [ ] Imports use `@/` path alias consistently
- [ ] `jest.mock()` calls are at the top of the file, after imports
- [ ] `beforeEach` includes `jest.clearAllMocks()`
- [ ] `beforeEach` resets Zustand store state (if using stores)
- [ ] `afterEach` cleans up fake timers (if used)

## Test Quality

- [ ] Each `it()` block tests exactly ONE behavior
- [ ] Test names follow `"should [behavior] when [condition]"` format
- [ ] Tests are ordered from simplest to most complex
- [ ] Tests use Arrange-Act-Assert (AAA) pattern with blank line separation
- [ ] No implementation details tested (no internal state, no CSS classes, no private functions)
- [ ] No test depends on another test's side effects (test isolation)

## Queries and Assertions

- [ ] Queries follow RTL priority: `getByRole` > `getByLabelText` > `getByText` > `getByTestId`
- [ ] `queryBy*` used for asserting absence (`expect(queryByText("x")).not.toBeInTheDocument()`)
- [ ] `findBy*` or `waitFor` used for async elements
- [ ] `screen` object used for all queries (not destructured from `render`)
- [ ] Assertions use `jest-dom` matchers: `toBeInTheDocument()`, `toHaveValue()`, `toBeDisabled()`, etc.
- [ ] No use of `.innerHTML`, `.className`, or `.style` for assertions

## User Interactions

- [ ] `userEvent.setup()` used (not `fireEvent`)
- [ ] All `userEvent` calls are `await`ed
- [ ] `userEvent.setup({ advanceTimers: jest.advanceTimersByTime })` used when combining with fake timers

## Mocking

- [ ] Uses `jest.fn()`, `jest.mock()`, `jest.spyOn()` (NEVER `vi.*`)
- [ ] Only mocks what is necessary (prefer real implementations)
- [ ] Does NOT mock base UI components from `@/components/ui/`
- [ ] Does NOT re-mock modules already mocked in `jest.setup.js`
- [ ] Mock return values match the actual API shape (type-safe)
- [ ] `jest.mocked()` used for type-safe mock assertions

## Async

- [ ] All `waitFor` calls contain a single assertion
- [ ] All promises are properly `await`ed
- [ ] `act()` wraps state-updating operations (store updates, timer advances)
- [ ] Fake timers cleaned up in `afterEach`: `jest.runOnlyPendingTimers()` then `jest.useRealTimers()`
- [ ] No unhandled promise rejections

## Challenge Tests (MANDATORY — not just happy paths)

- [ ] Happy path tests exist (baseline — code works under normal conditions)
- [ ] **Unexpected inputs tested**: `null`, `undefined`, `""`, `[]`, `{}`, `0`, `-1`
- [ ] **Boundary values tested**: max length, exactly at limit, one past limit, zero items, max items
- [ ] **Malformed data tested**: missing fields, extra fields, wrong types
- [ ] **Error states tested**: API 500, 404, 401, network failure, timeout
- [ ] **What should NOT happen tested**: forbidden actions are rejected, wrong user can't access resources
- [ ] **Error messages verified**: not just that it fails, but HOW it fails (correct message, correct type)
- [ ] Tests written based on **requirements/spec**, not copied from source code logic

## Coverage

- [ ] All exported functions/components are tested
- [ ] All conditional branches are covered (both sides of if/else, all catch blocks)
- [ ] Function coverage: 100%
- [ ] Branch coverage: > 95%
- [ ] Line coverage: > 95%

## Execution

- [ ] Test file runs without errors: `npm test -- path/to/file.test.tsx`
- [ ] No console warnings or errors in test output (or they are intentionally suppressed)
- [ ] Tests pass in isolation (can run the file alone)
- [ ] Tests pass with the full suite (no cross-file contamination)
- [ ] Coverage verified: `npm test -- --coverage --collectCoverageFrom='src/path/to/source.ts' path/to/test.test.ts`

## Final Review

- [ ] No `console.log` left in test code
- [ ] No `.only` or `.skip` left on tests
- [ ] No hardcoded timeouts longer than 5000ms
- [ ] No `any` type assertions that could be properly typed
- [ ] Test file is not in `testPathIgnorePatterns` (not named `test-utils.tsx`)
