import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { Switch } from "../switch";

describe("Switch accessibility", () => {
  it("should_have_no_axe_violations_when_labeled", async () => {
    const { container } = render(<Switch aria-label="Enable autosave" />);

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_switch_role_and_state", () => {
    render(<Switch aria-label="Enable autosave" checked />);

    const toggle = screen.getByRole("switch", { name: "Enable autosave" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
  });

  it("should_toggle_with_keyboard", async () => {
    const user = userEvent.setup();
    const onCheckedChange = jest.fn();
    render(
      <Switch aria-label="Enable autosave" onCheckedChange={onCheckedChange} />,
    );

    const toggle = screen.getByRole("switch");
    act(() => {
      toggle.focus();
    });
    await user.keyboard(" ");
    expect(onCheckedChange).toHaveBeenCalledWith(true);
  });
});
