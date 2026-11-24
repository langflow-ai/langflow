import { render, screen } from "@testing-library/react";
import { ParameterRenderComponent } from "..";

// ParameterRenderComponent's module-level imports pull in every widget it
// can dispatch to (~30 files) regardless of which one a given test exercises
// — all need a trivial stub so the module loads. We only care about the
// EmptyParameterComponent/default path here (real widget behavior is out of
// scope for this file; see index.test.tsx for the type-level checks).
jest.mock(
  "@/components/core/parameterRenderComponent/components/codeAreaComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/dataDisplayComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/dbProviderInputComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/modelInputComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/sliderComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/TableNodeComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock(
  "@/components/core/parameterRenderComponent/components/tabComponent",
  () => () => <div data-testid="widget" />,
);
jest.mock("@/customization/components/custom-connectionComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("@/customization/components/custom-input-file", () => () => (
  <div data-testid="widget" />
));
jest.mock("@/customization/components/custom-linkComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/accordionPromptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/actionPickerComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/dictComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/durationComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/emptyParameterComponent", () => ({
  EmptyParameterComponent: () => <div data-testid="widget" />,
}));
jest.mock("../components/floatComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/inputListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/intComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/keypairListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/mcpComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/multiselectComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/mustachePromptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/promptComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/queryComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/sortableListComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/strRenderComponent", () => ({
  StrRenderComponent: () => <div data-testid="widget" />,
}));
jest.mock("../components/ToolsComponent", () => () => (
  <div data-testid="widget" />
));
jest.mock("../components/toggleShadComponent", () => () => (
  <div data-testid="widget" />
));

const baseProps = {
  handleOnNewValue: jest.fn(),
  name: "prompt",
  nodeId: "node-1",
  templateData: { type: "some-unhandled-type" },
  templateValue: "hello",
  editNode: false,
  showParameter: true,
  inspectionPanel: false,
  handleNodeClass: jest.fn(),
  nodeClass: { template: {} } as never,
  disabled: false,
};

describe("ParameterRenderComponent — aria-labelledby wiring", () => {
  // Regression guard: this component used to wrap the rendered widget in a
  // <div role="group" aria-labelledby={ariaLabelledBy}> whenever a label id
  // was forwarded. That produced a real, audible bug: for widgets that
  // already compose the field label into their own accessible name (e.g.
  // dropdownComponent, modelInputComponent), a screen reader announced the
  // group's own name on entry and then the control's composed name right
  // after — the field label was heard twice in a row. There is no wrapper
  // element at all now; `ariaLabelledBy` flows through only as a plain prop
  // for each widget to apply to its own real control.
  it("does not introduce any wrapper element regardless of ariaLabelledBy", () => {
    const { container: withLabel } = render(
      <ParameterRenderComponent
        {...baseProps}
        ariaLabelledBy="node-1-field-prompt-label"
      />,
    );
    expect(withLabel.querySelector('[role="group"]')).not.toBeInTheDocument();
    expect(screen.getByTestId("widget")).toBeInTheDocument();

    const { container: withoutLabel } = render(
      <ParameterRenderComponent {...baseProps} />,
    );
    expect(
      withoutLabel.querySelector('[role="group"]'),
    ).not.toBeInTheDocument();
  });
});
