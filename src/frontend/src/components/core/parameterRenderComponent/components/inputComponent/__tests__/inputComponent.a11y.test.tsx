import { render } from "@testing-library/react";
import InputComponent from "../index";

const renderPasswordInput = () =>
  render(
    <InputComponent
      id="password-input"
      password={true}
      value=""
      placeholder="Enter password"
      onChange={() => {}}
    />,
  );

const getToggleButton = (container: HTMLElement) =>
  container.querySelector<HTMLButtonElement>("button[type='button']");

describe("InputComponent password toggle accessibility", () => {
  it("should_render_password_input_with_toggle", () => {
    const { container } = renderPasswordInput();

    expect(container.querySelector("input")).not.toBeNull();
    expect(getToggleButton(container)).not.toBeNull();
  });

  // Known gap (a11y-action-plan 1.1): the show/hide toggle has
  // tabIndex={-1}, no aria-label, and no aria-pressed state.
  it("should_keep_toggle_in_tab_order", () => {
    const { container } = renderPasswordInput();

    const toggle = getToggleButton(container);
    expect(toggle).not.toBeNull();
    expect(toggle).not.toHaveAttribute("tabindex", "-1");
  });

  it("should_name_toggle_with_current_state", () => {
    const { container } = renderPasswordInput();

    const toggle = getToggleButton(container);
    expect(toggle).not.toBeNull();
    expect(toggle).toHaveAccessibleName(/show|hide/i);
    expect(toggle).toHaveAttribute("aria-pressed");
  });
});
