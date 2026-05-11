import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionItem } from "../types";

// ---------------------------------------------------------------------------
// Mocks — stepper context
// ---------------------------------------------------------------------------

let mockIsEditMode = false;
let mockInitialFlowId: string | undefined;
let mockSelectedInstance: { id: string } | null = { id: "inst-1" };
let mockConnections: ConnectionItem[] = [];
const mockSetConnections = jest.fn();
let mockSelectedVersionByFlow = new Map<
  string,
  { versionId: string; versionTag: string }
>();
const mockHandleSelectVersion = jest.fn();
let mockToolNameByFlow = new Map<string, string>();
const mockSetToolNameByFlow = jest.fn();
let mockAttachedConnectionByFlow = new Map<string, string[]>();
const mockSetAttachedConnectionByFlow = jest.fn();
let mockRemovedFlowIds = new Set<string>();
const mockHandleRemoveAttachedFlow = jest.fn();
const mockHandleUndoRemoveFlow = jest.fn();

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: () => ({
    isEditMode: mockIsEditMode,
    initialFlowId: mockInitialFlowId,
    selectedInstance: mockSelectedInstance,
    connections: mockConnections,
    setConnections: mockSetConnections,
    selectedVersionByFlow: mockSelectedVersionByFlow,
    handleSelectVersion: mockHandleSelectVersion,
    toolNameByFlow: mockToolNameByFlow,
    setToolNameByFlow: mockSetToolNameByFlow,
    attachedConnectionByFlow: mockAttachedConnectionByFlow,
    setAttachedConnectionByFlow: mockSetAttachedConnectionByFlow,
    removedFlowIds: mockRemovedFlowIds,
    handleRemoveAttachedFlow: mockHandleRemoveAttachedFlow,
    handleUndoRemoveFlow: mockHandleUndoRemoveFlow,
  }),
}));

// ---------------------------------------------------------------------------
// Mocks — route & stores
// ---------------------------------------------------------------------------

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: () => "folder-1",
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

// ---------------------------------------------------------------------------
// Mocks — API hooks
// ---------------------------------------------------------------------------

let mockFlowsData: Array<{
  id: string;
  name: string;
  folder_id: string;
  is_component: boolean;
  icon?: string;
}> = [];

jest.mock(
  "@/controllers/API/queries/flows/use-get-refresh-flows-query",
  () => ({
    useGetRefreshFlowsQuery: () => ({
      data: mockFlowsData,
    }),
  }),
);

let mockConfigsData: {
  configs: Array<{ id: string; name: string }>;
} | null = null;

jest.mock(
  "@/controllers/API/queries/deployments/use-get-deployment-configs",
  () => ({
    useGetDeploymentConfigs: () => ({
      data: mockConfigsData,
    }),
  }),
);

let mockVersionsData: {
  entries: Array<{
    id: string;
    version_tag: string;
    created_at: string;
  }>;
} | null = null;
let mockIsLoadingVersions = false;

jest.mock(
  "@/controllers/API/queries/flow-version/use-get-flow-versions",
  () => ({
    useGetFlowVersions: () => ({
      data: mockVersionsData,
      isLoading: mockIsLoadingVersions,
    }),
  }),
);

const mockDetectEnvVars = jest.fn().mockResolvedValue({ variables: [] });

jest.mock(
  "@/controllers/API/queries/variables/use-post-detect-env-vars",
  () => ({
    usePostDetectEnvVars: () => ({
      mutateAsync: mockDetectEnvVars,
    }),
  }),
);

jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({
    data: [{ name: "GLOBAL_SECRET" }, { name: "DB_PASS" }],
  }),
}));

// ---------------------------------------------------------------------------
// UI component mocks
// ---------------------------------------------------------------------------

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
            data-testid={`input-${id}`}
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
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

import StepAttachFlows from "../components/step-attach-flows";

beforeEach(() => {
  jest.clearAllMocks();
  mockIsEditMode = false;
  mockInitialFlowId = undefined;
  mockSelectedInstance = { id: "inst-1" };
  mockConnections = [];
  mockSelectedVersionByFlow = new Map();
  mockToolNameByFlow = new Map();
  mockAttachedConnectionByFlow = new Map();
  mockRemovedFlowIds = new Set();
  mockFlowsData = [
    {
      id: "flow-1",
      name: "Sales Flow",
      folder_id: "folder-1",
      is_component: false,
    },
    {
      id: "flow-2",
      name: "Support Flow",
      folder_id: "folder-1",
      is_component: false,
    },
  ];
  mockConfigsData = null;
  mockVersionsData = {
    entries: [
      { id: "ver-1", version_tag: "v1", created_at: "2025-06-01T00:00:00Z" },
      { id: "ver-2", version_tag: "v2", created_at: "2025-06-02T00:00:00Z" },
    ],
  };
  mockIsLoadingVersions = false;
});

// ---------------------------------------------------------------------------
// Three-panel layout rendering
// ---------------------------------------------------------------------------

describe("Three-panel layout rendering", () => {
  it("renders the Attach Flows heading", () => {
    render(<StepAttachFlows />);
    expect(screen.getByText("Attach Flows")).toBeInTheDocument();
  });

  it("renders the Available Flows panel header", () => {
    render(<StepAttachFlows />);
    expect(screen.getByText("Available Flows")).toBeInTheDocument();
  });

  it("renders flow items in the list", () => {
    render(<StepAttachFlows />);
    expect(screen.getByTestId("flow-item-flow-1")).toBeInTheDocument();
    expect(screen.getByTestId("flow-item-flow-2")).toBeInTheDocument();
  });

  it("filters out components from flow list", () => {
    mockFlowsData = [
      ...mockFlowsData,
      {
        id: "comp-1",
        name: "My Component",
        folder_id: "folder-1",
        is_component: true,
      },
    ];
    render(<StepAttachFlows />);
    expect(screen.queryByText("My Component")).not.toBeInTheDocument();
  });

  it("filters out flows from other folders", () => {
    mockFlowsData = [
      ...mockFlowsData,
      {
        id: "other-flow",
        name: "Other Folder Flow",
        folder_id: "folder-2",
        is_component: false,
      },
    ];
    render(<StepAttachFlows />);
    expect(screen.queryByText("Other Folder Flow")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Version panel
// ---------------------------------------------------------------------------

describe("Version panel", () => {
  it("shows version panel with flow name when flow is selected", () => {
    render(<StepAttachFlows />);
    // First flow is selected by default — name appears in both flow list and version panel
    expect(screen.getAllByText("Sales Flow").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText("Select a version to attach to this deployment"),
    ).toBeInTheDocument();
  });

  it("renders version items", () => {
    render(<StepAttachFlows />);
    expect(screen.getByTestId("version-item-ver-1")).toBeInTheDocument();
    expect(screen.getByTestId("version-item-ver-2")).toBeInTheDocument();
  });

  it("shows loading state for versions", () => {
    mockIsLoadingVersions = true;
    render(<StepAttachFlows />);
    expect(screen.getByText("Loading versions...")).toBeInTheDocument();
  });

  it("shows empty state when no versions available", () => {
    mockVersionsData = { entries: [] };
    render(<StepAttachFlows />);
    expect(screen.getByText("No versions found")).toBeInTheDocument();
  });

  it("shows ATTACHED badge for already-attached versions", () => {
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
    ]);
    render(<StepAttachFlows />);
    expect(screen.getAllByText("ATTACHED").length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Flow selection triggers version panel
// ---------------------------------------------------------------------------

describe("Flow selection", () => {
  it("selecting a different flow shows its name in the version panel", async () => {
    const user = userEvent.setup();
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("flow-item-flow-2"));
    // Flow name appears in both the flow list and the version panel header
    expect(screen.getAllByText("Support Flow").length).toBeGreaterThanOrEqual(
      1,
    );
  });
});

// ---------------------------------------------------------------------------
// Connection panel toggle
// ---------------------------------------------------------------------------

describe("Connection panel toggle", () => {
  it("switches to connection panel after clicking a version", async () => {
    const user = userEvent.setup();
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      expect(
        screen.getByText("Select or Create New Connection"),
      ).toBeInTheDocument();
    });
  });

  it("detects env vars when a version is selected", async () => {
    const user = userEvent.setup();
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      expect(mockDetectEnvVars).toHaveBeenCalledWith({
        flow_version_ids: ["ver-1"],
      });
    });
  });

  it("defaults to create tab when no existing connections", async () => {
    const user = userEvent.setup();
    mockConnections = [];
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      expect(
        screen.getByPlaceholderText("e.g., SALES_BOT_PROD"),
      ).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Existing connections seeding
// ---------------------------------------------------------------------------

describe("Existing connections seeding", () => {
  it("seeds connections from provider configs", () => {
    mockConfigsData = {
      configs: [
        { id: "cfg-1", name: "Production Config" },
        { id: "cfg-2", name: "Staging Config" },
      ],
    };
    render(<StepAttachFlows />);
    expect(mockSetConnections).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// Edit mode features
// ---------------------------------------------------------------------------

describe("Edit mode features", () => {
  beforeEach(() => {
    mockIsEditMode = true;
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
    ]);
  });

  it("shows ATTACHED badge for attached flows in flow list", () => {
    render(<StepAttachFlows />);
    expect(screen.getAllByText("ATTACHED").length).toBeGreaterThanOrEqual(1);
  });

  it("shows detach button for attached flows", () => {
    render(<StepAttachFlows />);
    expect(screen.getByTestId("detach-flow-flow-1")).toBeInTheDocument();
  });

  it("calls handleRemoveAttachedFlow when detach is clicked", async () => {
    const user = userEvent.setup();
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("detach-flow-flow-1"));
    expect(mockHandleRemoveAttachedFlow).toHaveBeenCalledWith("flow-1");
  });

  it("shows REMOVED badge for removed flows", () => {
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepAttachFlows />);
    expect(screen.getByText("REMOVED")).toBeInTheDocument();
  });

  it("shows undo button for removed flows", () => {
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepAttachFlows />);
    expect(screen.getByTestId("undo-remove-flow-flow-1")).toBeInTheDocument();
  });

  it("calls handleUndoRemoveFlow when undo is clicked", async () => {
    const user = userEvent.setup();
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("undo-remove-flow-flow-1"));
    expect(mockHandleUndoRemoveFlow).toHaveBeenCalledWith("flow-1");
  });

  it("sorts attached flows to the top", () => {
    render(<StepAttachFlows />);
    const flowItems = screen.getAllByTestId(/^flow-item-/);
    // flow-1 is attached, so it should appear first
    expect(flowItems[0]).toHaveAttribute("data-testid", "flow-item-flow-1");
  });
});

// ---------------------------------------------------------------------------
// Detected env vars auto-population
// ---------------------------------------------------------------------------

describe("Detected env vars auto-population", () => {
  it("populates env var rows with keys and global variable selections from detection", async () => {
    const user = userEvent.setup();
    mockDetectEnvVars.mockResolvedValueOnce({
      variables: ["OPENAI_API_KEY", "DB_PASS"],
    });
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      const keyInputs = screen.getAllByPlaceholderText("Key");
      expect(keyInputs).toHaveLength(2);
      expect(keyInputs[0]).toHaveValue("OPENAI_API_KEY");
      expect(keyInputs[1]).toHaveValue("DB_PASS");
    });

    const selects = screen.getAllByTestId(/^select-env-val-/);
    expect(selects).toHaveLength(2);
  });

  it("renders empty row when detection returns no variables", async () => {
    const user = userEvent.setup();
    mockDetectEnvVars.mockResolvedValueOnce({ variables: [] });
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      const keyInputs = screen.getAllByPlaceholderText("Key");
      expect(keyInputs).toHaveLength(1);
      expect(keyInputs[0]).toHaveValue("");
    });
  });

  it("renders empty row when detection fails", async () => {
    const user = userEvent.setup();
    mockDetectEnvVars.mockRejectedValueOnce(new Error("network error"));
    render(<StepAttachFlows />);

    await user.click(screen.getByTestId("version-item-ver-1"));

    await waitFor(() => {
      expect(
        screen.getByText("Select or Create New Connection"),
      ).toBeInTheDocument();
    });

    const keyInputs = screen.getAllByPlaceholderText("Key");
    expect(keyInputs).toHaveLength(1);
    expect(keyInputs[0]).toHaveValue("");
  });

  it("auto-detects env vars for pre-selected flow version on mount", async () => {
    const user = userEvent.setup();
    mockInitialFlowId = "flow-1";
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
    ]);
    mockDetectEnvVars.mockResolvedValueOnce({
      variables: ["GLOBAL_SECRET"],
    });

    render(<StepAttachFlows />);

    await waitFor(() => {
      expect(mockDetectEnvVars).toHaveBeenCalledWith({
        flow_version_ids: ["ver-1"],
      });
    });

    // The pre-selected useEffect switches to the connection panel but defaults
    // to the "available" tab. Switch to "Create Connection" to see env var rows.
    await user.click(screen.getByText("Create Connection"));

    await waitFor(() => {
      const keyInputs = screen.getAllByPlaceholderText("Key");
      expect(keyInputs).toHaveLength(1);
      expect(keyInputs[0]).toHaveValue("GLOBAL_SECRET");
    });
  });
});
