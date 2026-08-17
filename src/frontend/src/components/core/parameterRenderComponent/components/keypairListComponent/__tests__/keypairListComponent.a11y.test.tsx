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

  // Rows past the first were previously left unnamed on the reasoning that
  // only row 1 stands in for the field. axe flags that as a `label`
  // violation, and it reproduces the exact symptom QA reported ("Type a
  // value…, edit text") one row down — so every row is named, and rows 2+
  // carry their position to stay distinguishable from row 1.
  it("names the second row's key input with the field label and its row position", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Headers row 2" }),
    ).toBeInTheDocument();
  });

  // QA (LE-2155): the value input was reachable but nameless — a screen
  // reader announced only "Type a value…, edit text", so it was
  // indistinguishable from the key input of the same row.
  it("names the first row's value input with the field label plus a value qualifier", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Headers value" }),
    ).toBeInTheDocument();
  });

  it("names the second row's value input with the field label, qualifier, and row position", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(
      screen.getByRole("textbox", { name: "Headers value row 2" }),
    ).toBeInTheDocument();
  });

  it("gives every row a distinct accessible name", () => {
    render(
      <>
        <span id="field-label">Headers</span>
        <KeypairListComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    const names = screen
      .getAllByRole("textbox")
      .map((el) => el.getAttribute("aria-labelledby"));
    // No input may be left without a name — that is the axe `label`
    // violation this replaced.
    expect(names.every(Boolean)).toBe(true);
    expect(new Set(names).size).toBe(names.length);
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
