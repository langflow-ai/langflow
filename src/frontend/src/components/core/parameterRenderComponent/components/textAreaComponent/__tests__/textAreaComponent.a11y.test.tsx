import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import TextAreaComponent from "../index";

const baseProps = {
  id: "field-1",
  value: "hello",
  editNode: false,
  handleOnNewValue: jest.fn(),
  disabled: false,
};

describe("TextAreaComponent accessibility", () => {
  it("should_have_no_axe_violations", async () => {
    const { container } = render(<TextAreaComponent {...baseProps} />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_edit_text_as_accessible_name_on_the_expand_trigger", () => {
    render(<TextAreaComponent {...baseProps} />);

    expect(
      screen.getByRole("button", { name: "Expand text editor" }),
    ).toBeInTheDocument();
  });

  it("should_expose_the_trigger_as_a_real_button_with_valid_aria_expanded", () => {
    render(<TextAreaComponent {...baseProps} />);

    const trigger = screen.getByRole("button", { name: "Expand text editor" });
    expect(trigger.tagName).toBe("BUTTON");
    expect(trigger).toHaveAttribute("aria-haspopup", "dialog");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });

  it("should_have_no_axe_violations_when_disabled", async () => {
    const { container } = render(
      <TextAreaComponent {...baseProps} disabled={true} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_render_the_password_toggle_as_a_named_button", async () => {
    render(<TextAreaComponent {...baseProps} password={true} />);

    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle.tagName).toBe("BUTTON");

    await userEvent.click(toggle);
    expect(
      screen.getByRole("button", { name: "Hide password" }),
    ).toBeInTheDocument();
  });

  it("should_toggle_password_visibility_from_the_keyboard", async () => {
    render(<TextAreaComponent {...baseProps} password={true} />);

    // Note: the toggle unmounts while the text input itself is focused
    // (`password && !isFocused`), so it is skipped in forward tab order from
    // the input. Focus it directly here; the tab-order gap is a known issue.
    const toggle = screen.getByRole("button", { name: "Show password" });
    toggle.focus();
    await userEvent.keyboard("{Enter}");

    expect(
      screen.getByRole("button", { name: "Hide password" }),
    ).toBeInTheDocument();
  });

  it("should_have_no_axe_violations_with_password_toggle", async () => {
    const { container } = render(
      <TextAreaComponent {...baseProps} password={true} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });
});
