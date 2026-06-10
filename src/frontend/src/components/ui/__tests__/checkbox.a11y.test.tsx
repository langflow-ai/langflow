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
  // Known gap (a11y-action-plan 1.3): CheckBoxDiv is a visual-only <div>
  // with no checkbox role, state, or keyboard support. This flips to a
  // regular test once the fix lands — jest will then report it as failing
  // because the inner expectation starts passing.
  it.failing("should_expose_checkbox_role_and_checked_state", () => {
    render(<CheckBoxDiv checked />);

    const checkbox = screen.getByRole("checkbox");
    expect(checkbox).toHaveAttribute("aria-checked", "true");
  });
});
