import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { CheckBoxDiv, Checkbox } from "../checkbox";

describe("Checkbox accessibility", () => {
  it("should_have_no_axe_violations_when_labeled", async () => {
    const { container } = render(
      <Checkbox aria-label="Enable notifications" />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_checkbox_role_and_state", () => {
    render(<Checkbox aria-label="Enable notifications" checked />);

    const checkbox = screen.getByRole("checkbox", {
      name: "Enable notifications",
    });
    expect(checkbox).toBeChecked();
  });
});

describe("CheckBoxDiv accessibility", () => {
  it("should_expose_checkbox_role_and_checked_state", () => {
    render(<CheckBoxDiv checked />);

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toHaveAttribute("aria-checked", "true");
  });

  // When the wrapping element owns the toggle semantics (e.g. a toggle
  // button) the indicator must NOT expose an interactive "checkbox" role,
  // otherwise it nests an interactive role inside another one
  // (IBM aria_descendant_valid).
  it("should_be_hidden_from_assistive_tech_when_presentational", () => {
    const { container } = render(<CheckBoxDiv checked presentational />);

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(container.firstChild).toHaveAttribute("aria-hidden", "true");
  });
});
