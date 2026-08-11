import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import {
  ContextMenu,
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuLabel,
  ContextMenuRadioGroup,
  ContextMenuRadioItem,
  ContextMenuSeparator,
  ContextMenuTrigger,
} from "../context-menu";

// Radix menus measure and scroll their content; jsdom implements neither.
beforeAll(() => {
  Element.prototype.scrollIntoView = jest.fn();
  Element.prototype.hasPointerCapture = jest.fn();
  Element.prototype.setPointerCapture = jest.fn();
  Element.prototype.releasePointerCapture = jest.fn();
});

const renderContextMenu = () =>
  render(
    <ContextMenu>
      <ContextMenuTrigger>Flow node</ContextMenuTrigger>
      <ContextMenuContent>
        <ContextMenuLabel>Node actions</ContextMenuLabel>
        <ContextMenuItem>Duplicate</ContextMenuItem>
        <ContextMenuItem>Delete</ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuCheckboxItem checked>Show output</ContextMenuCheckboxItem>
        <ContextMenuRadioGroup value="compact">
          <ContextMenuRadioItem value="compact">Compact</ContextMenuRadioItem>
          <ContextMenuRadioItem value="expanded">Expanded</ContextMenuRadioItem>
        </ContextMenuRadioGroup>
      </ContextMenuContent>
    </ContextMenu>,
  );

const openMenu = () => {
  fireEvent.contextMenu(screen.getByText("Flow node"));
};

describe("ContextMenu accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    renderContextMenu();
    openMenu();

    // Radix portals menu content to document.body, outside the render
    // container. The region rule is a page-level landmark concern that a bare
    // unit render cannot satisfy.
    expect(
      await axe(document.body, { rules: { region: { enabled: false } } }),
    ).toHaveNoViolations();
  });

  it("should_expose_menu_and_menuitem_roles", () => {
    renderContextMenu();
    openMenu();

    expect(screen.getByRole("menu")).toBeInTheDocument();
    expect(
      screen.getByRole("menuitem", { name: "Duplicate" }),
    ).toBeInTheDocument();
  });

  it("should_expose_checked_state_on_checkbox_and_radio_items", () => {
    renderContextMenu();
    openMenu();

    expect(
      screen.getByRole("menuitemcheckbox", { name: "Show output" }),
    ).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByRole("menuitemradio", { name: "Compact" }),
    ).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByRole("menuitemradio", { name: "Expanded" }),
    ).toHaveAttribute("aria-checked", "false");
  });

  it("should_move_focus_into_the_menu_when_opened", () => {
    renderContextMenu();
    openMenu();

    const menu = screen.getByRole("menu");
    expect(menu.contains(document.activeElement)).toBe(true);
  });

  it("should_close_on_escape", () => {
    renderContextMenu();
    openMenu();

    fireEvent.keyDown(screen.getByRole("menu"), { key: "Escape" });

    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("should_mark_the_trigger_as_expanded_while_open", () => {
    renderContextMenu();
    const trigger = screen.getByText("Flow node");
    expect(trigger).toHaveAttribute("data-state", "closed");

    openMenu();

    expect(trigger).toHaveAttribute("data-state", "open");
  });
});
