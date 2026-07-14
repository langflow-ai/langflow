import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { APIClassType } from "@/types/api";
import type { targetHandleType } from "@/types/flow";
import { CustomParameterComponent } from "../custom-parameter";

const mockUseIsFlowReadOnly = jest.fn();
const mockFlowState = {
  currentFlow: { id: "flow-1" },
  edges: [],
};

jest.mock("@/contexts/permissionsContext", () => ({
  useIsFlowReadOnly: (...args: unknown[]) => mockUseIsFlowReadOnly(...args),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowState) => unknown) =>
    selector(mockFlowState),
}));

jest.mock("@/components/core/parameterRenderComponent", () => ({
  ParameterRenderComponent: ({ disabled }: { disabled: boolean }) => (
    <div data-testid="parameter" data-disabled={String(disabled)} />
  ),
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: (value: unknown) => JSON.stringify(value),
}));

const defaultProps: ComponentProps<typeof CustomParameterComponent> = {
  handleOnNewValue: jest.fn(),
  name: "prompt",
  nodeId: "node-1",
  inputId: { fieldName: "prompt" } as targetHandleType,
  templateData: {},
  templateValue: "hello",
  showParameter: true,
  inspectionPanel: false,
  editNode: false,
  handleNodeClass: jest.fn(),
  nodeClass: {} as APIClassType,
  proxy: undefined,
};

describe("CustomParameterComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseIsFlowReadOnly.mockReturnValue(false);
  });

  it("keeps the parameter enabled when the flow is writable", () => {
    render(<CustomParameterComponent {...defaultProps} />);

    expect(screen.getByTestId("parameter")).toHaveAttribute(
      "data-disabled",
      "false",
    );
  });

  it("disables the parameter when the flow is read-only", () => {
    mockUseIsFlowReadOnly.mockReturnValue(true);

    render(<CustomParameterComponent {...defaultProps} />);

    expect(screen.getByTestId("parameter")).toHaveAttribute(
      "data-disabled",
      "true",
    );
  });
});
