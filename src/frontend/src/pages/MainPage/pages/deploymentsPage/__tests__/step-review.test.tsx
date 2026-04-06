import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ConnectionItem } from "../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

let mockIsEditMode = false;
let mockDeploymentType = "agent";
let mockDeploymentName = "My Agent";
let mockSelectedLlm = "granite-13b-chat";
let mockConnections: ConnectionItem[] = [];
let mockSelectedVersionByFlow = new Map<
  string,
  { versionId: string; versionTag: string }
>();
let mockToolNameByFlow = new Map<string, string>();
const mockSetToolNameByFlow = jest.fn();
let mockAttachedConnectionByFlow = new Map<string, string[]>();
let mockRemovedFlowIds = new Set<string>();

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: () => ({
    isEditMode: mockIsEditMode,
    deploymentType: mockDeploymentType,
    deploymentName: mockDeploymentName,
    selectedLlm: mockSelectedLlm,
    connections: mockConnections,
    selectedVersionByFlow: mockSelectedVersionByFlow,
    toolNameByFlow: mockToolNameByFlow,
    setToolNameByFlow: mockSetToolNameByFlow,
    attachedConnectionByFlow: mockAttachedConnectionByFlow,
    removedFlowIds: mockRemovedFlowIds,
  }),
}));

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: () => "folder-1",
}));

let mockFlowsData: Array<{
  id: string;
  name: string;
  folder_id: string;
  is_component: boolean;
}> = [];

jest.mock(
  "@/controllers/API/queries/flows/use-get-refresh-flows-query",
  () => ({
    useGetRefreshFlowsQuery: () => ({
      data: mockFlowsData,
    }),
  }),
);

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import StepReview from "../components/step-review";

beforeEach(() => {
  jest.clearAllMocks();
  mockIsEditMode = false;
  mockDeploymentType = "agent";
  mockDeploymentName = "My Agent";
  mockSelectedLlm = "granite-13b-chat";
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
});

// ---------------------------------------------------------------------------
// Two-column layout
// ---------------------------------------------------------------------------

describe("Two-column layout", () => {
  it("renders the Review & Confirm heading", () => {
    render(<StepReview />);
    expect(screen.getByText("Review & Confirm")).toBeInTheDocument();
  });

  it("shows deployment type", () => {
    render(<StepReview />);
    expect(screen.getByText("agent")).toBeInTheDocument();
  });

  it("shows deployment name", () => {
    render(<StepReview />);
    expect(screen.getByText("My Agent")).toBeInTheDocument();
  });

  it("shows selected LLM model", () => {
    render(<StepReview />);
    expect(screen.getByText("granite-13b-chat")).toBeInTheDocument();
  });

  it("shows dash when no flows attached", () => {
    render(<StepReview />);
    // The "Attached Flows" column should show "—"
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("shows dash when deployment name is empty", () => {
    mockDeploymentName = "";
    render(<StepReview />);
    // At least one "—" for the empty name
    expect(screen.getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("does not show Model row when no LLM is selected", () => {
    mockSelectedLlm = "";
    render(<StepReview />);
    expect(screen.queryByText("granite-13b-chat")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Attached flows display
// ---------------------------------------------------------------------------

describe("Attached flows display", () => {
  beforeEach(() => {
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "v1-id", versionTag: "v1" }],
    ]);
  });

  it("shows attached flow name and version badge", () => {
    render(<StepReview />);
    // Flow name appears in both Attached Flows column and config section
    expect(screen.getAllByText("Sales Flow").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("v1").length).toBeGreaterThanOrEqual(1);
  });

  it("shows multiple attached flows", () => {
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "v1-id", versionTag: "v1" }],
      ["flow-2", { versionId: "v2-id", versionTag: "v3" }],
    ]);
    render(<StepReview />);
    // Flow names appear in both the Attached Flows column and the config section
    expect(screen.getAllByText("Sales Flow").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Support Flow").length).toBeGreaterThanOrEqual(
      1,
    );
  });

  it("shows Unknown for flows not found in flow data", () => {
    mockSelectedVersionByFlow = new Map([
      ["flow-missing", { versionId: "v1-id", versionTag: "v1" }],
    ]);
    render(<StepReview />);
    expect(screen.getAllByText("Unknown").length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// Tool name inline editing
// ---------------------------------------------------------------------------

describe("Tool name inline editing", () => {
  beforeEach(() => {
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "v1-id", versionTag: "v1" }],
    ]);
  });

  it("shows flow name as tool name when no custom name is set", () => {
    render(<StepReview />);
    // The tool name defaults to flowName
    expect(screen.getAllByText("Sales Flow").length).toBeGreaterThanOrEqual(1);
  });

  it("shows custom tool name when set", () => {
    mockToolNameByFlow = new Map([["flow-1", "Custom Tool"]]);
    render(<StepReview />);
    expect(screen.getByText("Custom Tool")).toBeInTheDocument();
  });

  it("renders edit button for tool name", () => {
    render(<StepReview />);
    expect(screen.getByTestId("edit-tool-name")).toBeInTheDocument();
  });

  it("enters editing mode when edit button is clicked", async () => {
    const user = userEvent.setup();
    render(<StepReview />);

    await user.click(screen.getByTestId("edit-tool-name"));
    expect(screen.getByTestId("tool-name-input")).toBeInTheDocument();
  });

  it("confirms edit on Enter key", async () => {
    const user = userEvent.setup();
    render(<StepReview />);

    await user.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    await user.clear(input);
    await user.type(input, "New Name{Enter}");

    expect(mockSetToolNameByFlow).toHaveBeenCalled();
  });

  it("cancels edit on Escape key", async () => {
    const user = userEvent.setup();
    mockToolNameByFlow = new Map([["flow-1", "Original"]]);
    render(<StepReview />);

    await user.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    await user.clear(input);
    await user.type(input, "Changed{Escape}");

    // Should revert — no setToolNameByFlow call after Escape
    expect(screen.queryByTestId("tool-name-input")).not.toBeInTheDocument();
    expect(screen.getByText("Original")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Connection display with masked env vars
// ---------------------------------------------------------------------------

describe("Connection display with masked env vars", () => {
  beforeEach(() => {
    mockSelectedVersionByFlow = new Map([
      ["flow-1", { versionId: "v1-id", versionTag: "v1" }],
    ]);
    mockConnections = [
      {
        id: "conn-1",
        name: "Prod Connection",
        variableCount: 2,
        isNew: true,
        environmentVariables: {
          API_KEY: "secret-value", // pragma: allowlist secret
          DB_URL: "postgres://...",
        },
      },
      {
        id: "conn-2",
        name: "Existing Connection",
        variableCount: 0,
        isNew: false,
        environmentVariables: {},
      },
    ];
    mockAttachedConnectionByFlow = new Map([["flow-1", ["conn-1", "conn-2"]]]);
  });

  it("shows new connections section", () => {
    render(<StepReview />);
    expect(screen.getByText("New Connections")).toBeInTheDocument();
    expect(screen.getByText("Prod Connection")).toBeInTheDocument();
  });

  it("shows existing connections section", () => {
    render(<StepReview />);
    expect(screen.getByText("Existing Connections")).toBeInTheDocument();
    expect(screen.getByText("Existing Connection")).toBeInTheDocument();
  });

  it("masks environment variable values", () => {
    render(<StepReview />);
    expect(screen.getByText("API_KEY")).toBeInTheDocument();
    expect(screen.getByText("DB_URL")).toBeInTheDocument();
    // Values should be masked
    expect(screen.getAllByText("••••••••").length).toBe(2);
    // Actual values should NOT appear
    expect(screen.queryByText("secret-value")).not.toBeInTheDocument();
    expect(screen.queryByText("postgres://...")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Detaching section (edit mode)
// ---------------------------------------------------------------------------

describe("Detaching section (edit mode)", () => {
  it("does not show detaching section in create mode", () => {
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepReview />);
    expect(screen.queryByText("Detaching")).not.toBeInTheDocument();
  });

  it("shows detaching section in edit mode with removed flows", () => {
    mockIsEditMode = true;
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepReview />);
    expect(screen.getByText("Detaching")).toBeInTheDocument();
    expect(screen.getByText("removing")).toBeInTheDocument();
  });

  it("does not show detaching section when no flows are removed", () => {
    mockIsEditMode = true;
    mockRemovedFlowIds = new Set();
    render(<StepReview />);
    expect(screen.queryByText("Detaching")).not.toBeInTheDocument();
  });

  it("shows flow name in detaching section", () => {
    mockIsEditMode = true;
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepReview />);
    expect(screen.getByText("Sales Flow")).toBeInTheDocument();
  });

  it("shows Unknown flow for unrecognized flow IDs", () => {
    mockIsEditMode = true;
    mockRemovedFlowIds = new Set(["flow-unknown"]);
    render(<StepReview />);
    expect(screen.getByText("Unknown flow")).toBeInTheDocument();
  });

  it("shows help text about detaching", () => {
    mockIsEditMode = true;
    mockRemovedFlowIds = new Set(["flow-1"]);
    render(<StepReview />);
    expect(
      screen.getByText(/These tools will be detached from the agent/),
    ).toBeInTheDocument();
  });
});
