import { fireEvent, render, screen } from "@testing-library/react";
import { useCheckToolNames } from "@/controllers/API/queries/deployments";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import StepReview from "../components/step-review";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

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
