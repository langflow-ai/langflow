import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import AccordionPromptComponent from "../index";

// AccordionPromptComponent is what ParameterRenderComponent actually
// dispatches "prompt"/"mustache" fields to in the primary canvas-node view
// (ENABLE_INSPECTION_PANEL is hardcoded true and NodeInputField always
// passes editNode={false}), NOT PromptAreaComponent/MustachePromptAreaComponent
// — those are only reached from table-cell inline editing. A fix applied
// only to the latter two is dead code for the field type's real usage.
jest.mock("@/modals/promptModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-prompt-modal">{children}</div>
  ),
}));
jest.mock("@/modals/mustachePromptModal", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="mock-mustache-modal">{children}</div>
  ),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-validate-prompt", () => ({
  usePostValidatePrompt: () => ({ mutateAsync: jest.fn() }),
}));

const baseProps = {
  field_name: "template",
  nodeClass: undefined as never,
  handleOnNewValue: jest.fn(),
  handleNodeClass: jest.fn(),
  value: "hello",
  disabled: false,
  id: "accordion-prompt",
  nodeId: "node-1",
  showParameter: true,
  editNode: false,
};

describe("AccordionPromptComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="prompt-label">System Prompt</span>
        <AccordionPromptComponent
          {...baseProps}
          ariaLabelledBy="prompt-label"
        />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_forward_ariaLabelledBy_to_the_editable_control", () => {
    render(
      <>
        <span id="prompt-label">System Prompt</span>
        <AccordionPromptComponent
          {...baseProps}
          ariaLabelledBy="prompt-label"
        />
      </>,
    );
    expect(
      screen.getByRole("textbox", { name: "System Prompt" }),
    ).toBeInTheDocument();
  });

  it("should_render_the_editable_control_with_no_aria_labelledby_when_no_field_label_is_forwarded", () => {
    render(<AccordionPromptComponent {...baseProps} />);
    expect(screen.getByTestId("accordion-prompt")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });

  it("should_expose_the_editable_control_as_a_multiline_textbox", () => {
    render(
      <>
        <span id="prompt-label">System Prompt</span>
        <AccordionPromptComponent
          {...baseProps}
          ariaLabelledBy="prompt-label"
        />
      </>,
    );
    expect(screen.getByTestId("accordion-prompt")).toHaveAttribute(
      "aria-multiline",
      "true",
    );
  });
});
