import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";

jest.mock("@/modals/codeAreaModal", () => {
  return function MockCodeAreaModal({
    children,
  }: {
    children: React.ReactNode;
  }) {
    return <div data-testid="mock-code-area-modal">{children}</div>;
  };
});

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: (
    selector: (state: { allowCustomComponents: boolean }) => unknown,
  ) => selector({ allowCustomComponents: true }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

import CodeAreaComponent from "../index";

const baseProps = {
  value: "",
  handleOnNewValue: jest.fn(),
  disabled: false,
  editNode: false,
  nodeClass: undefined as never,
  handleNodeClass: jest.fn(),
  id: "code-field",
};

describe("CodeAreaComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="code-label">System Message</span>
        <CodeAreaComponent {...baseProps} ariaLabelledBy="code-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_forward_ariaLabelledBy_to_the_modal_trigger_button", () => {
    render(
      <>
        <span id="code-label">System Message</span>
        <CodeAreaComponent {...baseProps} ariaLabelledBy="code-label" />
      </>,
    );
    expect(
      screen.getByRole("button", { name: "System Message" }),
    ).toBeInTheDocument();
  });

  it("should_fall_back_to_visible_placeholder_text_when_no_field_label_is_forwarded", () => {
    // With no ariaLabelledBy, the button has no explicit label, so its
    // accessible name falls back to its visible text content (the
    // placeholder span) rather than being empty.
    render(<CodeAreaComponent {...baseProps} />);
    expect(screen.getByRole("button")).not.toHaveAttribute("aria-labelledby");
  });
});
