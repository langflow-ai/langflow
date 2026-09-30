# Async Testing Patterns

Patterns for testing asynchronous behavior in Langflow with Jest and React Testing Library.

## waitFor

Use `waitFor` when you need to wait for an asynchronous operation to complete before making assertions.

```typescript
import { render, screen, waitFor } from "@testing-library/react";

it("should load and display data", async () => {
  jest.mocked(api.get).mockResolvedValueOnce({
    data: { items: [{ id: "1", name: "Test Item" }] },
  });

  render(<ItemList />);

  // Wait for the async data to appear
  await waitFor(() => {
    expect(screen.getByText("Test Item")).toBeInTheDocument();
  });
});
```

### waitFor Options

```typescript
await waitFor(
  () => {
    expect(screen.getByText("loaded")).toBeInTheDocument();
  },
  {
    timeout: 3000,    // Max time to wait (default: 1000ms)
    interval: 50,     // Polling interval (default: 50ms)
  },
);
```

### waitFor Best Practices

- Put only ONE assertion inside `waitFor`. Multiple assertions can cause misleading failures.
- Use `waitFor` for appearance, not disappearance. Use `waitForElementToBeRemoved` for that.
- Do not use `waitFor` for synchronous operations -- it adds unnecessary delay.

```typescript
// GOOD: Single assertion in waitFor
await waitFor(() => {
  expect(screen.getByText("Data loaded")).toBeInTheDocument();
});

// BAD: Multiple assertions -- if second fails, first may have been true
await waitFor(() => {
  expect(screen.getByText("Data loaded")).toBeInTheDocument();
  expect(screen.getByText("5 items")).toBeInTheDocument(); // unreliable
});

// GOOD: Chain waitFor calls
await waitFor(() => {
  expect(screen.getByText("Data loaded")).toBeInTheDocument();
});
expect(screen.getByText("5 items")).toBeInTheDocument();
```

## waitForElementToBeRemoved

```typescript
it("should hide loading spinner after data loads", async () => {
  jest.mocked(api.get).mockResolvedValueOnce({ data: [] });

  render(<ItemList />);

  // Spinner appears immediately
  expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();

  // Wait for it to disappear
  await waitForElementToBeRemoved(() =>
    screen.queryByTestId("loading-spinner"),
  );

  // Now assert the loaded state
  expect(screen.getByText("No items found")).toBeInTheDocument();
});
```

## findBy Queries

`findBy*` queries return a promise that resolves when the element appears. They are shorthand for `waitFor` + `getBy*`.

```typescript
it("should display async content", async () => {
  jest.mocked(api.get).mockResolvedValueOnce({ data: { name: "Test" } });

  render(<AsyncComponent />);

  // findByText = waitFor(() => getByText(...))
  const element = await screen.findByText("Test");
  expect(element).toBeInTheDocument();
});
```

### findBy with Custom Timeout

```typescript
const element = await screen.findByText("Slow content", {}, { timeout: 5000 });
```

## Fake Timers

Use fake timers for components that use `setTimeout`, `setInterval`, or `Date.now`.

```typescript
describe("TimerComponent", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  it("should update after interval", () => {
    render(<TimerComponent interval={1000} />);

    expect(screen.getByText("0 seconds")).toBeInTheDocument();

    act(() => {
      jest.advanceTimersByTime(3000);
    });

    expect(screen.getByText("3 seconds")).toBeInTheDocument();
  });

  it("should clean up interval on unmount", () => {
    const clearIntervalSpy = jest.spyOn(global, "clearInterval");

    const { unmount } = render(<TimerComponent interval={1000} />);
    unmount();

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
  });
});
```

### Combining Fake Timers with Async Operations

When a component uses both timers and async operations (API calls), you need special handling:

```typescript
it("should poll for updates", async () => {
  jest.useFakeTimers();

  const mockGet = jest.mocked(api.get);
  mockGet
    .mockResolvedValueOnce({ data: { status: "pending" } })
    .mockResolvedValueOnce({ data: { status: "complete" } });

  render(<PollingComponent />);

  // First fetch happens immediately
  await waitFor(() => {
    expect(screen.getByText("pending")).toBeInTheDocument();
  });

  // Advance past the polling interval
  act(() => {
    jest.advanceTimersByTime(5000);
  });

  // Second fetch resolves
  await waitFor(() => {
    expect(screen.getByText("complete")).toBeInTheDocument();
  });

  jest.useRealTimers();
});
```

### Mocking Date.now

For components that use `Date.now()` for elapsed time:

```typescript
it("should track elapsed time", async () => {
  const realDateNow = Date.now;
  let mockTime = 1000000;
  Date.now = jest.fn(() => mockTime);

  jest.useFakeTimers();

  render(<ElapsedTimer />);

  // Advance mock time by 2 seconds
  mockTime += 2000;
  act(() => {
    jest.advanceTimersByTime(100); // Trigger interval callback
  });

  await waitFor(() => {
    expect(screen.getByText("2.0s")).toBeInTheDocument();
  });

  Date.now = realDateNow;
  jest.useRealTimers();
});
```

## Testing Promise Rejection

```typescript
it("should display error message on API failure", async () => {
  jest.mocked(api.get).mockRejectedValueOnce(new Error("Server error"));

  render(<DataComponent />);

  await waitFor(() => {
    expect(screen.getByText(/server error/i)).toBeInTheDocument();
  });
});
```

## Testing Debounced Functions

```typescript
it("should debounce search input", async () => {
  jest.useFakeTimers();
  const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });

  render(<SearchInput onSearch={mockSearch} debounceMs={300} />);

  const input = screen.getByRole("textbox");
  await user.type(input, "hello");

  // Should not have called search yet
  expect(mockSearch).not.toHaveBeenCalled();

  // Advance past debounce delay
  act(() => {
    jest.advanceTimersByTime(300);
  });

  expect(mockSearch).toHaveBeenCalledWith("hello");

  jest.useRealTimers();
});
```

**Important**: When using `userEvent` with fake timers, pass `advanceTimers: jest.advanceTimersByTime` to the setup options. This allows userEvent to advance fake timers during its internal delays.

## Testing Event Streams / WebSockets

For components that consume SSE or WebSocket events:

```typescript
it("should handle streaming messages", async () => {
  const mockEventSource = {
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    close: jest.fn(),
  };

  jest.spyOn(global, "EventSource" as any).mockImplementation(
    () => mockEventSource,
  );

  render(<StreamingChat />);

  // Simulate incoming message
  const onMessage = mockEventSource.addEventListener.mock.calls.find(
    ([event]: [string]) => event === "message",
  )?.[1];

  act(() => {
    onMessage?.({ data: JSON.stringify({ text: "Hello from stream" }) });
  });

  expect(screen.getByText("Hello from stream")).toBeInTheDocument();
});
```

## Testing React Query Mutations

```typescript
it("should save and show success", async () => {
  const user = userEvent.setup();
  jest.mocked(api.post).mockResolvedValueOnce({ data: { id: "new-1" } });

  render(
    <QueryClientProvider client={createTestQueryClient()}>
      <CreateForm />
    </QueryClientProvider>,
  );

  await user.type(screen.getByLabelText("Name"), "New Item");
  await user.click(screen.getByRole("button", { name: /save/i }));

  await waitFor(() => {
    expect(screen.getByText(/saved successfully/i)).toBeInTheDocument();
  });

  expect(api.post).toHaveBeenCalledWith("/api/v1/items", {
    name: "New Item",
  });
});
```

## Testing Loading States

```typescript
it("should show loading then content", async () => {
  let resolvePromise: (value: any) => void;
  const promise = new Promise((resolve) => {
    resolvePromise = resolve;
  });

  jest.mocked(api.get).mockReturnValueOnce(promise as any);

  render(<DataDisplay />);

  // Loading state
  expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
  expect(screen.queryByText("Data content")).not.toBeInTheDocument();

  // Resolve the promise
  await act(async () => {
    resolvePromise!({ data: { content: "Data content" } });
  });

  // Loaded state
  expect(screen.queryByTestId("loading-spinner")).not.toBeInTheDocument();
  expect(screen.getByText("Data content")).toBeInTheDocument();
});
```

## Common Pitfalls

1. **Forgetting `act()` with timers**: Always wrap `jest.advanceTimersByTime()` in `act()` when it triggers React state updates.

2. **Not cleaning up timers**: Always call `jest.runOnlyPendingTimers()` then `jest.useRealTimers()` in `afterEach` to prevent timer leaks between tests.

3. **Using `waitFor` for sync assertions**: If the element is already in the DOM after render, use `getBy*` directly. `waitFor` adds unnecessary polling.

4. **Missing `await` on async operations**: Forgetting `await` on `waitFor`, `findBy*`, or `userEvent` methods causes tests to pass vacuously.

5. **Fake timers breaking promises**: If promises are not resolving with fake timers, try `jest.advanceTimersByTime()` inside `act(async () => { ... })`.
