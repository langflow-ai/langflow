# Incremental Testing Workflow

Step-by-step process for systematically testing a directory of source files in Langflow.

## Phase 1: Discovery

### 1.1 Identify Source Files

List all `.ts` and `.tsx` files in the target directory (excluding existing test files):

```bash
find src/frontend/src/path/to/directory -name '*.ts' -o -name '*.tsx' | grep -v '__tests__' | grep -v '.test.' | grep -v '.spec.' | sort
```

### 1.2 Categorize by Complexity

Sort files into tiers:

| Tier | Description | Examples |
|---|---|---|
| 1 | Pure functions, constants, types | `utils.ts`, `constants.ts`, `types.ts` |
| 2 | Custom hooks (no UI) | `useDebounce.ts`, `useLocalStorage.ts` |
| 3 | Simple presentational components | `Badge.tsx`, `EmptyState.tsx` |
| 4 | Stateful components | `SearchInput.tsx`, `FilterPanel.tsx` |
| 5 | Store-connected components | `NodeToolbar.tsx`, `SidebarHeader.tsx` |
| 6 | Async/API components | `FlowList.tsx`, `GlobalVariablesPage.tsx` |
| 7 | Integration components | `FlowPage.tsx`, `ChatView.tsx` |

### 1.3 Check Existing Coverage

```bash
npm test -- --coverage --collectCoverageFrom='src/path/to/directory/**/*.{ts,tsx}' src/path/to/directory/__tests__/
```

## Phase 2: Write Tests (Per File)

For each source file, starting from Tier 1:

### 2.1 Read the Source

Read the entire source file. Identify:
- All exported functions, components, hooks, and types
- All conditional branches (if/else, ternary, switch, early returns)
- All side effects (API calls, store mutations, DOM manipulation)
- All dependencies that need mocking

### 2.2 Create the Test File

Create `__tests__/SourceFileName.test.tsx` (or `.test.ts` for non-JSX files).

### 2.3 Write Tests in Order

1. **Imports and mocks** at the top
2. **describe block** named after the exported entity
3. **beforeEach** with `jest.clearAllMocks()` and any store resets
4. **Rendering tests** first
5. **Props/state variation tests** next
6. **Interaction tests** next
7. **Async/error tests** last

### 2.4 Run and Verify

```bash
# Run the single test file
npm test -- src/path/to/__tests__/SourceFileName.test.tsx

# Check coverage for the source file
npm test -- --coverage --collectCoverageFrom='src/path/to/SourceFileName.tsx' src/path/to/__tests__/SourceFileName.test.tsx
```

### 2.5 Fix Failures

Common issues:
- **Missing mock**: Add `jest.mock()` for the dependency
- **Act warning**: Wrap state updates in `act()` or use `await waitFor()`
- **Element not found**: Check query strategy -- use `screen.debug()` to inspect DOM
- **Globally mocked module**: Check `jest.setup.js` -- the module may already be mocked

### 2.6 Reach Coverage Targets

If coverage is below targets (100% function, >95% branch/line):
1. Identify uncovered lines in the coverage report
2. Write additional test cases targeting those branches
3. Re-run coverage to confirm improvement

## Phase 3: Directory-Level Verification

After all files in the directory have tests:

### 3.1 Run All Tests Together

```bash
npm test -- --testPathPattern="src/path/to/directory"
```

### 3.2 Check Combined Coverage

```bash
npm test -- --coverage --collectCoverageFrom='src/path/to/directory/**/*.{ts,tsx}' --testPathPattern="src/path/to/directory"
```

### 3.3 Review Test Quality

For each test file, verify:
- [ ] No implementation details tested (no internal state inspection)
- [ ] No redundant tests (each test adds unique coverage)
- [ ] All async operations properly awaited
- [ ] Cleanup performed (timers, spies, store resets)
- [ ] Test names are descriptive and follow the `"should ... when ..."` pattern

## Phase 4: Cleanup

### 4.1 Remove Unnecessary Mocks

If a mock is not actually needed (the real implementation works in jsdom), remove it. Fewer mocks means more realistic tests.

### 4.2 Extract Shared Test Utilities

If multiple test files use the same setup patterns, extract them into a `test-utils.tsx` file in the `__tests__` directory:

```tsx
// __tests__/test-utils.tsx
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
}

export function renderWithProviders(
  ui: React.ReactElement,
  options?: RenderOptions & { route?: string },
) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[options?.route ?? "/"]}>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
    options,
  );
}
```

Note: The Jest config ignores files named `test-utils.tsx` via `testPathIgnorePatterns`.

### 4.3 Final Verification

```bash
# Run full test suite to ensure nothing is broken
npm test

# Run with coverage for a summary report
npm run test:coverage
```

## Troubleshooting

### "Cannot find module" Errors

The `@/` alias maps to `src/frontend/src/`. If a module is not resolved, check `jest.config.js` `moduleNameMapper`.

### "import.meta" Errors

The project uses `transform-import-meta.js` to handle Vite's `import.meta.env`. If you encounter issues, check that the transform is applied in `jest.config.js`.

### Global Mocks Conflicting

Modules mocked in `jest.setup.js` are mocked globally. If you need the real implementation in a specific test:

```typescript
// At the top of your test file, before other imports
jest.unmock("@/stores/darkStore");
```

### Zustand Store State Leaking Between Tests

Always reset store state in `beforeEach`:

```typescript
import useMyStore from "@/stores/myStore";

beforeEach(() => {
  useMyStore.setState({
    // Reset to initial state
    items: [],
    loading: false,
  });
});
```
