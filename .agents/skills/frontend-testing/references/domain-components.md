# Domain-Specific Component Testing for Langflow

Patterns for testing Langflow-specific components that have unique architectural concerns.

## Flow/Graph Components

Langflow's flow editor is built on `@xyflow/react` (React Flow). These components require specific mocking strategies.

### GenericNode

`GenericNode` is the main node component rendered in the flow canvas. Located at `src/frontend/src/CustomNodes/GenericNode/`.

```typescript
import { render, screen } from "@testing-library/react";
import GenericNode from "@/CustomNodes/GenericNode";

// Mock @xyflow/react
jest.mock("@xyflow/react", () => ({
  Handle: ({ type, position, id }: any) => (
    <div data-testid={`handle-${type}-${id}`} data-position={position} />
  ),
  Position: { Top: "top", Bottom: "bottom", Left: "left", Right: "right" },
  useUpdateNodeInternals: () => jest.fn(),
  useReactFlow: () => ({
    getNodes: jest.fn().mockReturnValue([]),
    getEdges: jest.fn().mockReturnValue([]),
    setNodes: jest.fn(),
    setEdges: jest.fn(),
  }),
}));

// Mock the flow store
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: (state: any) => any) =>
    selector
      ? selector({
          nodes: [],
          edges: [],
          setNodes: jest.fn(),
          onNodesChange: jest.fn(),
        })
      : {},
}));

const mockNodeData = {
  id: "node-1",
  type: "genericNode",
  data: {
    node: {
      display_name: "OpenAI",
      description: "OpenAI language model",
      template: {
        api_key: {
          type: "str",
          required: true,
          show: true,
          name: "api_key",
          display_name: "API Key",
          password: true,
          value: "",
          advanced: false,
        },
        model_name: {
          type: "str",
          required: false,
          show: true,
          name: "model_name",
          display_name: "Model Name",
          options: ["gpt-4", "gpt-3.5-turbo"],
          value: "gpt-4",
          advanced: false,
        },
      },
      output_types: ["Message"],
      input_types: ["Text"],
    },
    showNode: true,
  },
  position: { x: 100, y: 200 },
};

describe("GenericNode", () => {
  it("should render the node with display name", () => {
    render(<GenericNode data={mockNodeData.data} id="node-1" />);
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
  });

  it("should render input handles for each visible input field", () => {
    render(<GenericNode data={mockNodeData.data} id="node-1" />);
    // Verify handles are rendered based on template fields
    expect(screen.getByTestId("handle-target-api_key")).toBeInTheDocument();
  });
});
```

### Edge Components

Test edge rendering and connection validation:

```typescript
describe("CustomEdge", () => {
  it("should render a connection between compatible types", () => {
    render(
      <CustomEdge
        id="edge-1"
        source="node-1"
        target="node-2"
        sourceHandle="output-Message"
        targetHandle="input-Text"
      />,
    );

    expect(screen.getByTestId("edge-edge-1")).toBeInTheDocument();
  });
});
```

### Connection Validation

Test type compatibility logic (typically a pure function):

```typescript
import { isValidConnection } from "@/CustomNodes/helpers/connection-validation";

describe("isValidConnection", () => {
  it("should allow connection between compatible types", () => {
    expect(
      isValidConnection({
        sourceType: "Message",
        targetType: "Text",
        compatibleTypes: { Text: ["Message", "Text"] },
      }),
    ).toBe(true);
  });

  it("should reject connection between incompatible types", () => {
    expect(
      isValidConnection({
        sourceType: "DataFrame",
        targetType: "Text",
        compatibleTypes: { Text: ["Message", "Text"] },
      }),
    ).toBe(false);
  });
});
```

### Handle Rendering

Test the handle display logic for minimized/expanded nodes:

```typescript
import { computeDisplayHandle } from "@/CustomNodes/GenericNode/components/RenderInputParameters/helpers";

describe("computeDisplayHandle", () => {
  it("should show handles for non-advanced visible fields", () => {
    const result = computeDisplayHandle({
      showNode: true,
      isAdvanced: false,
      isHidden: false,
    });
    expect(result).toBe(true);
  });

  it("should hide handles when node is minimized", () => {
    const result = computeDisplayHandle({
      showNode: false,
      isAdvanced: false,
      isHidden: false,
    });
    expect(result).toBe(false);
  });
});
```

## Component Configuration Panels

Components for editing node parameters in the inspection panel or modal.

### Parameter Render Components

Located at `src/frontend/src/components/core/parameterRenderComponent/`:

```typescript
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InputComponent from "@/components/core/parameterRenderComponent/components/inputComponent";

describe("InputComponent", () => {
  const defaultProps = {
    value: "",
    onChange: jest.fn(),
    name: "api_key",
    id: "input-api_key",
    password: false,
    placeholder: "Enter API key",
  };

  it("should render input with placeholder", () => {
    render(<InputComponent {...defaultProps} />);
    expect(screen.getByPlaceholderText("Enter API key")).toBeInTheDocument();
  });

  it("should call onChange when user types", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(<InputComponent {...defaultProps} onChange={onChange} />);

    await user.type(screen.getByRole("textbox"), "sk-123");
    expect(onChange).toHaveBeenCalled();
  });

  it("should mask input when password is true", () => {
    render(<InputComponent {...defaultProps} password={true} />);
    expect(screen.getByTestId("popover-anchor-input-api_key")).toHaveAttribute(
      "type",
      "password",
    );
  });
});
```

### Dropdown/Select Components

```typescript
describe("DropdownComponent", () => {
  it("should render options and allow selection", async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();

    render(
      <DropdownComponent
        value="gpt-4"
        options={["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]}
        onChange={onChange}
      />,
    );

    // Open dropdown
    await user.click(screen.getByRole("combobox"));

    // Select an option
    await user.click(screen.getByText("gpt-3.5-turbo"));

    expect(onChange).toHaveBeenCalledWith("gpt-3.5-turbo");
  });
});
```

## Chat Components

Located at `src/frontend/src/components/core/chatComponents/` and `src/frontend/src/modals/IOModal/components/chatView/`.

### Message Display

```typescript
import { render, screen } from "@testing-library/react";
import ChatMessage from "@/components/core/chatComponents/ChatMessage";

describe("ChatMessage", () => {
  it("should render user message", () => {
    render(
      <ChatMessage
        message={{ text: "Hello!", sender: "User", sender_name: "User" }}
      />,
    );

    expect(screen.getByText("Hello!")).toBeInTheDocument();
  });

  it("should render bot message with different styling", () => {
    render(
      <ChatMessage
        message={{ text: "Hi there!", sender: "Machine", sender_name: "AI" }}
      />,
    );

    expect(screen.getByText("Hi there!")).toBeInTheDocument();
  });

  it("should render markdown content", () => {
    render(
      <ChatMessage
        message={{
          text: "Here is **bold** text",
          sender: "Machine",
          sender_name: "AI",
        }}
      />,
    );

    // react-markdown is mocked globally, so test the text content
    expect(screen.getByText(/bold/)).toBeInTheDocument();
  });
});
```

### Message Sorting

Test the message sorting utility (pure function):

```typescript
import { sortMessages } from "@/modals/IOModal/components/chatView/helpers";

describe("sortMessages", () => {
  it("should sort messages by timestamp ascending", () => {
    const messages = [
      { id: "3", timestamp: "2024-01-03T00:00:00Z" },
      { id: "1", timestamp: "2024-01-01T00:00:00Z" },
      { id: "2", timestamp: "2024-01-02T00:00:00Z" },
    ];

    const sorted = sortMessages(messages);

    expect(sorted.map((m) => m.id)).toEqual(["1", "2", "3"]);
  });

  it("should handle empty array", () => {
    expect(sortMessages([])).toEqual([]);
  });
});
```

### Chat Input

```typescript
describe("ChatInput", () => {
  it("should send message on Enter key", async () => {
    const user = userEvent.setup();
    const onSend = jest.fn();

    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "Hello{Enter}");

    expect(onSend).toHaveBeenCalledWith("Hello");
  });

  it("should not send empty message", async () => {
    const user = userEvent.setup();
    const onSend = jest.fn();

    render(<ChatInput onSend={onSend} />);

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "{Enter}");

    expect(onSend).not.toHaveBeenCalled();
  });

  it("should disable input while message is being sent", () => {
    render(<ChatInput onSend={jest.fn()} isLoading={true} />);

    expect(screen.getByRole("textbox")).toBeDisabled();
  });
});
```

## Global Variable Components

Located at `src/frontend/src/components/core/GlobalVariableModal/` and `src/frontend/src/pages/SettingsPage/pages/GlobalVariablesPage/`.

### Global Variable Modal

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GlobalVariableModal from "@/components/core/GlobalVariableModal";

// Mock the API
jest.mock("@/controllers/API/api", () => ({
  __esModule: true,
  default: {
    get: jest.fn(),
    post: jest.fn(),
  },
}));

describe("GlobalVariableModal", () => {
  it("should render the form fields", () => {
    render(
      <GlobalVariableModal
        open={true}
        onClose={jest.fn()}
      />,
    );

    expect(screen.getByLabelText(/variable name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/value/i)).toBeInTheDocument();
  });

  it("should validate required fields", async () => {
    const user = userEvent.setup();

    render(
      <GlobalVariableModal
        open={true}
        onClose={jest.fn()}
      />,
    );

    await user.click(screen.getByRole("button", { name: /save/i }));

    await waitFor(() => {
      expect(screen.getByText(/name is required/i)).toBeInTheDocument();
    });
  });
});
```

### Global Variable in Node Fields

When a global variable is selected for a node field, the input renders as a badge instead of a text input. This is important for testing:

```typescript
describe("InputGlobalComponent", () => {
  it("should show badge when global variable is selected", () => {
    render(
      <InputGlobalComponent
        name="api_key"
        value="OPENAI_API_KEY"
        load_from_db={true}
      />,
    );

    // Badge is rendered instead of input
    expect(screen.queryByTestId("popover-anchor-input-api_key")).not.toBeInTheDocument();
    // Look for the global variable badge instead
    expect(screen.getByText("OPENAI_API_KEY")).toBeInTheDocument();
  });

  it("should show input when no global variable is selected", () => {
    render(
      <InputGlobalComponent
        name="api_key"
        value=""
        load_from_db={false}
      />,
    );

    expect(screen.getByTestId("popover-anchor-input-api_key")).toBeInTheDocument();
  });
});
```

## Playground Components

Located at `src/frontend/src/components/core/playgroundComponent/`.

### Playground View

```typescript
// Mock stores needed by playground
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector?: (state: any) => any) =>
    selector
      ? selector({
          nodes: [],
          edges: [],
          inputs: [{ id: "input-1", type: "ChatInput" }],
          outputs: [{ id: "output-1", type: "ChatOutput" }],
        })
      : {},
}));

jest.mock("@/stores/playgroundStore", () => ({
  __esModule: true,
  default: (selector?: (state: any) => any) =>
    selector
      ? selector({
          isPlaygroundOpen: true,
          setIsPlaygroundOpen: jest.fn(),
        })
      : {},
}));

describe("PlaygroundComponent", () => {
  it("should render chat interface when flow has chat I/O", () => {
    render(<PlaygroundComponent />);
    expect(screen.getByRole("textbox")).toBeInTheDocument();
  });
});
```

### Duration Display

The `DurationDisplay` component shows elapsed time during message processing. It uses `Date.now()` and `setInterval`:

```typescript
// See DurationDisplay.test.tsx in the codebase for a comprehensive example
// Key patterns:
// 1. Mock Date.now for deterministic time
// 2. Use jest.useFakeTimers() for interval control
// 3. Use act() when advancing timers
// 4. Test remount behavior (playground open/close)
```

## Sidebar Components

Located at `src/frontend/src/pages/FlowPage/components/flowSidebarComponent/`.

### Sidebar Search and Filtering

```typescript
describe("SidebarSearch", () => {
  it("should filter components by search term", async () => {
    const user = userEvent.setup();

    render(
      <FlowSidebar
        components={[
          { name: "OpenAI", category: "LLMs" },
          { name: "Pinecone", category: "Vector Stores" },
          { name: "ChatInput", category: "Inputs" },
        ]}
      />,
    );

    await user.type(screen.getByPlaceholderText(/search/i), "open");

    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.queryByText("Pinecone")).not.toBeInTheDocument();
    expect(screen.queryByText("ChatInput")).not.toBeInTheDocument();
  });
});
```

### Draggable Components

```typescript
describe("SidebarDraggableComponent", () => {
  it("should have draggable attributes", () => {
    render(
      <SidebarDraggableComponent
        name="OpenAI"
        type="llm"
        draggable={true}
      />,
    );

    const draggable = screen.getByTestId("sidebar-draggable-openai");
    expect(draggable).toHaveAttribute("draggable", "true");
  });
});
```

## API Code Generation (Modals)

Located at `src/frontend/src/modals/apiModal/utils/`.

These are pure functions that generate code snippets -- ideal for data-driven tests:

```typescript
import { getPythonApiCode } from "@/modals/apiModal/utils/get-python-api-code";

describe("getPythonApiCode", () => {
  it("should generate valid Python code for a flow", () => {
    const code = getPythonApiCode({
      flowId: "flow-123",
      tweaks: { "node-1": { model_name: "gpt-4" } },
      isAuth: true,
    });

    expect(code).toContain("flow-123");
    expect(code).toContain("gpt-4");
    expect(code).toContain("Authorization");
  });

  it("should omit auth header when isAuth is false", () => {
    const code = getPythonApiCode({
      flowId: "flow-123",
      tweaks: {},
      isAuth: false,
    });

    expect(code).not.toContain("Authorization");
  });
});
```

## Testing Tips for Langflow Components

1. **Node template data**: Create reusable mock node data objects. The template structure is deeply nested and used across many components.

2. **Store interdependencies**: Many components read from multiple stores (flowStore, typesStore, alertStore). Mock or initialize all relevant stores.

3. **data-testid conventions**: Langflow uses `data-testid` extensively. Common patterns:
   - `popover-anchor-input-{name}` for input fields
   - `handle-{type}-{position}` for flow handles
   - `sidebar-nav-{action}` for sidebar buttons
   - `edit-fields-button` for inspection panel

4. **Global variable awareness**: When testing components that render node fields, be aware that fields with `load_from_db: true` and a global variable value render as badges, not inputs. The input element will not exist in the DOM.

5. **Inspection panel vs. canvas**: Fields render differently depending on context. Canvas shows non-advanced fields; the inspection panel shows advanced fields. Use `shouldRenderInspectionPanelField()` and `isCanvasVisible()` from `src/frontend/src/CustomNodes/helpers/parameter-filtering.ts`.
