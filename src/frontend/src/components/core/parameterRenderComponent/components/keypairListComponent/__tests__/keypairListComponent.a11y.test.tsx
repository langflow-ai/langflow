import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import KeypairListComponent from "..";

const baseProps = {
  value: [{ headerA: "1" }, { headerB: "2" }],
  id: "keypair-field",
  editNode: false,
  disabled: false,
  handleOnNewValue: jest.fn(),
};

describe("KeypairListComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: only the first row's key input stands in for the
  // field itself — additional rows are entries the user added, same
  // reasoning as inputListComponent.
  it("uses the field's real label as the first row's key-input accessible name", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Headers" }),
    ).toBeInTheDocument();
  });

  it("does not label the second row's key input with the field's label", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    const secondKeyInput = screen.getByTestId("keypair1");
    expect(secondKeyInput).not.toHaveAttribute("aria-labelledby");
  });

  it("falls back to no accessible-name override when ariaLabelledBy is absent", () => {
    // KeypairListComponent has no TS prop types (plain JS-style
    // destructuring), so ariaLabelledBy infers as required — pass it
    // explicitly as undefined to exercise the same absent-prop behavior.
    render(<KeypairListComponent {...baseProps} ariaLabelledBy={undefined} />);

    const firstKeyInput = screen.getByTestId("keypair0");
    expect(firstKeyInput).not.toHaveAttribute("aria-labelledby");
  });
});
