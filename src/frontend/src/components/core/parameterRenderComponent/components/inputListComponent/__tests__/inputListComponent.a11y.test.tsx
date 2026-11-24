import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import InputListComponent from "..";

const baseProps = {
  value: ["first", "second"],
  id: "input-list-field",
  editNode: false,
  disabled: false,
  handleOnNewValue: jest.fn(),
};

describe("InputListComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">URLs</span>
        <InputListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: only the first row stands in for the field itself —
  // additional rows are entries the user added, not the field being labeled.
  it("uses the field's real label as the first row's accessible name", () => {
    render(
      <>
        <span id="field-label">URLs</span>
        <InputListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(screen.getByRole("textbox", { name: "URLs" })).toBeInTheDocument();
  });

  it("does not label the additional rows with the field's label", () => {
    render(
      <>
        <span id="field-label">URLs</span>
        <InputListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    const secondRow = screen.getByTestId("input-list-field_1");
    expect(secondRow).not.toHaveAttribute("aria-labelledby");
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<InputListComponent {...baseProps} />);

    const firstRow = screen.getByTestId("input-list-field_0");
    expect(firstRow).not.toHaveAttribute("aria-labelledby");
  });
});
