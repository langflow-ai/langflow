import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionItem, EnvVarEntry } from "../types";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputComponent",
  () =>
    function MockInputComponent({
      id,
      placeholder,
      value,
      onChange,
      options,
      selectedOption,
      setSelectedOption,
    }: {
      id: string;
      placeholder: string;
      value: string;
      onChange: (v: string) => void;
      options?: string[];
      selectedOption?: string;
      setSelectedOption?: (v: string) => void;
    }) {
      return (
        <div data-testid={`input-component-${id}`}>
          <input
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            data-testid={`input-${id}`}
          />
          {options && options.length > 0 && (
            <select
              data-testid={`select-${id}`}
              value={selectedOption ?? ""}
              onChange={(e) => setSelectedOption?.(e.target.value)}
            >
              <option value="">Select...</option>
              {options.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          )}
        </div>
      );
    },
);

import { ConnectionPanel } from "../components/step-attach-flows-connection-panel";

const _noop = jest.fn();

const defaultProps = {
  connectionTab: "available" as const,
  onTabChange: jest.fn(),
  connections: [] as ConnectionItem[],
  selectedConnections: new Set<string>(),
  onToggleConnection: jest.fn(),
  newConnectionName: "",
  onNameChange: jest.fn(),
  envVars: [{ id: "ev-1", key: "", value: "" }] as EnvVarEntry[],
  detectedVarCount: 0,
  globalVariableOptions: [] as string[],
  onEnvVarChange: jest.fn(),
  onEnvVarSelectGlobalVar: jest.fn(),
  onAddEnvVar: jest.fn(),
  onChangeFlow: jest.fn(),
  onSkipConnection: jest.fn(),
  onAttachConnection: jest.fn(),
  onCreateConnection: jest.fn(),
  isDuplicateName: false,
};

function renderPanel(overrides: Partial<typeof defaultProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(<ConnectionPanel {...props} />);
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tab toggle
// ---------------------------------------------------------------------------

describe("Tab toggle", () => {
  it("renders Available Connections and Create Connection tabs", () => {
    renderPanel();
    expect(screen.getByText("Available Connections")).toBeInTheDocument();
    expect(screen.getByText("Create Connection")).toBeInTheDocument();
  });

  it("calls onTabChange when switching tabs", async () => {
    const user = userEvent.setup();
    const onTabChange = jest.fn();
    renderPanel({ onTabChange });

    await user.click(screen.getByText("Create Connection"));
    expect(onTabChange).toHaveBeenCalledWith("create");
  });
});

// ---------------------------------------------------------------------------
// Available tab — empty state
// ---------------------------------------------------------------------------

describe("Available tab — empty state", () => {
  it("shows empty state when no connections exist", () => {
    renderPanel({ connections: [] });
    expect(screen.getByText("No connections yet")).toBeInTheDocument();
    expect(
      screen.getByText("Create your first connection"),
    ).toBeInTheDocument();
  });

  it("clicking 'Create your first connection' switches to create tab", async () => {
    const user = userEvent.setup();
    const onTabChange = jest.fn();
    renderPanel({ connections: [], onTabChange });

    await user.click(screen.getByText("Create your first connection"));
    expect(onTabChange).toHaveBeenCalledWith("create");
  });
});

// ---------------------------------------------------------------------------
// Available tab — with connections
// ---------------------------------------------------------------------------

describe("Available tab — with connections", () => {
  const connections: ConnectionItem[] = [
    {
      id: "conn-1",
      connectionId: "conn-1",
      name: "Prod Connection",
      variableCount: 0,
      isNew: false,
      environmentVariables: {},
    },
    {
      id: "conn-2",
      connectionId: "conn-2",
      name: "New Connection",
      variableCount: 1,
      isNew: true,
      environmentVariables: { KEY: "val" },
    },
  ];

  it("renders connection items", () => {
    renderPanel({ connections });
    expect(screen.getByText("Prod Connection")).toBeInTheDocument();
    expect(screen.getByText("New Connection")).toBeInTheDocument();
  });

  it("shows search input", () => {
    renderPanel({ connections });
    expect(
      screen.getByPlaceholderText("Search connections..."),
    ).toBeInTheDocument();
  });

  it("filters connections by search query", async () => {
    const user = userEvent.setup();
    renderPanel({ connections });

    await user.type(
      screen.getByPlaceholderText("Search connections..."),
      "Prod",
    );
    expect(screen.getByText("Prod Connection")).toBeInTheDocument();
    expect(screen.queryByText("New Connection")).not.toBeInTheDocument();
  });

  it("shows no-match message for unmatched search", async () => {
    const user = userEvent.setup();
    renderPanel({ connections });

    await user.type(
      screen.getByPlaceholderText("Search connections..."),
      "zzz",
    );
    expect(screen.getByText(/No connections match/)).toBeInTheDocument();
  });

  it("calls onToggleConnection when clicking a connection", async () => {
    const user = userEvent.setup();
    const onToggle = jest.fn();
    renderPanel({ connections, onToggleConnection: onToggle });

    await user.click(screen.getByText("Prod Connection"));
    expect(onToggle).toHaveBeenCalledWith("conn-1");
  });

  it("sorts new connections to the top", () => {
    renderPanel({ connections });
    const items = screen.getAllByText(/Connection/);
    // "New Connection" (isNew=true) should appear before "Prod Connection"
    expect(items[0].textContent).toContain("New Connection");
  });
});

// ---------------------------------------------------------------------------
// Create tab — form
// ---------------------------------------------------------------------------

describe("Create tab — form", () => {
  it("renders connection name input", () => {
    renderPanel({ connectionTab: "create" });
    expect(
      screen.getByPlaceholderText("e.g., SALES_BOT_PROD"),
    ).toBeInTheDocument();
  });

  it("renders environment variable key/value row", () => {
    renderPanel({
      connectionTab: "create",
      envVars: [{ id: "ev-1", key: "", value: "" }],
    });
    expect(screen.getByPlaceholderText("Key")).toBeInTheDocument();
  });

  it("calls onNameChange on name input", async () => {
    const user = userEvent.setup();
    const onNameChange = jest.fn();
    renderPanel({ connectionTab: "create", onNameChange });

    await user.type(screen.getByPlaceholderText("e.g., SALES_BOT_PROD"), "A");
    expect(onNameChange).toHaveBeenCalled();
  });

  it("calls onAddEnvVar when add variable button is clicked", async () => {
    const user = userEvent.setup();
    const onAddEnvVar = jest.fn();
    renderPanel({ connectionTab: "create", onAddEnvVar });

    await user.click(screen.getByText("+ Add variable"));
    expect(onAddEnvVar).toHaveBeenCalled();
  });

  it("shows detected variable count message", () => {
    renderPanel({ connectionTab: "create", detectedVarCount: 3 });
    expect(
      screen.getByText(
        "3 variables auto-detected from the selected flow version.",
      ),
    ).toBeInTheDocument();
  });

  it("shows singular variable count message for 1 variable", () => {
    renderPanel({ connectionTab: "create", detectedVarCount: 1 });
    expect(
      screen.getByText(
        "1 variable auto-detected from the selected flow version.",
      ),
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Duplicate name detection
// ---------------------------------------------------------------------------

describe("Duplicate name detection", () => {
  it("shows duplicate name error", () => {
    renderPanel({
      connectionTab: "create",
      newConnectionName: "Existing",
      isDuplicateName: true,
    });
    expect(
      screen.getByText("A connection with this name already exists."),
    ).toBeInTheDocument();
  });

  it("does not show error when name is unique", () => {
    renderPanel({
      connectionTab: "create",
      newConnectionName: "Unique",
      isDuplicateName: false,
    });
    expect(
      screen.queryByText("A connection with this name already exists."),
    ).not.toBeInTheDocument();
  });

  it("disables Create Connection footer button when name is duplicate", () => {
    renderPanel({
      connectionTab: "create",
      newConnectionName: "Existing",
      isDuplicateName: true,
    });
    expect(screen.getByTestId("connection-create")).toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Footer buttons
// ---------------------------------------------------------------------------

describe("Footer buttons", () => {
  it("renders all footer buttons via data-testid", () => {
    renderPanel();
    expect(screen.getByTestId("connection-change-flow")).toBeInTheDocument();
    expect(screen.getByTestId("connection-skip")).toBeInTheDocument();
    expect(screen.getByTestId("connection-attach")).toBeInTheDocument();
  });

  it("Attach is disabled when no connections selected", () => {
    renderPanel({ selectedConnections: new Set() });
    expect(screen.getByTestId("connection-attach")).toBeDisabled();
  });

  it("Attach is enabled when connections are selected", () => {
    renderPanel({ selectedConnections: new Set(["conn-1"]) });
    expect(screen.getByTestId("connection-attach")).not.toBeDisabled();
  });

  it("Create is disabled when name is empty", () => {
    renderPanel({ connectionTab: "create", newConnectionName: "" });
    expect(screen.getByTestId("connection-create")).toBeDisabled();
  });

  it("Create is enabled when name is provided", () => {
    renderPanel({ connectionTab: "create", newConnectionName: "MyConn" });
    expect(screen.getByTestId("connection-create")).not.toBeDisabled();
  });

  it("calls onChangeFlow when Change Flow is clicked", async () => {
    const user = userEvent.setup();
    const onChangeFlow = jest.fn();
    renderPanel({ onChangeFlow });

    await user.click(screen.getByTestId("connection-change-flow"));
    expect(onChangeFlow).toHaveBeenCalled();
  });

  it("calls onSkipConnection when Skip is clicked", async () => {
    const user = userEvent.setup();
    const onSkip = jest.fn();
    renderPanel({ onSkipConnection: onSkip });

    await user.click(screen.getByTestId("connection-skip"));
    expect(onSkip).toHaveBeenCalled();
  });

  it("calls onAttachConnection when Attach is clicked", async () => {
    const user = userEvent.setup();
    const onAttach = jest.fn();
    renderPanel({
      selectedConnections: new Set(["conn-1"]),
      onAttachConnection: onAttach,
    });

    await user.click(screen.getByTestId("connection-attach"));
    expect(onAttach).toHaveBeenCalled();
  });

  it("calls onCreateConnection when Create is clicked", async () => {
    const user = userEvent.setup();
    const onCreate = jest.fn();
    renderPanel({
      connectionTab: "create",
      newConnectionName: "New",
      onCreateConnection: onCreate,
    });

    await user.click(screen.getByTestId("connection-create"));
    expect(onCreate).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Global variable options
// ---------------------------------------------------------------------------

describe("Global variable options", () => {
  it("renders global variable dropdown in env var row when options available", () => {
    renderPanel({
      connectionTab: "create",
      globalVariableOptions: ["MY_SECRET", "DB_PASS"],
      envVars: [{ id: "ev-1", key: "TEST_KEY", value: "" }],
    });
    expect(screen.getByTestId("select-env-val-ev-1")).toBeInTheDocument();
  });
});
