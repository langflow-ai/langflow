import { render, screen } from "@testing-library/react";
import { ReactFlowProvider } from "@xyflow/react";
import type { NodeDataType } from "@/types/flow";
import { axe } from "@/utils/a11y-test";
import NodeInputField from "..";

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: () => false,
}));

jest.mock("@/stores/darkStore", () => ({
  __esModule: true,
  useDarkStore: (selector: (state: unknown) => unknown) =>
    selector({ dark: false }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ isAuthenticated: true }),
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: (selector: (state: unknown) => unknown) =>
    selector({ data: {} }),
}));

jest.mock("@/hooks/use-is-auto-login", () => ({
  useIsAutoLogin: () => false,
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: () => ({ mutate: jest.fn(), mutateAsync: jest.fn() }),
}));

jest.mock("@/CustomNodes/hooks/use-handle-node-class", () => ({
  __esModule: true,
  default: () => ({ handleNodeClass: jest.fn() }),
}));

jest.mock("@/CustomNodes/hooks/use-handle-new-value", () => ({
  __esModule: true,
  default: () => ({ handleOnNewValue: jest.fn() }),
}));

jest.mock("@/CustomNodes/hooks/use-fetch-data-on-mount", () => ({
  __esModule: true,
  default: () => undefined,
}));

// custom-parameter.tsx itself (CustomParameterComponent, the real
// getCustomParameterTitle that applies id={labelId} to the visible label —
// the chokepoint gap 3 depends on — and CustomParameterLabel) is kept
// entirely real. Only ParameterRenderComponent, the actual root of the
// ~37-widget dispatch tree (already covered by gap 3's own 461 tests), is
// stubbed — its own dependency chain pulls in nanoid (ESM-only, not
// transformable under this Jest config) via mcpComponent's addMcpServerModal,
// so requireActual-ing custom-parameter.tsx and overriding just
// CustomParameterComponent doesn't avoid that: the heavy import still runs
// at module-eval time regardless of what gets exported afterward.
jest.mock("@/components/core/parameterRenderComponent", () => ({
  __esModule: true,
  ParameterRenderComponent: (props: { ariaLabelledBy?: string }) => (
    <div
      data-testid="mock-parameter-component"
      data-aria-labelledby={props.ariaLabelledBy}
    />
  ),
}));

const mockFlowStoreState = {
  currentFlow: { id: "flow-1", name: "My Flow", locked: false },
  edges: [],
  handleDragging: undefined,
  filterType: undefined,
  setHandleDragging: jest.fn(),
  setFilterType: jest.fn(),
  setFilterComponent: jest.fn(),
  setFilterEdge: jest.fn(),
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

const baseData = {
  id: "node-1",
  type: "SomeComponent",
  node: {
    template: {
      input_value: {
        type: "str",
        required: true,
        value: "hello",
      },
    },
  },
} as unknown as NodeDataType;

const baseProps = {
  id: {
    fieldName: "input_value",
    id: "node-1",
    inputTypes: ["Message"],
    type: "",
  },
  data: baseData,
  tooltipTitle: "Message",
  title: "Input Value",
  colors: ["red"],
  colorName: ["red"],
  type: "str",
  name: "input_value",
  required: true,
  optionalHandle: null,
  info: "",
  proxy: undefined,
  showNode: true,
};

describe("NodeInputField", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <ReactFlowProvider>
        <NodeInputField {...baseProps} />
      </ReactFlowProvider>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard for the gap 3 chokepoint: the visible label must
  // carry an id, and that same id must reach the field widget's
  // ariaLabelledBy — this is the thing every one of the 37 widgets
  // downstream depends on.
  it("links the visible label to the field widget via a shared id", () => {
    render(
      <ReactFlowProvider>
        <NodeInputField {...baseProps} />
      </ReactFlowProvider>,
    );

    const labelId = "node-node-1-field-input_value-label";
    expect(document.getElementById(labelId)).toHaveTextContent("Input Value");
    expect(screen.getByTestId("mock-parameter-component")).toHaveAttribute(
      "data-aria-labelledby",
      labelId,
    );
  });

  it("marks a required field for assistive tech without duplicating the asterisk visually", () => {
    render(
      <ReactFlowProvider>
        <NodeInputField {...baseProps} />
      </ReactFlowProvider>,
    );

    expect(screen.getAllByText("*")[0]).toHaveAttribute("aria-hidden", "true");
  });
});
