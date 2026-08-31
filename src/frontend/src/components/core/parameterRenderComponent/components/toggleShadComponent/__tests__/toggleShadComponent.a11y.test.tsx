import { render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import ToggleShadComponent from "../index";

const baseProps = {
  value: false,
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
  id: "toggle-field",
};

describe("ToggleShadComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(
      <>
        <span id="toggle-label">Use Cache</span>
        <ToggleShadComponent {...baseProps} ariaLabelledBy="toggle-label" />
      </>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_the_forwarded_field_label_as_accessible_name", () => {
    render(
      <>
        <span id="toggle-label">Use Cache</span>
        <ToggleShadComponent {...baseProps} ariaLabelledBy="toggle-label" />
      </>,
    );
    expect(
      screen.getByRole("switch", { name: "Use Cache" }),
    ).toBeInTheDocument();
  });

  it("should_render_with_no_accessible_name_when_no_field_label_is_forwarded", () => {
    render(<ToggleShadComponent {...baseProps} />);
    expect(screen.getByTestId("toggle-field")).not.toHaveAccessibleName();
  });

  it("should_reflect_the_checked_state_for_assistive_technology", () => {
    render(
      <>
        <span id="toggle-label">Use Cache</span>
        <ToggleShadComponent
          {...baseProps}
          value={true}
          ariaLabelledBy="toggle-label"
        />
      </>,
    );
    expect(screen.getByRole("switch")).toHaveAttribute("aria-checked", "true");
  });
});
