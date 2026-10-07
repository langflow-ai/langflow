import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import DictComponent from "..";

const baseProps = {
  value: {},
  id: "dict-field",
  editNode: false,
  disabled: false,
  name: "",
  handleOnNewValue: jest.fn(),
};

describe("DictComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Headers</span>
        <DictComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: the visible text is "Edit {name}", which is already
  // field-specific when name is set, but name is often blank/generic — the
  // field's real label should win when present, same reasoning as
  // dataDisplayComponent.
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <DictComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(screen.getByRole("button", { name: "Headers" })).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<DictComponent {...baseProps} />);

    const button = screen.getByRole("button");
    expect(button).not.toHaveAttribute("aria-labelledby");
  });
});
