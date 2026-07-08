import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "@/utils/a11y-test";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "../dropdown-menu";

const renderMenu = () =>
  render(
    <DropdownMenu>
      <DropdownMenuTrigger>Flow actions</DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem>Duplicate</DropdownMenuItem>
        <DropdownMenuItem>Delete</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>,
  );

describe("DropdownMenu accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByRole("button", { name: "Flow actions" }));

    // Radix portals menu content to document.body, outside the render
    // container. The region rule is a page-level landmark concern that a
    // bare unit render cannot satisfy.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_expose_menu_and_menuitem_roles", async () => {
    const user = userEvent.setup();
    renderMenu();

    await user.click(screen.getByRole("button", { name: "Flow actions" }));

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Duplicate" }),
    ).toBeInTheDocument();
  });

  it("should_expose_expanded_state_on_trigger", async () => {
    const user = userEvent.setup();
    renderMenu();

    const trigger = screen.getByRole("button", { name: "Flow actions" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
  });

  it("should_close_on_escape_and_restore_focus_to_trigger", async () => {
    const user = userEvent.setup();
    renderMenu();

    const trigger = screen.getByRole("button", { name: "Flow actions" });
    await user.click(trigger);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
