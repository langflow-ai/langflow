# Store Testing Utilities

This directory contains shared testing utilities for Zustand stores in the Langflow frontend application.

## Files

### `testUtils.ts`
Common utilities and helpers for testing Zustand stores:

- **`resetStoreState(store, initialState)`**: Helper to reset store state in beforeEach blocks
- **`createLocalStorageMock()`**: Creates a mock localStorage implementation for testing
- **`mockDataFactory`**: Factory functions for creating consistent test data:
  - `createUser()`, `createFlow()`, `createFolder()`, `createMessage()`
  - `createVoice()`, `createProvider()`, `createTag()`, `createPagination()`
- **`createMockApiResponse()`**: Creates mock API response objects
- **`createMockFetch()`**: Creates mock fetch functions with configurable responses
- **`testHelpers`**: Common test assertion helpers for array toggles and sequential updates
- **`mockHelpers`**: Jest mock setup helpers

### `setupTests.ts`
Global test setup and common mocks used across all store tests:
- Mock implementations for browser APIs (ResizeObserver, IntersectionObserver, crypto)
- Common environment variables and DOM method mocks
- Global beforeEach cleanup

## Usage Examples

### Using `resetStoreState` instead of manual act calls:

```typescript
// Before
beforeEach(() => {
  act(() => {
    useMyStore.setState({
      prop1: defaultValue1,
      prop2: defaultValue2,
    });
  });
});

// After
import { resetStoreState } from "./testUtils";

beforeEach(() => {
  resetStoreState(useMyStore, {
    prop1: defaultValue1,
    prop2: defaultValue2,
  });
});
```

### Using `mockDataFactory` for consistent test data:

```typescript
// Before
const mockUser = {
  id: "user-1",
  username: "testuser",
  email: "test@example.com",
  is_active: true,
  is_superuser: false,
  // ... more properties
};

// After
import { mockDataFactory } from "./testUtils";

const mockUser = mockDataFactory.createUser({
  username: "testuser",
  email: "test@example.com",
});
```

### Using `createLocalStorageMock` for localStorage tests:

```typescript
import { createLocalStorageMock } from "./testUtils";

beforeEach(() => {
  const mockStorage = createLocalStorageMock();
  Object.defineProperty(window, 'localStorage', {
    value: mockStorage,
    writable: true,
  });
});
```

## Benefits

1. **Consistency**: All tests use the same patterns and mock data structures
2. **Maintainability**: Changes to common patterns only need to be made in one place
3. **Readability**: Tests are more focused on the actual test logic rather than setup boilerplate
4. **Reliability**: Shared utilities are tested and proven to work across all stores
5. **Efficiency**: Reduced code duplication across 14+ test files

## Test Coverage

The shared utilities support comprehensive testing of:
- ✅ State initialization and reset
- ✅ Action function calls and state updates
- ✅ Complex business logic (undo/redo, message management)
- ✅ Edge cases (large datasets, rapid changes, Unicode support)
- ✅ Browser API interactions (localStorage, DOM events)
- ✅ Multi-store interactions and state consistency

## Migration

When updating existing tests to use these utilities:

1. Import required utilities: `import { resetStoreState, mockDataFactory } from "./testUtils"`
2. Replace manual `act(() => store.setState())` with `resetStoreState(store, initialState)`
3. Replace hardcoded mock objects with `mockDataFactory.createX()` calls
4. Keep existing `act` imports for test actions (still needed for user interactions)
5. Ensure jest.mock calls use static values (not imported utilities)

## Total Test Count: 372 Tests
- 14 Zustand stores fully tested
- Comprehensive coverage including edge cases
- Consistent patterns across all test files