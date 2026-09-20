import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import MultiselectComponent from "..";

const baseProps = {
  value: [],
  id: "multiselect-field",
  editNode: false,
  disabled: false,
  options: ["a", "b", "c"],
  handleOnNewValue: jest.fn(),
};

describe("MultiselectComponent", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="field-label">Tags</span>
        <MultiselectComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  // Regression guard: label only, not composed with the selected values —
  // role="combobox" gets special handling from screen readers, so composing
  // would double-announce the value (same reasoning as connectionComponent).
  it("uses the field's real label as the combobox trigger's accessible name", () => {
    render(
      <>
        <span id="field-label">Tags</span>
        <MultiselectComponent {...baseProps} ariaLabelledBy="field-label" />
      </>,
    );

    expect(screen.getByRole("combobox", { name: "Tags" })).toBeInTheDocument();
  });

  it("does not set aria-labelledby on the combobox trigger when absent", () => {
    render(<MultiselectComponent {...baseProps} />);

    expect(screen.getByRole("combobox")).not.toHaveAttribute("aria-labelledby");
  });
});
