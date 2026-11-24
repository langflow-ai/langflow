import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import QueryComponent from "../index";

const baseProps = {
  id: "field-1",
  value: "SELECT * FROM table",
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
  display_name: "Filter",
  info: "Query filter",
};

describe("QueryComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<QueryComponent {...baseProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_edit_text_as_accessible_name_on_the_expand_trigger", () => {
    render(<QueryComponent {...baseProps} />);

    expect(
      screen.getByRole("button", { name: "Expand text editor" }),
    ).toBeInTheDocument();
  });

  it("should_expose_the_trigger_as_a_real_button_with_valid_aria_expanded", () => {
    render(<QueryComponent {...baseProps} />);

    const trigger = screen.getByRole("button", { name: "Expand text editor" });
    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("should_have_no_axe_violations_when_disabled", async () => {
    const { container } = render(
      <QueryComponent {...baseProps} disabled={true} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
