# Frontend Testing Skill - Langflow

## When to Apply

Activate this skill when:
- Writing new unit or integration tests for React components, hooks, utilities, or Zustand stores
- Reviewing existing tests for correctness, coverage, or best practices
- Improving test coverage for under-tested modules
- Debugging flaky or failing tests
- Refactoring test code for maintainability

## Tech Stack

| Technology | Version | Purpose |
|---|---|---|
| Jest | 30.x | Test runner and assertion framework |
| ts-jest | 29.x | TypeScript transform for Jest |
| React Testing Library | 16.x | Component rendering and DOM queries |
| @testing-library/user-event | 14.x | Realistic user interaction simulation |
| @testing-library/jest-dom | 6.x | Extended DOM matchers |
| jsdom | (via jest-environment-jsdom 30.x) | Browser environment simulation |
| React | 19.x | UI framework |
| TypeScript | 5.4 | Type safety |
| Zustand | 4.x | State management |
| React Router DOM | 6.x | Client-side routing |
| @tanstack/react-query | 5.x | Server state management |
| Axios | 1.x | HTTP client |

## Project Configuration

- **Jest config**: `src/frontend/jest.config.js`
- **Setup files**: `src/frontend/jest.setup.js` (globals/mocks) and `src/frontend/src/setupTests.ts` (DOM matchers, ResizeObserver, IntersectionObserver, matchMedia)
- **Path alias**: `@/` maps to `<rootDir>/src/`
- **Test match patterns**: `src/**/__tests__/**/*.{test,spec}.{ts,tsx}` and `src/**/*.{test,spec}.{ts,tsx}`
- **Transform**: Custom `transform-import-meta.js` handles `import.meta` for Jest compatibility
- **Global mocks** (in `jest.setup.js`): `@radix-ui/react-form`, `react-markdown`, `lucide-react/dynamicIconImports`, `@/components/common/genericIconComponent`, `@/icons/BotMessageSquare`, `@/stores/darkStore`, `localStorage`, `sessionStorage`, `crypto`

## Key Commands

```bash
# Run all tests
npm test

# Run a specific test file
npm test -- path/to/file.test.tsx

# Run tests matching a pattern
npm test -- --testPathPattern="alertStore"

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage

# Run a single test file with coverage
npm test -- --coverage --collectCoverageFrom='src/path/to/source.ts' path/to/__tests__/source.test.ts
```

## File Naming and Location

Test files follow one of two patterns:

1. **Dedicated `__tests__` directory** (preferred for components and modules):
   ```
   src/components/core/my-component/
   ├── my-component.tsx
   └── __tests__/
       └── my-component.test.tsx
   ```

2. **Co-located test file** (acceptable for utilities and simple modules):
   ```
   src/utils/
   ├── myUtil.ts
   └── myUtil.test.ts
   ```

Naming convention: `ComponentName.test.tsx` for components, `hook-name.test.ts` for hooks, `util-name.test.ts` for utilities.

**Do NOT use `.spec.tsx`** -- while technically matched, the project convention is `.test.tsx`.

## Test Structure Template

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MyComponent from "../MyComponent";

// Mock dependencies (use jest.mock, NOT vi.mock)
jest.mock("@/controllers/API/api", () => ({
  get: jest.fn(),
  post: jest.fn(),
}));

describe("MyComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("rendering", () => {
    it("should render the component with default props", () => {
      // Arrange
      render(<MyComponent />);

      // Act - (none for render test)

      // Assert
      expect(screen.getByRole("button", { name: /submit/i })).toBeInTheDocument();
    });
  });

  describe("user interactions", () => {
    it("should call onSubmit when the form is submitted", async () => {
      // Arrange
      const user = userEvent.setup();
      const onSubmit = jest.fn();
      render(<MyComponent onSubmit={onSubmit} />);

      // Act
      await user.click(screen.getByRole("button", { name: /submit/i }));

      // Assert
      expect(onSubmit).toHaveBeenCalledTimes(1);
    });
  });
});
```

## Incremental Testing Workflow

When testing a directory with multiple files, follow this order:

1. **Identify all source files** in the target directory
2. **Order by complexity** (simplest first):
   - Pure utility functions (no React, no side effects)
   - Constants and configuration objects
   - Custom hooks (no UI rendering)
   - Simple presentational components (no state, no side effects)
   - Stateful components with local state
   - Components using Zustand stores
   - Components with API calls or complex async behavior
   - Integration-level components that compose many children
3. **For each file**:
   a. Read the source file completely
   b. Identify all exported functions, components, and types
   c. Write tests covering all branches and edge cases
   d. Run the tests and fix any failures
   e. Check coverage and add tests for uncovered lines
   f. Move to the next file
4. **Run full directory coverage** at the end to verify

## Complexity-Based Test Ordering

Within a single test file, order test cases from simplest to most complex:

1. Default rendering / initial state
2. Props variations and conditional rendering
3. User interactions (clicks, typing, form submission)
4. Async operations (API calls, timers)
5. Error states and edge cases
6. Integration with stores or context
7. Cleanup and unmount behavior

## Core Principles

### Arrange-Act-Assert (AAA)
Every test should have a clear three-phase structure. Use blank lines to separate each phase for readability.

### Black-Box Testing
Test the component from the user's perspective. Query by role, label, text, or `data-testid` -- never by CSS class, internal state variable, or implementation detail.

### Single Behavior Per Test
Each `it()` block should verify exactly one behavior. If you need to write "and" in the test name, split it into two tests.

### Semantic Test Names
Use descriptive names that explain the expected behavior:
- Good: `"should disable the submit button when the form is invalid"`
- Bad: `"button test"` or `"test 1"`

Format: `"should [expected behavior] when [condition]"`

## Required Test Scenarios

For every component, cover at minimum:

### Rendering
- Default render with no optional props
- Render with all optional props provided
- Conditional rendering branches (if/else in JSX)

### Props and State
- Each prop variation that changes rendered output
- Default prop values
- State transitions triggered by user actions

### User Interactions
- Click handlers
- Form input and submission
- Keyboard navigation (if applicable)
- Hover/focus states (if applicable)

### Challenge Tests (MANDATORY — not optional)

**Happy path tests alone are NOT enough.** They only confirm the code works when everything is perfect. Real bugs hide in the cracks. You MUST write tests that actively TRY TO BREAK the code:

**Unexpected inputs:**
- `null`, `undefined`, `""`, `[]`, `{}`, `0`, `-1`, `NaN`, `Infinity`
- What happens when a required prop is missing?
- What happens when data from the API comes back with missing fields?

**Boundary values:**
- Max length strings (paste 10,000 chars in an input)
- Exactly at the limit, one past the limit
- Zero items, one item, maximum items
- First page, last page, out-of-range page

**Malformed data:**
- API returns `{ data: null }` instead of `{ data: [] }`
- JSON with extra unexpected fields
- Dates in wrong format, numbers as strings

**Error states:**
- Network failure (API rejects with 500)
- Authentication expired mid-action (401)
- Resource not found (404)
- Permission denied (403)
- Timeout

**What should NOT happen:**
- Verify that deleting a flow does NOT delete flows from other users
- Verify that a read-only user CANNOT trigger write mutations
- Verify that XSS payloads in user input are sanitized

**Rapid/concurrent actions:**
- Double-click on submit button
- Rapid repeated API calls
- Unmount component while async operation is in flight

**Write tests based on REQUIREMENTS, not on what the source code does.** This is how you catch bugs where the code diverges from expected behavior.

**When a test fails:** first ask if the CODE is wrong, not the test. Do NOT silently change a failing assertion to match the current code without understanding WHY.

### Async Behavior
- Loading states
- Success states
- Error states
- Timeout/retry behavior

## Coverage Goals

Per source file:
- **Function coverage**: 100%
- **Branch coverage**: > 95%
- **Line coverage**: > 95%
- **Statement coverage**: > 95%

Run coverage for a specific file:
```bash
npm test -- --coverage --collectCoverageFrom='src/path/to/file.ts' src/path/to/__tests__/file.test.ts
```

## Important Rules

1. **Never use Vitest APIs**: Use `jest.fn()`, `jest.mock()`, `jest.spyOn()`, `jest.mocked()` -- never `vi.*` equivalents.
2. **Never mock base UI components** from `@/components/ui/` -- render them as-is.
3. **Check `jest.setup.js` before mocking**: Many modules are already globally mocked (darkStore, genericIconComponent, react-markdown, radix-form, etc.). Do not re-mock them.
4. **Use `@testing-library/user-event`** over `fireEvent` for user interactions.
5. **Wrap state updates in `act()`** when testing Zustand stores or React state changes.
6. **Clean up after each test**: Use `beforeEach(() => jest.clearAllMocks())` and `afterEach` for timers.
7. **Always write both happy path AND adversarial tests** (null, undefined, empty values, boundary conditions, error states).
8. **Minimum coverage: 75%** (target 80%). Below 75% the task is not complete.

## Forbidden Test Anti-Patterns

| Pattern | Problem | How to Detect |
|---------|---------|---------------|
| **The Liar** | Test passes but doesn't verify the behavior it claims to test | Assertions don't match the test name |
| **The Mirror** | Test reads source code and asserts exactly what the code does — finds zero bugs | Test would never fail even if logic changes |
| **The Giant** | 50+ lines of setup, multiple acts, dozens of assertions | Should be 5+ separate tests |
| **The Mockery** | So many mocks that the test only tests the mock setup | Count mocks — if > 3 deep, rethink |
| **The Inspector** | Coupled to implementation details, breaks on any refactor | Tests internal state instead of behavior |
| **The Chain Gang** | Tests depend on execution order or share mutable state | Tests fail when run in isolation |
| **The Flaky** | Sometimes passes, sometimes fails with no code changes | Non-deterministic assertions or timing issues |

## References

- [Incremental Testing Workflow](references/workflow.md) - Step-by-step process for testing directories
- [Mocking Guide](references/mocking.md) - Patterns for mocking APIs, stores, routers, and context
- [Async Testing](references/async-testing.md) - Patterns for async operations, timers, and waitFor
- [Common Patterns](references/common-patterns.md) - Query priority, events, forms, modals, data-driven tests
- [Test Checklist](references/checklist.md) - Pre-submission verification checklist
- [Domain Components](references/domain-components.md) - Langflow-specific component testing patterns
- [Component Template](assets/component-test.template.tsx) - Starter template for component tests
- [Hook Template](assets/hook-test.template.ts) - Starter template for hook tests
- [Utility Template](assets/utility-test.template.ts) - Starter template for utility tests
