import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

jest.mock("@/modals/promptModal", () => {
  return function MockPromptModal({ children }: { children: React.ReactNode }) {
    return <div data-testid="mock-prompt-modal">{children}</div>;
  };
});

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

import PromptAreaComponent from "../index";

const baseProps = {
  field_name: "template",
  nodeClass: undefined as never,
  handleOnNewValue: jest.fn(),
  handleNodeClass: jest.fn(),
  value: "",
  disabled: false,
  editNode: false,
  id: "prompt-field",
  readonly: false,
};

describe("PromptAreaComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="prompt-label">System Prompt</span>
        <PromptAreaComponent {...baseProps} ariaLabelledBy="prompt-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_forward_ariaLabelledBy_to_the_modal_trigger_button", () => {
    render(
      <>
        <span id="prompt-label">System Prompt</span>
        <PromptAreaComponent {...baseProps} ariaLabelledBy="prompt-label" />
      </>,
    );
    expect(screen.getByTestId("button_open_prompt_modal")).toHaveAttribute(
      "aria-labelledby",
      "prompt-label",
    );
  });

  it("should_render_the_trigger_with_no_aria_labelledby_when_no_field_label_is_forwarded", () => {
    render(<PromptAreaComponent {...baseProps} />);
    expect(screen.getByTestId("button_open_prompt_modal")).not.toHaveAttribute(
      "aria-labelledby",
    );
  });
});
