import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import { Popover, PopoverContent, PopoverTrigger } from "../popover";

const renderPopover = () =>
  render(
    <Popover>
      <PopoverTrigger>Filter flows</PopoverTrigger>
      <PopoverContent aria-label="Filter options">
        <button type="button">Only mine</button>
      </PopoverContent>
    </Popover>,
  );

describe("Popover accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    const user = userEvent.setup();
    renderPopover();

    await user.click(screen.getByRole("button", { name: "Filter flows" }));

    // Radix portals popover content to document.body, outside the render
    // container.
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_expanded_state_on_trigger", async () => {
    const user = userEvent.setup();
    renderPopover();

    const trigger = screen.getByRole("button", { name: "Filter flows" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).not.toHaveAttribute("aria-controls");

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(trigger).toHaveAttribute("aria-controls");
  });

  it("should_close_on_escape_and_restore_focus_to_trigger", async () => {
    const user = userEvent.setup();
    renderPopover();

    const trigger = screen.getByRole("button", { name: "Filter flows" });
    await user.click(trigger);
    expect(
      screen.getByRole("button", { name: "Only mine" }),
    ).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(
      screen.queryByRole("button", { name: "Only mine" }),
    ).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
