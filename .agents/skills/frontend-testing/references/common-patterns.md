# Common Testing Patterns

Frequently used patterns for testing Langflow React components with Jest and React Testing Library.

## Query Priority

Use queries in this priority order (most to least preferred):

| Priority | Query | When to Use |
|---|---|---|
| 1 | `getByRole` | Buttons, inputs, headings, links, checkboxes |
| 2 | `getByLabelText` | Form inputs associated with labels |
| 3 | `getByPlaceholderText` | Inputs with placeholder text |
| 4 | `getByText` | Non-interactive content, paragraphs, spans |
| 5 | `getByDisplayValue` | Filled input/textarea/select values |
| 6 | `getByAltText` | Images |
| 7 | `getByTitle` | Elements with title attribute |
| 8 | `getByTestId` | Last resort -- when no semantic query works |

### Query Variants

| Variant | Throws if not found | Returns | Use When |
|---|---|---|---|
| `getBy*` | Yes | Element | Element should exist |
| `queryBy*` | No | Element or null | Asserting element does NOT exist |
| `findBy*` | Yes (after timeout) | Promise<Element> | Element appears asynchronously |
| `getAllBy*` | Yes | Element[] | Multiple elements expected |
| `queryAllBy*` | No | Element[] (may be empty) | Counting or absence of multiple |
| `findAllBy*` | Yes (after timeout) | Promise<Element[]> | Multiple elements appear async |

### Examples

```typescript
// Preferred: query by role
screen.getByRole("button", { name: /save/i });
screen.getByRole("textbox", { name: /search/i });
screen.getByRole("heading", { level: 2 });
screen.getByRole("checkbox", { name: /agree/i });
screen.getByRole("combobox");

// Assert absence
expect(screen.queryByText("Error")).not.toBeInTheDocument();

// Async appearance
const element = await screen.findByText("Loaded");
```

## User Events

Always use `@testing-library/user-event` over `fireEvent`:

```typescript
import userEvent from "@testing-library/user-event";

describe("UserInteractions", () => {
  it("should handle click", async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();

    render(<button onClick={onClick}>Click me</button>);
    await user.click(screen.getByRole("button"));

    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("should handle typing", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();

    render(<input onChange={onChange} />);
    await user.type(screen.getByRole("textbox"), "hello");

    expect(onChange).toHaveBeenCalledTimes(5); // One per character
  });

  it("should handle clearing and typing", async () => {
    const user = userEvent.setup();

    render(<input defaultValue="old value" />);
    const input = screen.getByRole("textbox");

    await user.clear(input);
    await user.type(input, "new value");

    expect(input).toHaveValue("new value");
  });

  it("should handle keyboard navigation", async () => {
    const user = userEvent.setup();

    render(
      <div>
        <input data-testid="input-1" />
        <input data-testid="input-2" />
      </div>,
    );

    await user.tab();
    expect(screen.getByTestId("input-1")).toHaveFocus();

    await user.tab();
    expect(screen.getByTestId("input-2")).toHaveFocus();
  });

  it("should handle select/dropdown", async () => {
    const user = userEvent.setup();

    render(
      <select>
        <option value="a">Option A</option>
        <option value="b">Option B</option>
      </select>,
    );

    await user.selectOptions(screen.getByRole("combobox"), "b");
    expect(screen.getByRole("combobox")).toHaveValue("b");
  });

  it("should handle hover", async () => {
    const user = userEvent.setup();
    const onMouseEnter = jest.fn();

    render(<div onMouseEnter={onMouseEnter}>Hover me</div>);
    await user.hover(screen.getByText("Hover me"));

    expect(onMouseEnter).toHaveBeenCalledTimes(1);
  });
});
```

## Form Testing

```typescript
describe("LoginForm", () => {
  it("should submit form with valid data", async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn();

    render(<LoginForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/username/i), "testuser");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(onSubmit).toHaveBeenCalledWith({
      username: "testuser",
      password: "password123",
    });
  });

  it("should show validation errors for empty fields", async () => {
    const user = userEvent.setup();

    render(<LoginForm onSubmit={jest.fn()} />);

    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByText(/username is required/i)).toBeInTheDocument();
    expect(screen.getByText(/password is required/i)).toBeInTheDocument();
  });

  it("should disable submit button while submitting", async () => {
    const user = userEvent.setup();
    const onSubmit = jest.fn(() => new Promise(() => {})); // Never resolves

    render(<LoginForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText(/username/i), "testuser");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
  });
});
```

## Modal/Dialog Testing

Langflow uses Radix UI dialogs:

```typescript
describe("ConfirmDialog", () => {
  it("should open and close the dialog", async () => {
    const user = userEvent.setup();

    render(<ConfirmDialog trigger={<button>Open</button>} />);

    // Dialog should not be visible initially
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    // Open dialog
    await user.click(screen.getByRole("button", { name: /open/i }));

    // Dialog should be visible
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText(/are you sure/i)).toBeInTheDocument();

    // Close dialog by clicking cancel
    await user.click(screen.getByRole("button", { name: /cancel/i }));

    // Dialog should be hidden
    await waitForElementToBeRemoved(() => screen.queryByRole("dialog"));
  });

  it("should call onConfirm when confirmed", async () => {
    const user = userEvent.setup();
    const onConfirm = jest.fn();

    render(
      <ConfirmDialog trigger={<button>Open</button>} onConfirm={onConfirm} />,
    );

    await user.click(screen.getByRole("button", { name: /open/i }));
    await user.click(screen.getByRole("button", { name: /confirm/i }));

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
```

## Data-Driven Tests (Parameterized)

Use `it.each` for testing multiple inputs with the same logic:

```typescript
describe("formatDuration", () => {
  it.each([
    [0, "0s"],
    [500, "0.5s"],
    [1000, "1.0s"],
    [1500, "1.5s"],
    [60000, "1m 0s"],
    [90000, "1m 30s"],
    [3600000, "1h 0m"],
  ])("should format %i ms as %s", (input, expected) => {
    expect(formatDuration(input)).toBe(expected);
  });
});
```

### Named Parameters with Objects

```typescript
it.each([
  { input: "", expected: false, description: "empty string" },
  { input: "valid@email.com", expected: true, description: "valid email" },
  { input: "no-at-sign", expected: false, description: "missing @" },
  { input: "@no-local", expected: false, description: "missing local part" },
])("should return $expected for $description", ({ input, expected }) => {
  expect(isValidEmail(input)).toBe(expected);
});
```

## Snapshot Testing

Use sparingly -- only for stable, presentational components:

```typescript
it("should match snapshot", () => {
  const { container } = render(<Badge variant="success" label="Active" />);
  expect(container.firstChild).toMatchSnapshot();
});
```

Prefer explicit assertions over snapshots. Snapshots are fragile and do not communicate test intent.

## Testing Conditional Rendering

```typescript
describe("StatusBadge", () => {
  it("should render success variant", () => {
    render(<StatusBadge status="success" />);
    expect(screen.getByText("Success")).toBeInTheDocument();
  });

  it("should render error variant", () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("should render nothing for unknown status", () => {
    const { container } = render(<StatusBadge status="unknown" />);
    expect(container).toBeEmptyDOMElement();
  });
});
```

## Testing Lists and Tables

```typescript
describe("ItemList", () => {
  it("should render all items", () => {
    const items = [
      { id: "1", name: "Item 1" },
      { id: "2", name: "Item 2" },
      { id: "3", name: "Item 3" },
    ];

    render(<ItemList items={items} />);

    const listItems = screen.getAllByRole("listitem");
    expect(listItems).toHaveLength(3);
    expect(listItems[0]).toHaveTextContent("Item 1");
    expect(listItems[1]).toHaveTextContent("Item 2");
    expect(listItems[2]).toHaveTextContent("Item 3");
  });

  it("should show empty state when no items", () => {
    render(<ItemList items={[]} />);

    expect(screen.getByText(/no items/i)).toBeInTheDocument();
    expect(screen.queryByRole("listitem")).not.toBeInTheDocument();
  });
});
```

## Testing Tooltips

Langflow uses Radix tooltips which require hover:

```typescript
it("should show tooltip on hover", async () => {
  const user = userEvent.setup();

  render(<TooltipButton label="Delete" tooltip="Delete this item" />);

  await user.hover(screen.getByRole("button", { name: /delete/i }));

  await waitFor(() => {
    expect(screen.getByRole("tooltip")).toHaveTextContent("Delete this item");
  });
});
```

## Testing Error Boundaries

```typescript
describe("ErrorBoundary", () => {
  // Suppress console.error for expected errors
  const originalError = console.error;
  beforeAll(() => {
    console.error = jest.fn();
  });
  afterAll(() => {
    console.error = originalError;
  });

  it("should catch errors and show fallback UI", () => {
    const ThrowError = () => {
      throw new Error("Test error");
    };

    render(
      <ErrorBoundary fallback={<div>Something went wrong</div>}>
        <ThrowError />
      </ErrorBoundary>,
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
```

## Testing Custom data-testid Attributes

Langflow components frequently use `data-testid` for testing. Common patterns:

```typescript
// Input components
screen.getByTestId("popover-anchor-input-api_key");

// Buttons
screen.getByTestId("sidebar-nav-add_note");

// Modal elements
screen.getByTestId("modal-title");

// Flow elements
screen.getByTestId("handle-source-bottom");
```

## Testing with Zustand Store Updates

```typescript
it("should react to store changes", async () => {
  render(<NotificationBanner />);

  // Initially no notification
  expect(screen.queryByText("Error occurred")).not.toBeInTheDocument();

  // Update store
  act(() => {
    useAlertStore.setState({
      errorData: { title: "Error occurred", list: [] },
    });
  });

  // Notification should appear
  expect(screen.getByText("Error occurred")).toBeInTheDocument();
});
```

## Cleanup

React Testing Library automatically cleans up after each test (unmounts rendered components). You do not need to call `cleanup()` manually.

However, you DO need to clean up:
- Fake timers: `jest.useRealTimers()` in `afterEach`
- Spies: `spy.mockRestore()` or `jest.restoreAllMocks()` in `afterEach`
- Store state: Reset via `store.setState()` in `beforeEach`
- Global overrides: Restore original values in `afterEach`
