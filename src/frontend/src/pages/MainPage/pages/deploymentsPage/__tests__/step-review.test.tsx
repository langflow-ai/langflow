import { fireEvent, render, screen } from "@testing-library/react";
import { useGetRefreshFlowsQuery } from "@/controllers/API/queries/flows/use-get-refresh-flows-query";
import { useFolderStore } from "@/stores/foldersStore";
import StepReview from "../components/step-review";
import { useDeploymentStepper } from "../contexts/deployment-stepper-context";

jest.mock("../contexts/deployment-stepper-context", () => ({
  useDeploymentStepper: jest.fn(),
}));

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

describe("StepReview tool name editing", () => {
  it("persists tool name edits when input loses focus", () => {
    const setToolNameByFlow = jest.fn();

    mockedUseFolderStore.mockImplementation((selector) =>
      selector({ myCollectionId: "folder-1" } as never),
    );
    mockedUseGetRefreshFlowsQuery.mockReturnValue({
      data: [{ id: "flow-1", name: "New Flow", folder_id: "folder-1" }],
    } as never);
    mockedUseDeploymentStepper.mockReturnValue({
      isEditMode: false,
      deploymentType: "agent",
      deploymentName: "Agent One",
      selectedLlm: "meta-llama/llama-3-3-70b-instruct",
      connections: [],
      selectedVersionByFlow: new Map([
        ["flow-1", { versionId: "ver-1", versionTag: "v1" }],
      ]),
      toolNameByFlow: new Map(),
      setToolNameByFlow,
      attachedConnectionByFlow: new Map(),
      removedFlowIds: new Set(),
    } as never);

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
