import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import DataDisplayComponent from "..";

const baseProps = {
  value: { title: "Widget", sections: [{ text: "Some content" }] },
  id: "data-display-field",
  editNode: false,
  disabled: false,
  handleOnNewValue: jest.fn(),
};

describe("DataDisplayComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Deployment manifest</span>
        <DataDisplayComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: the trigger's own visible text is always the generic
  // "View" verb with no field context, so aria-labelledby must be applied
  // (unlike widgets whose visible text already includes the field name).
  it("uses the field's real label as the trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Deployment manifest</span>
        <DataDisplayComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Deployment manifest" }),
    ).toBeInTheDocument();
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    render(<DataDisplayComponent {...baseProps} />);

    const button = screen.getByTestId("data_display_data-display-field");
    expect(button).not.toHaveAttribute("aria-labelledby");
  });
});
