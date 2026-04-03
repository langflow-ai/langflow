# Mocking Guide for Langflow Tests

All mocking in Langflow uses Jest APIs. Never use Vitest (`vi.*`) APIs.

## Quick Reference

| Vitest (DO NOT USE) | Jest (USE THIS) |
|---|---|
| `vi.fn()` | `jest.fn()` |
| `vi.mock()` | `jest.mock()` |
| `vi.spyOn()` | `jest.spyOn()` |
| `vi.mocked()` | `jest.mocked()` |
| `vi.clearAllMocks()` | `jest.clearAllMocks()` |
| `vi.useFakeTimers()` | `jest.useFakeTimers()` |
| `vi.useRealTimers()` | `jest.useRealTimers()` |
| `vi.advanceTimersByTime()` | `jest.advanceTimersByTime()` |

## Pre-Existing Global Mocks

These modules are already mocked in `jest.setup.js`. Do NOT re-mock them unless you need different behavior:

- `@radix-ui/react-form` (all exports render children)
- `react-markdown` (renders null)
- `lucide-react/dynamicIconImports` (empty object)
- `@/components/common/genericIconComponent` (renders null)
- `@/icons/BotMessageSquare` (renders null)
- `@/stores/darkStore` (returns default state)
- `localStorage` and `sessionStorage` (jest.fn() stubs)

To use the real implementation instead:
```typescript
jest.unmock("@/stores/darkStore");
```

## API Mocking

### Mocking Axios Calls

Langflow uses Axios via a configured API instance. Mock the API module:

```typescript
import api from "@/controllers/API/api";

jest.mock("@/controllers/API/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
    put: jest.fn(),
    patch: jest.fn(),
    delete: jest.fn(),
  },
}));

describe("MyComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should fetch data on mount", async () => {
    jest.mocked(api.get).mockResolvedValueOnce({
      data: { items: [{ id: "1", name: "Test" }] },
    });

    render(<MyComponent />);

    await waitFor(() => {
      expect(screen.getByText("Test")).toBeInTheDocument();
    });

    expect(api.get).toHaveBeenCalledWith("/api/v1/items");
  });

  it("should handle API errors", async () => {
    jest.mocked(api.get).mockRejectedValueOnce(new Error("Network error"));

    render(<MyComponent />);

    await waitFor(() => {
      expect(screen.getByText(/error/i)).toBeInTheDocument();
    });
  });
});
```

### Mocking Specific API Query Hooks

For components using React Query hooks from `@/controllers/API/queries/`:

```typescript
jest.mock("@/controllers/API/queries/flows", () => ({
  useGetFlowsQuery: jest.fn().mockReturnValue({
    data: [{ id: "flow-1", name: "My Flow" }],
    isLoading: false,
    error: null,
    refetch: jest.fn(),
  }),
}));
```

### Mocking Individual API Functions

```typescript
jest.mock("@/controllers/API", () => ({
  getFlows: jest.fn().mockResolvedValue([]),
  saveFlow: jest.fn().mockResolvedValue({ id: "new-flow" }),
  deleteFlow: jest.fn().mockResolvedValue(undefined),
}));
```

## Zustand Store Mocking

Langflow does NOT have a global Zustand auto-mock. You have two options:

### Option 1: Use Real Stores with `setState()` (Preferred)

```typescript
import useAlertStore from "@/stores/alertStore";

describe("Alert-dependent component", () => {
  beforeEach(() => {
    // Reset store to known state before each test
    useAlertStore.setState({
      errorData: { title: "", list: [] },
      noticeData: { title: "", link: "" },
      successData: { title: "" },
      notificationCenter: false,
      notificationList: [],
      tempNotificationList: [],
    });
  });

  it("should display error notification", () => {
    // Pre-set store state
    useAlertStore.setState({
      errorData: { title: "Something went wrong", list: ["Detail"] },
    });

    render(<NotificationBanner />);

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });
});
```

### Option 2: Mock the Store Module

Use when the real store has complex initialization or `import.meta` dependencies:

```typescript
const mockFlowStore = {
  nodes: [],
  edges: [],
  setNodes: jest.fn(),
  setEdges: jest.fn(),
  onNodesChange: jest.fn(),
  onEdgesChange: jest.fn(),
  onConnect: jest.fn(),
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: (state: any) => any) =>
    selector ? selector(mockFlowStore) : mockFlowStore,
}));

describe("FlowCanvas", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockFlowStore.nodes = [];
    mockFlowStore.edges = [];
  });

  it("should render nodes from the store", () => {
    mockFlowStore.nodes = [
      { id: "node-1", type: "genericNode", data: { node: { display_name: "OpenAI" } }, position: { x: 0, y: 0 } },
    ];

    render(<FlowCanvas />);

    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });
});
```

### Option 3: Use `renderHook` for Store Tests

For testing the store itself:

```typescript
import { act, renderHook } from "@testing-library/react";
import useMyStore from "../myStore";

describe("useMyStore", () => {
  beforeEach(() => {
    useMyStore.setState({ count: 0 });
  });

  it("should increment count", () => {
    const { result } = renderHook(() => useMyStore());

    act(() => {
      result.current.increment();
    });

    expect(result.current.count).toBe(1);
  });
});
```

## React Router Mocking

Langflow uses `react-router-dom` v6 (NOT Next.js routing).

### Wrapping with MemoryRouter

```typescript
import { MemoryRouter } from "react-router-dom";

it("should render the page", () => {
  render(
    <MemoryRouter initialEntries={["/flows/flow-123"]}>
      <FlowPage />
    </MemoryRouter>,
  );
});
```

### Mocking useNavigate

```typescript
const mockNavigate = jest.fn();

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useNavigate: () => mockNavigate,
}));

it("should navigate to flow page on click", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <FlowCard flow={mockFlow} />
    </MemoryRouter>,
  );

  await user.click(screen.getByText("Open Flow"));
  expect(mockNavigate).toHaveBeenCalledWith("/flow/flow-123");
});
```

### Mocking useParams

```typescript
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useParams: () => ({ flowId: "flow-123" }),
}));
```

### Mocking useSearchParams

```typescript
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useSearchParams: () => [new URLSearchParams("tab=settings"), jest.fn()],
}));
```

## React Query Mocking

### Creating a Test QueryClient

```typescript
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}
```

### Mocking useMutation

```typescript
jest.mock("@tanstack/react-query", () => ({
  ...jest.requireActual("@tanstack/react-query"),
  useMutation: jest.fn().mockReturnValue({
    mutate: jest.fn(),
    mutateAsync: jest.fn(),
    isPending: false,
    isError: false,
    error: null,
    data: undefined,
  }),
}));
```

## Context Provider Mocking

### Wrapping with Providers

For components that depend on React context:

```typescript
import { AuthContext } from "@/contexts/authContext";

const mockAuthContext = {
  isAuthenticated: true,
  userData: { id: "user-1", username: "testuser" },
  login: jest.fn(),
  logout: jest.fn(),
  getAuthentication: jest.fn(),
  autoLogin: false,
};

it("should show user name when authenticated", () => {
  render(
    <AuthContext.Provider value={mockAuthContext}>
      <UserMenu />
    </AuthContext.Provider>,
  );

  expect(screen.getByText("testuser")).toBeInTheDocument();
});
```

### Mocking useContext Directly

```typescript
jest.mock("react", () => ({
  ...jest.requireActual("react"),
  useContext: jest.fn().mockReturnValue({
    isAuthenticated: true,
    userData: { username: "testuser" },
  }),
}));
```

## Component Mocking

### Mocking Child Components

When a child component is complex or has side effects:

```typescript
jest.mock("@/components/core/chatView/ChatView", () => ({
  __esModule: true,
  default: ({ onSend }: any) => (
    <div data-testid="mock-chat-view">
      <button onClick={() => onSend("test message")}>Send</button>
    </div>
  ),
}));
```

### DO NOT Mock Base UI Components

Never mock components from `@/components/ui/`:
- `Button`, `Input`, `Select`, `Dialog`, `Popover`, etc.
- These are simple Radix/shadcn wrappers and should be rendered as-is
- Mocking them hides real rendering issues

### Mocking Third-Party Components

```typescript
// Mock @xyflow/react for flow-related tests
jest.mock("@xyflow/react", () => ({
  ReactFlow: ({ children }: any) => <div data-testid="react-flow">{children}</div>,
  useReactFlow: () => ({
    getNodes: jest.fn().mockReturnValue([]),
    getEdges: jest.fn().mockReturnValue([]),
    setNodes: jest.fn(),
    setEdges: jest.fn(),
    fitView: jest.fn(),
    zoomIn: jest.fn(),
    zoomOut: jest.fn(),
  }),
  useNodesState: jest.fn().mockReturnValue([[], jest.fn(), jest.fn()]),
  useEdgesState: jest.fn().mockReturnValue([[], jest.fn(), jest.fn()]),
  Background: () => null,
  Controls: () => null,
  MiniMap: () => null,
  Handle: ({ type, position }: any) => (
    <div data-testid={`handle-${type}-${position}`} />
  ),
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
  MarkerType: { ArrowClosed: "arrowclosed" },
}));
```

## Window and DOM Mocking

### Already Mocked in Setup Files

These are globally mocked in `setupTests.ts` -- do not re-mock:
- `ResizeObserver`
- `IntersectionObserver`
- `window.matchMedia`

### Mocking window.location

```typescript
const originalLocation = window.location;

beforeEach(() => {
  Object.defineProperty(window, "location", {
    value: { ...originalLocation, href: "http://localhost:3000", assign: jest.fn() },
    writable: true,
  });
});

afterEach(() => {
  Object.defineProperty(window, "location", {
    value: originalLocation,
    writable: true,
  });
});
```

### Mocking Clipboard

```typescript
Object.assign(navigator, {
  clipboard: {
    writeText: jest.fn().mockResolvedValue(undefined),
    readText: jest.fn().mockResolvedValue("clipboard content"),
  },
});
```

## Common Pitfalls

1. **Mocking before imports**: `jest.mock()` calls are hoisted automatically by Jest. You do not need to place them before import statements (but it is conventional to do so for readability).

2. **Forgetting `__esModule: true`**: When mocking a module with default exports, include `__esModule: true` in the mock factory.

3. **Over-mocking**: Only mock what is necessary. If the real module works in jsdom, prefer using it.

4. **Not resetting mocks**: Always use `jest.clearAllMocks()` in `beforeEach` to prevent test contamination.

5. **Mocking globally-mocked modules**: Check `jest.setup.js` first. Duplicating a mock may cause unexpected behavior.
