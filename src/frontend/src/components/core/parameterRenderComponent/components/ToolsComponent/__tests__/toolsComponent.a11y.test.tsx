import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { mockGenericIconComponent } from "../../__tests__/a11y-mock-helpers";
import ToolsComponent from "..";

jest.mock("@/modals/toolsModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../../../../../common/genericIconComponent", () =>
  mockGenericIconComponent(),
);

const baseProps = {
  value: [{ name: "search", status: true, tags: [], description: "" }],
  id: "tools-field",
  editNode: false,
  disabled: false,
  description: "",
  title: "Tools",
  handleOnNewValue: jest.fn(),
};

describe("ToolsComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Available tools</span>
        <ToolsComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: the "open actions" button is icon-only unless a
  // button_description is configured — the field's real label is the only
  // accessible name it gets either way.
  it("uses the field's real label as the open-actions button's accessible name", () => {
    render(
      <>
        <span id="field-label">Available tools</span>
        <ToolsComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Available tools" }),
    ).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<ToolsComponent {...baseProps} />);

    const button = screen.getByTestId("button_open_actions");
    expect(button).not.toHaveAttribute("aria-labelledby");
  });

  it("keeps the empty-state add-actions button's own name instead of the field label", () => {
    render(
      <>
        <span id="field-label">Available tools</span>
        <ToolsComponent
          {...baseProps}
          value={[]}
          isAction
          ariaLabelledBy="field-label"
        />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Available tools" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Add actions" }),
    ).toBeInTheDocument();
  });
});
