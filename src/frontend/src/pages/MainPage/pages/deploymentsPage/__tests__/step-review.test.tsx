import { fireEvent, render, screen, within } from "@testing-library/react";
import { useCheckToolNames } from "@/controllers/API/queries/deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import StepReview from "../components/step-review";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";
import type { ConnectionItem } from "../types";

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: jest.fn(),
}));

jest.mock("@/controllers/API/queries/deployments", () => ({
  useCheckToolNames: jest.fn(() => ({ data: undefined })),
}));

const mockedUseCheckToolNames = useCheckToolNames as jest.MockedFunction<
  typeof useCheckToolNames
>;

jest.mock(
  "@/controllers/API/queries/flows/use-get-refresh-flows-query",
  () => ({
    useGetRefreshFlowsQuery: jest.fn(),
  }),
);

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: jest.fn(),
}));

jest.mock("react-router-dom", () => ({
  useParams: () => ({ folderId: "folder-1" }),
}));

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

const mockedUseDeploymentStepper = useDeploymentStepper as jest.MockedFunction<
  typeof useDeploymentStepper
>;
const mockedUseGetRefreshFlowsQuery =
  useGetRefreshFlowsQuery as jest.MockedFunction<
    typeof useGetRefreshFlowsQuery
  >;
const mockedUseFolderStore = useFolderStore as jest.MockedFunction<
  typeof useFolderStore
>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildBaseStepper(overrides: Record<string, unknown> = {}) {
  return {
    isEditMode: false,
    deploymentType: "agent",
    deploymentName: "Agent One",
    selectedLlm: "meta-llama/llama-3-3-70b-instruct",
    connections: [],
    selectedVersionByFlow: new Map([
      ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
    ]),
    toolNameByFlow: new Map<string, string>(),
    setToolNameByFlow: jest.fn(),
    attachedConnectionByFlow: new Map(),
    removedFlowIds: new Set(),
    selectedInstance: null,
    preExistingFlowIds: new Set<string>(),
    initialToolNameByFlow: new Map<string, string>(),
    setHasToolNameErrors: jest.fn(),
    ...overrides,
  } as never;
}

function setupFolderStore() {
  mockedUseFolderStore.mockImplementation((selector) =>
    selector({ myCollectionId: "folder-1" } as never),
  );
}

function setupFlowsQuery(
  flows: Array<{ id: string; name: string; folder_id: string }> = [],
) {
  mockedUseGetRefreshFlowsQuery.mockReturnValue({
    data: flows,
  } as never);
}

function defaultStepperValues(
  overrides: Record<string, unknown> = {},
): Record<string, unknown> {
  return {
    isEditMode: false,
    deploymentType: "agent",
    deploymentName: "Agent One",
    selectedLlm: "meta-llama/llama-3-3-70b-instruct",
    connections: [] as ConnectionItem[],
    selectedVersionByFlow: new Map(),
    toolNameByFlow: new Map(),
    setToolNameByFlow: jest.fn(),
    attachedConnectionByFlow: new Map(),
    removedFlowIds: new Set<string>(),
    selectedInstance: null,
    preExistingFlowIds: new Set<string>(),
    initialToolNameByFlow: new Map<string, string>(),
    setHasToolNameErrors: jest.fn(),
    ...overrides,
  };
}

function setupStepper(overrides: Record<string, unknown> = {}) {
  const values = defaultStepperValues(overrides);
  mockedUseDeploymentStepper.mockReturnValue(values as never);
  return values;
}

function setup(
  stepperOverrides: Record<string, unknown> = {},
  flows: Array<{ id: string; name: string; folder_id: string }> = [],
) {
  setupFolderStore();
  setupFlowsQuery(flows);
  const values = setupStepper(stepperOverrides);
  render(<StepReview />);
  return values;
}

// ---------------------------------------------------------------------------
// Tool name editing
// ---------------------------------------------------------------------------

describe("StepReview tool name editing", () => {
  beforeEach(() => {
    mockedUseFolderStore.mockImplementation((selector) =>
      selector({ myCollectionId: "folder-1" } as never),
    );
    mockedUseGetRefreshFlowsQuery.mockReturnValue({
      data: [
        { id: "flow-1", name: "New Flow", folder_id: "folder-1" },
        { id: "flow-2", name: "Other Flow", folder_id: "folder-1" },
      ],
    } as never);
    mockedUseCheckToolNames.mockReturnValue({ data: undefined } as never);
  });

  it("persists tool name edits when input loses focus", () => {
    const setToolNameByFlow = jest.fn();
    mockedUseDeploymentStepper.mockReturnValue(
      buildBaseStepper({ setToolNameByFlow }),
    );

    render(<StepReview />);

    fireEvent.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    fireEvent.change(input, { target: { value: "My Tool Name" } });
    fireEvent.blur(input);

    expect(setToolNameByFlow).toHaveBeenCalled();
    const updater = setToolNameByFlow.mock.calls[0][0] as (
      prev: Map<string, string>,
    ) => Map<string, string>;
    const updated = updater(new Map());
    expect(updated.get("flow-1")).toBe("My Tool Name");
  });
});

// ---------------------------------------------------------------------------
// 1. Deployment summary display
// ---------------------------------------------------------------------------

describe("Deployment summary display", () => {
  it("renders a dash when deployment name is empty", () => {
    setup({ deploymentName: "" });

    // Two dashes: one for the empty name, one for empty attached flows
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
    // The name field dash is inside a span with text-foreground
    const nameDash = dashes.find(
      (el) => el.className.includes("text-foreground") && el.tagName === "SPAN",
    );
    expect(nameDash).toBeDefined();
  });

  it("does not render model row when selectedLlm is empty", () => {
    setup({ selectedLlm: "" });

    expect(screen.queryByText("Model")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2. Attached flows section
// ---------------------------------------------------------------------------

describe("Attached flows section", () => {
  it("shows dash when no flows are attached", () => {
    setup({
      selectedVersionByFlow: new Map(),
    });

    // The attached flows column renders "—" when empty
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("falls back to versionId when versionTag is empty", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "abc123", versionTag: "" }],
        ]),
      },
      [{ id: "flow-1", name: "Some Flow", folder_id: "folder-1" }],
    );

    const versionLabels = screen.getAllByText("abc123");
    expect(versionLabels.length).toBeGreaterThanOrEqual(1);
  });

  it("shows 'Unknown' for flows not found in flowsData", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-missing", { versionId: "ver-1", versionTag: "v1" }],
        ]),
      },
      [], // no flows in data
    );

    const unknowns = screen.getAllByText("Unknown");
    expect(unknowns.length).toBeGreaterThanOrEqual(1);
  });
});

// ---------------------------------------------------------------------------
// 3. Flow configuration section
// ---------------------------------------------------------------------------

describe("Flow configuration section", () => {
  it("shows custom tool name for a flow in the configuration section", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map([["flow-1", "Custom Tool"]]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    // The custom tool name is rendered next to the Wrench icon in configuration
    const wrenchIcon = screen.getByTestId("icon-Wrench");
    const configRow = wrenchIcon.closest(".flex.items-center.gap-2")!;
    expect(
      within(configRow as HTMLElement).getByText("Custom Tool"),
    ).toBeInTheDocument();

    // The flow name still appears in the sub-detail, not replaced by the tool name
    const configBlock = wrenchIcon.closest(".rounded-xl")!;
    expect(
      within(configBlock as HTMLElement).getByText("My Flow"),
    ).toBeInTheDocument();
  });

  it("shows flow name as placeholder when no custom tool name is set", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map(),
      },
      [{ id: "flow-1", name: "Default Name Flow", folder_id: "folder-1" }],
    );

    // The flow name appears in the attached column, in the EditableToolName
    // (as placeholder fallback), and in the config sub-detail = 3 total
    const nameInstances = screen.getAllByText("Default Name Flow");
    expect(nameInstances).toHaveLength(3);

    // Verify the EditableToolName specifically shows the flow name as placeholder
    const wrenchIcon = screen.getByTestId("icon-Wrench");
    const configRow = wrenchIcon.closest(".flex.items-center.gap-2")!;
    expect(
      within(configRow as HTMLElement).getByText("Default Name Flow"),
    ).toBeInTheDocument();
  });

  it("does not render configuration section when no flows selected", () => {
    setup({ selectedVersionByFlow: new Map() });

    expect(screen.queryByTestId("icon-Wrench")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 4. Connection details
// ---------------------------------------------------------------------------

describe("Connection details", () => {
  it("renders new connections with env var details", () => {
    const connections: ConnectionItem[] = [
      {
        id: "conn-new",
        connectionId: "conn-new",
        name: "New API Connection",
        variableCount: 1,
        isNew: true,
        environmentVariables: { API_KEY: "my-secret-key" },
      },
    ];

    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        connections,
        attachedConnectionByFlow: new Map([["flow-1", ["conn-new"]]]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    expect(screen.getByText("New Connections")).toBeInTheDocument();
    expect(screen.getByText("New API Connection")).toBeInTheDocument();
    expect(screen.getByText("API_KEY")).toBeInTheDocument();
  });

  it("masks env var values with masked characters", () => {
    const connections: ConnectionItem[] = [
      {
        id: "conn-new",
        connectionId: "conn-new",
        name: "New Connection",
        variableCount: 1,
        isNew: true,
        environmentVariables: { SECRET_KEY: "actual-secret-value" },
      },
    ];

    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        connections,
        attachedConnectionByFlow: new Map([["flow-1", ["conn-new"]]]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    expect(screen.getByText("••••••••")).toBeInTheDocument();
    expect(screen.queryByText("actual-secret-value")).not.toBeInTheDocument();
  });

  it("renders multiple env vars for a new connection", () => {
    const connections: ConnectionItem[] = [
      {
        id: "conn-new",
        connectionId: "conn-new",
        name: "Multi Var Conn",
        variableCount: 3,
        isNew: true,
        environmentVariables: {
          VAR_ONE: "val1",
          VAR_TWO: "val2",
          VAR_THREE: "val3",
        },
      },
    ];

    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        connections,
        attachedConnectionByFlow: new Map([["flow-1", ["conn-new"]]]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    expect(screen.getByText("VAR_ONE")).toBeInTheDocument();
    expect(screen.getByText("VAR_TWO")).toBeInTheDocument();
    expect(screen.getByText("VAR_THREE")).toBeInTheDocument();

    // Each env var gets its own masked value
    const maskedValues = screen.getAllByText("••••••••");
    expect(maskedValues).toHaveLength(3);
  });

  it("renders both existing and new connections for one flow", () => {
    const connections: ConnectionItem[] = [
      {
        id: "conn-existing",
        connectionId: "conn-existing",
        name: "Old Connection",
        variableCount: 0,
        isNew: false,
        environmentVariables: {},
      },
      {
        id: "conn-new",
        connectionId: "conn-new",
        name: "Fresh Connection",
        variableCount: 1,
        isNew: true,
        environmentVariables: { TOKEN: "abc" },
      },
    ];

    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        connections,
        attachedConnectionByFlow: new Map([
          ["flow-1", ["conn-existing", "conn-new"]],
        ]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    expect(screen.getByText("Existing Connections")).toBeInTheDocument();
    expect(screen.getByText("New Connections")).toBeInTheDocument();
    expect(screen.getByText("Old Connection")).toBeInTheDocument();
    expect(screen.getByText("Fresh Connection")).toBeInTheDocument();
  });

  it("does not render connection sections when flow has no connections", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        connections: [],
        attachedConnectionByFlow: new Map(),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    expect(screen.queryByText("Existing Connections")).not.toBeInTheDocument();
    expect(screen.queryByText("New Connections")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 5. Removal section (edit mode)
// ---------------------------------------------------------------------------

describe("Removal section (edit mode)", () => {
  it("shows detached flows in edit mode with removing badge", () => {
    setup(
      {
        isEditMode: true,
        removedFlowIds: new Set(["flow-removed"]),
        selectedVersionByFlow: new Map(),
      },
      [{ id: "flow-removed", name: "Removed Flow", folder_id: "folder-1" }],
    );

    expect(screen.getByText("Detaching")).toBeInTheDocument();
    expect(screen.getByText("Removed Flow")).toBeInTheDocument();
    expect(screen.getByText("removing")).toBeInTheDocument();
    expect(
      screen.getByText(
        "These tools will be detached from the agent. They will remain available on your provider tenant.",
      ),
    ).toBeInTheDocument();
  });

  it("shows 'Unknown flow' for removed flows not found in data", () => {
    setup(
      {
        isEditMode: true,
        removedFlowIds: new Set(["flow-unknown"]),
        selectedVersionByFlow: new Map(),
      },
      [],
    );

    expect(screen.getByText("Unknown flow")).toBeInTheDocument();
  });

  it("does not show removal section in create mode", () => {
    setup({
      isEditMode: false,
      removedFlowIds: new Set(["flow-1"]),
      selectedVersionByFlow: new Map(),
    });

    expect(screen.queryByText("Detaching")).not.toBeInTheDocument();
    expect(screen.queryByText("removing")).not.toBeInTheDocument();
  });

  it("does not show removal section when removedFlowIds is empty in edit mode", () => {
    setup({
      isEditMode: true,
      removedFlowIds: new Set(),
      selectedVersionByFlow: new Map(),
    });

    expect(screen.queryByText("Detaching")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. EditableToolName sub-component
// ---------------------------------------------------------------------------

describe("EditableToolName sub-component", () => {
  it("Enter key confirms edit", () => {
    const setToolNameByFlow = jest.fn();
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map(),
        setToolNameByFlow,
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    fireEvent.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    fireEvent.change(input, { target: { value: "Enter Tool" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(setToolNameByFlow).toHaveBeenCalled();
    const updater = setToolNameByFlow.mock.calls[0][0] as (
      prev: Map<string, string>,
    ) => Map<string, string>;
    const updated = updater(new Map());
    expect(updated.get("flow-1")).toBe("Enter Tool");
  });

  it("Escape key cancels edit and reverts to original value", () => {
    const setToolNameByFlow = jest.fn();
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map([["flow-1", "Original Name"]]),
        setToolNameByFlow,
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    fireEvent.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    fireEvent.change(input, { target: { value: "Changed Name" } });
    fireEvent.keyDown(input, { key: "Escape" });

    // Escape cancels so setToolNameByFlow should NOT have been called
    expect(setToolNameByFlow).not.toHaveBeenCalled();
    // Should be back in display mode showing original name
    expect(screen.getByText("Original Name")).toBeInTheDocument();
    expect(screen.queryByTestId("tool-name-input")).not.toBeInTheDocument();
  });

  it("click edit button activates edit mode", () => {
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map([["flow-1", "My Tool"]]),
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    // Before clicking: display mode, no input
    expect(screen.queryByTestId("tool-name-input")).not.toBeInTheDocument();
    expect(screen.getByText("My Tool")).toBeInTheDocument();

    // Click the edit button
    fireEvent.click(screen.getByTestId("edit-tool-name"));

    // After clicking: edit mode, input visible
    expect(screen.getByTestId("tool-name-input")).toBeInTheDocument();
  });

  it("empty name reverts (deletes) the tool name entry", () => {
    const setToolNameByFlow = jest.fn();
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map([["flow-1", "Existing Tool"]]),
        setToolNameByFlow,
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    fireEvent.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    fireEvent.change(input, { target: { value: "" } });
    fireEvent.blur(input);

    expect(setToolNameByFlow).toHaveBeenCalled();
    const updater = setToolNameByFlow.mock.calls[0][0] as (
      prev: Map<string, string>,
    ) => Map<string, string>;
    // Start with existing entry; saving empty should delete it
    const updated = updater(new Map([["flow-1", "Existing Tool"]]));
    expect(updated.has("flow-1")).toBe(false);
  });

  it("whitespace-only name is treated as empty and deletes the entry", () => {
    const setToolNameByFlow = jest.fn();
    setup(
      {
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
        ]),
        toolNameByFlow: new Map([["flow-1", "Some Name"]]),
        setToolNameByFlow,
      },
      [{ id: "flow-1", name: "My Flow", folder_id: "folder-1" }],
    );

    fireEvent.click(screen.getByTestId("edit-tool-name"));
    const input = screen.getByTestId("tool-name-input");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.blur(input);

    expect(setToolNameByFlow).toHaveBeenCalled();
    const updater = setToolNameByFlow.mock.calls[0][0] as (
      prev: Map<string, string>,
    ) => Map<string, string>;
    const updated = updater(new Map([["flow-1", "Some Name"]]));
    expect(updated.has("flow-1")).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// 7. Duplicate tool name detection (edit mode)
// ---------------------------------------------------------------------------

describe("StepReview duplicate tool name detection in edit mode", () => {
  beforeEach(() => {
    mockedUseFolderStore.mockImplementation((selector) =>
      selector({ myCollectionId: "folder-1" } as never),
    );
    mockedUseGetRefreshFlowsQuery.mockReturnValue({
      data: [
        { id: "flow-1", name: "New Flow", folder_id: "folder-1" },
        { id: "flow-2", name: "Other Flow", folder_id: "folder-1" },
      ],
    } as never);
  });

  it("shows provider duplicate error when pre-existing flow tool name is changed to an existing name", () => {
    const setHasToolNameErrors = jest.fn();
    mockedUseCheckToolNames.mockReturnValue({
      data: { existing_names: ["taken_tool"] },
    } as never);
    mockedUseDeploymentStepper.mockReturnValue(
      buildBaseStepper({
        isEditMode: true,
        preExistingFlowIds: new Set(["flow-1"]),
        initialToolNameByFlow: new Map([["flow-1", "original_tool"]]),
        toolNameByFlow: new Map([["flow-1", "taken_tool"]]),
        selectedInstance: { id: "inst-1" },
        setHasToolNameErrors,
      }),
    );

    render(<StepReview />);

    expect(
      screen.getByText("Edit tool name (already exists in provider)"),
    ).toBeInTheDocument();
    expect(setHasToolNameErrors).toHaveBeenCalledWith(true);
  });

  it("does not show error when pre-existing flow tool name is unchanged", () => {
    const setHasToolNameErrors = jest.fn();
    mockedUseCheckToolNames.mockReturnValue({
      data: { existing_names: ["original_tool"] },
    } as never);
    mockedUseDeploymentStepper.mockReturnValue(
      buildBaseStepper({
        isEditMode: true,
        preExistingFlowIds: new Set(["flow-1"]),
        initialToolNameByFlow: new Map([["flow-1", "original_tool"]]),
        toolNameByFlow: new Map([["flow-1", "original_tool"]]),
        selectedInstance: { id: "inst-1" },
        setHasToolNameErrors,
      }),
    );

    render(<StepReview />);

    expect(
      screen.queryByText("Edit tool name (already exists in provider)"),
    ).not.toBeInTheDocument();
  });

  it("shows batch duplicate error when two flows have the same renamed tool name", () => {
    const setHasToolNameErrors = jest.fn();
    mockedUseCheckToolNames.mockReturnValue({ data: undefined } as never);
    mockedUseDeploymentStepper.mockReturnValue(
      buildBaseStepper({
        isEditMode: true,
        selectedVersionByFlow: new Map([
          ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
          ["flow-2", { versionId: "ver-2", versionTag: "v2" }],
        ]),
        preExistingFlowIds: new Set(["flow-1"]),
        initialToolNameByFlow: new Map([["flow-1", "original_tool"]]),
        toolNameByFlow: new Map([
          ["flow-1", "same_name"],
          ["flow-2", "same_name"],
        ]),
        selectedInstance: { id: "inst-1" },
        setHasToolNameErrors,
      }),
    );

    render(<StepReview />);

    const errors = screen.getAllByText(
      "Duplicate tool name within this deployment",
    );
    expect(errors.length).toBe(2);
    expect(setHasToolNameErrors).toHaveBeenCalledWith(true);
  });
});
