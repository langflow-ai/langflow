import { fireEvent, render, screen } from "@testing-library/react";
import { axe } from "@/utils/a11y-test";
import { SimpleSidebar, SimpleSidebarProvider } from "../simple-sidebar";

class ResizeObserverMock {
  observe = jest.fn();
  disconnect = jest.fn();
}

describe("SimpleSidebar", () => {
  beforeAll(() => {
    Object.defineProperty(window, "ResizeObserver", {
      writable: true,
      configurable: true,
      value: ResizeObserverMock,
    });
  });

  it("has no detectable axe violations in fullscreen mode", async () => {
    const { container } = render(
      <SimpleSidebarProvider open fullscreen>
        <SimpleSidebar>
          <button type="button">First</button>
          <button type="button">Last</button>
        </SimpleSidebar>
      </SimpleSidebarProvider>,
    );

    const results = await axe(container);

    expect(results).toHaveNoViolations();
  });

  it("traps focus inside the fullscreen sidebar", () => {
    render(
      <SimpleSidebarProvider open fullscreen>
        <button type="button">Before sidebar</button>
        <SimpleSidebar>
          <button type="button" tabIndex={2}>
            Second
          </button>
          <button type="button" tabIndex={1}>
            First
          </button>
          <button type="button" disabled>
            Disabled
          </button>
          <button type="button" style={{ display: "none" }}>
            Hidden
          </button>
          <button type="button">Last</button>
        </SimpleSidebar>
        <button type="button">After sidebar</button>
      </SimpleSidebarProvider>,
    );

    const sidebar = screen.getByRole("dialog", { name: /playground/i });
    const first = screen.getByRole("button", { name: "First" });
    const last = screen.getByRole("button", { name: "Last" });

    last.focus();
    fireEvent.keyDown(sidebar, { key: "Tab" });
    expect(first).toHaveFocus();

    fireEvent.keyDown(sidebar, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
  });

  // Regression guard: a nested dialog (e.g. the Session logs modal) portals
  // its content elsewhere in the DOM but still bubbles React keydown events
  // up through this component's React-tree ancestry. Previously, the
  // sidebar's own subtree being aria-hidden/inert while the nested dialog is
  // open meant getFocusableElements found nothing, and the fallback
  // "refocus the container" branch yanked focus out of the nested dialog on
  // every single Tab press — a keyboard trap that made the nested dialog's
  // own contents completely unreachable via Tab (WCAG 2.1.2).
  it("does not hijack focus on Tab when focus has moved into a nested dialog", () => {
    render(
      <SimpleSidebarProvider open fullscreen>
        <SimpleSidebar>
          <button type="button">Sidebar button</button>
        </SimpleSidebar>
      </SimpleSidebarProvider>,
    );

    const sidebar = screen.getByRole("dialog", { name: /playground/i });

    // Simulate the sidebar's own subtree being hidden from the accessibility
    // tree while a nested modal is open on top of it (what Radix's
    // useInertForAriaHiddenElements does to background content).
    sidebar.setAttribute("aria-hidden", "true");

    // A detached element standing in for focus that currently lives inside
    // a portaled nested dialog — i.e. genuinely outside the sidebar's DOM.
    const nestedDialogButton = document.createElement("button");
    document.body.appendChild(nestedDialogButton);
    nestedDialogButton.focus();
    expect(nestedDialogButton).toHaveFocus();

    fireEvent.keyDown(sidebar, { key: "Tab" });

    expect(nestedDialogButton).toHaveFocus();
    expect(sidebar).not.toHaveFocus();

    nestedDialogButton.remove();
  });
});
