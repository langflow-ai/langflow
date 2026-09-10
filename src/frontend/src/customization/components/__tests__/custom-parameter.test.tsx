import { render, screen } from "@testing-library/react";
import type { ComponentProps } from "react";
import type { APIClassType } from "@/types/api";
import type { targetHandleType } from "@/types/flow";
import {
  CustomParameterComponent,
  getCustomParameterTitle,
} from "../custom-parameter";

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
  ParameterRenderComponent: ({
    disabled,
    ariaLabelledBy,
  }: {
    disabled: boolean;
    ariaLabelledBy?: string;
  }) => (
    <div
      data-testid="parameter"
      data-disabled={String(disabled)}
      aria-labelledby={ariaLabelledBy}
    />
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

  it("makes the parameter inert without triggering legacy disabled cleanup", () => {
    mockUseIsFlowReadOnly.mockReturnValue(true);

    render(<CustomParameterComponent {...defaultProps} />);

    expect(screen.getByTestId("parameter")).toHaveAttribute(
      "data-disabled",
      "false",
    );
    expect(screen.getByTestId("parameter-permission-gate")).toHaveAttribute(
      "aria-disabled",
      "true",
    );
  });

  // Regression guard: NodeInputField generates one label id per field and
  // relies on this component to forward it down to whichever widget
  // ParameterRenderComponent ends up rendering — that's what gives every
  // field type an accessible name without touching each widget individually.
  it("forwards ariaLabelledBy through to ParameterRenderComponent", () => {
    render(
      <CustomParameterComponent
        {...defaultProps}
        ariaLabelledBy="node-1-field-prompt-label"
      />,
    );

    expect(screen.getByTestId("parameter")).toHaveAttribute(
      "aria-labelledby",
      "node-1-field-prompt-label",
    );
  });
});

describe("getCustomParameterTitle", () => {
  // Regression guard: the required-field asterisk lives inside the same
  // labelId element that widgets reference via aria-labelledby, so its raw
  // "*" text was leaking into their accessible name (some screen readers
  // read it literally as "asterisk" instead of conveying "required").
  it("hides the required asterisk from the accessible name and exposes real text instead", () => {
    render(
      <div>
        {getCustomParameterTitle({
          title: "API Key",
          nodeId: "node-1",
          isFlexView: false,
          required: true,
          labelId: "api-key-label",
          requiredText: "required",
        })}
      </div>,
    );

    const label = screen.getByText("*");
    expect(label).toHaveAttribute("aria-hidden", "true");
    expect(screen.getByText("required")).toHaveClass("sr-only");
  });

  // Regression guard: getCustomParameterTitle is a plain function, not a
  // component — it can't call useTranslation itself, so the sr-only text
  // must come from whatever the caller passes. No caller may hardcode
  // English text into this function again.
  it("uses whatever requiredText the caller passes, not a hardcoded English string", () => {
    render(
      <div>
        {getCustomParameterTitle({
          title: "API Key",
          nodeId: "node-1",
          isFlexView: false,
          required: true,
          labelId: "api-key-label",
          requiredText: "erforderlich",
        })}
      </div>,
    );

    expect(screen.getByText("erforderlich")).toHaveClass("sr-only");
    expect(screen.queryByText("required")).not.toBeInTheDocument();
  });

  it("renders no required marker at all when the field isn't required", () => {
    render(
      <div>
        {getCustomParameterTitle({
          title: "API Key",
          nodeId: "node-1",
          isFlexView: false,
          required: false,
          labelId: "api-key-label",
        })}
      </div>,
    );

    expect(screen.queryByText("*")).not.toBeInTheDocument();
    expect(screen.queryByText("required")).not.toBeInTheDocument();
  });
});
