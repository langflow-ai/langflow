import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {
  Popover,
  PopoverContentWithoutPortal,
  PopoverTrigger,
} from "../popover";
import {
  Select,
  SelectContentWithoutPortal,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../select";

// React Flow listens for arrow and selection keys on the node element itself,
// and inline (non-portalled) Radix content renders inside that element. These
// lock in that such content swallows the keys the canvas reserves, so a menu
// keypress can no longer move the node underneath it.

const renderInlinePopover = (
  ancestorOnKeyDown: jest.Mock,
  contentOnKeyDown?: jest.Mock,
) =>
  render(
    // biome-ignore lint/a11y/noStaticElementInteractions: stands in for React Flow's node wrapper
    <div onKeyDown={ancestorOnKeyDown} data-testid="node-wrapper">
      <Popover defaultOpen>
        <PopoverTrigger>Open menu</PopoverTrigger>
        <PopoverContentWithoutPortal
          aria-label="Node actions"
          onKeyDown={contentOnKeyDown}
        >
          <button type="button">Duplicate</button>
        </PopoverContentWithoutPortal>
      </Popover>
    </div>,
  );

describe("inline Radix content key propagation", () => {
  beforeAll(() => {
    if (!Element.prototype.hasPointerCapture) {
      Element.prototype.hasPointerCapture = jest.fn(() => false);
    }
    if (!Element.prototype.releasePointerCapture) {
      Element.prototype.releasePointerCapture = jest.fn();
    }
    if (!Element.prototype.scrollIntoView) {
      Element.prototype.scrollIntoView = jest.fn();
    }
  });

  it("should_not_leak_arrow_keys_to_the_canvas_from_popover_content", async () => {
    const user = userEvent.setup();
    const ancestorOnKeyDown = jest.fn();
    renderInlinePopover(ancestorOnKeyDown);

    screen.getByRole("button", { name: "Duplicate" }).focus();
    await user.keyboard("{ArrowDown}{ArrowUp}{ArrowLeft}{ArrowRight}");

    expect(ancestorOnKeyDown).not.toHaveBeenCalled();
  });

  it("should_not_leak_selection_keys_to_the_canvas_from_popover_content", async () => {
    const user = userEvent.setup();
    const ancestorOnKeyDown = jest.fn();
    renderInlinePopover(ancestorOnKeyDown);

    screen.getByRole("button", { name: "Duplicate" }).focus();
    await user.keyboard("{Enter}{ }");

    expect(ancestorOnKeyDown).not.toHaveBeenCalled();
  });

  it("should_still_let_unreserved_keys_bubble", async () => {
    const user = userEvent.setup();
    const ancestorOnKeyDown = jest.fn();
    renderInlinePopover(ancestorOnKeyDown);

    screen.getByRole("button", { name: "Duplicate" }).focus();
    await user.keyboard("a");

    expect(ancestorOnKeyDown).toHaveBeenCalledTimes(1);
  });

  it("should_still_run_a_caller_supplied_key_handler", async () => {
    const user = userEvent.setup();
    const ancestorOnKeyDown = jest.fn();
    const contentOnKeyDown = jest.fn();
    renderInlinePopover(ancestorOnKeyDown, contentOnKeyDown);

    screen.getByRole("button", { name: "Duplicate" }).focus();
    await user.keyboard("{ArrowDown}");

    expect(contentOnKeyDown).toHaveBeenCalledTimes(1);
    expect(ancestorOnKeyDown).not.toHaveBeenCalled();
  });

  // Radix dismisses on a document capture listener, which runs before the
  // content's own handler — stopping propagation must not break it.
  it("should_still_close_the_popover_on_escape", async () => {
    const user = userEvent.setup();
    renderInlinePopover(jest.fn());

    expect(screen.getByRole("dialog", { name: "Node actions" })).toBeVisible();

    screen.getByRole("button", { name: "Duplicate" }).focus();
    await user.keyboard("{Escape}");

    expect(
      screen.queryByRole("dialog", { name: "Node actions" }),
    ).not.toBeInTheDocument();
  });

  it("should_not_leak_arrow_keys_to_the_canvas_from_select_content", async () => {
    const user = userEvent.setup();
    const ancestorOnKeyDown = jest.fn();
    render(
      // biome-ignore lint/a11y/noStaticElementInteractions: stands in for React Flow's node wrapper
      <div onKeyDown={ancestorOnKeyDown} data-testid="node-wrapper">
        <Select defaultOpen>
          <SelectTrigger aria-label="Model">
            <SelectValue placeholder="Pick a model" />
          </SelectTrigger>
          <SelectContentWithoutPortal>
            <SelectItem value="gpt">GPT</SelectItem>
            <SelectItem value="claude">Claude</SelectItem>
          </SelectContentWithoutPortal>
        </Select>
      </div>,
    );

    await user.keyboard("{ArrowDown}{ArrowUp}");

    expect(ancestorOnKeyDown).not.toHaveBeenCalled();
  });
});
