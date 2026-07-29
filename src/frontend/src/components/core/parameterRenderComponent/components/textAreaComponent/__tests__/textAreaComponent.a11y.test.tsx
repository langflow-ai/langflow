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

  it("should_keep_the_toggle_in_forward_tab_order_while_the_input_is_focused", async () => {
    render(<TextAreaComponent {...baseProps} password={true} />);

    // type="password" inputs have no "textbox" role; query by test id.
    await userEvent.click(screen.getByTestId("field-1"));

    // Visually hidden while editing, but still mounted and tabbable.
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toBeInTheDocument();

    await userEvent.tab(); // expand-editor trigger
    await userEvent.tab(); // password toggle
    expect(toggle).toHaveFocus();

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
