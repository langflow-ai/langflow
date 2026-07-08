import { fireEvent, render, screen } from "@testing-library/react";
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
});
