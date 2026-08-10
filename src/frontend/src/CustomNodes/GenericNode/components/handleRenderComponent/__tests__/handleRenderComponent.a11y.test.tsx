import { render } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import { axe } from "@/utils/a11y-test";
import HandleRenderComponent from "..";

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => false,
}));

jest.mock("@/stores/darkStore", () => ({
  __esModule: true,
  useDarkStore: (selector: (state: unknown) => unknown) =>
    selector({ dark: false }),
}));

const mockFlowStoreState = {
  currentFlow: { locked: false, id: "flow-1" },
  edges: [],
  handleDragging: undefined,
  filterType: undefined,
  setHandleDragging: jest.fn(),
  setFilterType: jest.fn(),
  setFilterComponent: jest.fn(),
  onConnect: jest.fn(),
  nodes: [],
};

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (
    selector?: (state: typeof mockFlowStoreState) => unknown,
  ) => (selector ? selector(mockFlowStoreState) : mockFlowStoreState);
  useFlowStore.getState = () => mockFlowStoreState;

  return {
    __esModule: true,
    default: useFlowStore,
  };
});

const baseProps = {
  left: true,
  tooltipTitle: "Message",
  id: { fieldName: "input", id: "node-1", inputTypes: ["Message"], type: "" },
  title: "Input",
  myData: {},
  colors: ["red"],
  colorName: ["red"],
  setFilterEdge: jest.fn(),
  showNode: true,
  testIdComplement: "test-node-1",
  nodeId: "node-1",
};

describe("HandleRenderComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <HandleRenderComponent {...baseProps} />
      </ReactFlowProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
