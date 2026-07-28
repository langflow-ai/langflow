import { fireEvent, render, screen } from "@testing-library/react";
import {
  Sidebar,
  SidebarProvider,
  SidebarTrigger,
  useSidebar,
} from "../sidebar";

// Mock component to test useSidebar hook
const TestComponent = ({ onToggle }: { onToggle?: () => void }) => {
  const { setOpen, open } = useSidebar();

  return (
    <div>
      <div data-testid="sidebar-state">{open ? "open" : "closed"}</div>
      <button
        data-testid="toggle-btn"
        onClick={() => {
          setOpen((prev) => !prev);
          onToggle?.();
        }}
      >
        Toggle
      </button>
      <button data-testid="set-open-btn" onClick={() => setOpen(true)}>
        Set Open
      </button>
      <button data-testid="set-closed-btn" onClick={() => setOpen(false)}>
        Set Closed
      </button>
    </div>
  );
};

describe("Sidebar", () => {
  let cookieStore: Record<string, string> = {};

  beforeEach(() => {
    // Reset cookie store
    cookieStore = {};

    // Mock document.cookie
    Object.defineProperty(document, "cookie", {
      get: jest.fn(() => {
        return Object.entries(cookieStore)
          .map(([key, value]) => `${key}=${value}`)
          .join("; ");
      }),
      set: jest.fn((cookieString: string) => {
        const [keyValue] = cookieString.split(";");
        const [key, value] = keyValue.split("=");
        if (key && value !== undefined) {
          cookieStore[key.trim()] = value.trim();
        }
      }),
      configurable: true,
    });
  });

  it("should use computed nextOpen value in cookie, not stale open state", () => {
    const { getByTestId } = render(
      <SidebarProvider>
        <TestComponent />
      </SidebarProvider>,
    );

    // Initial state should be open (default)
    expect(getByTestId("sidebar-state")).toHaveTextContent("open");

    // Toggle to closed using function updater
    fireEvent.click(getByTestId("toggle-btn"));

    // Cookie should reflect the NEW state (closed), not the old state
    // This verifies the bug fix: using nextOpen instead of open
    expect(cookieStore["sidebar:state"]).toBe("false");
  });

  it("should update cookie when setOpen is called with boolean", () => {
    const { getByTestId } = render(
      <SidebarProvider defaultOpen={false}>
        <TestComponent />
      </SidebarProvider>,
    );

    // Set to open
    fireEvent.click(getByTestId("set-open-btn"));
    expect(cookieStore["sidebar:state"]).toBe("true");

    // Set to closed
    fireEvent.click(getByTestId("set-closed-btn"));
    expect(cookieStore["sidebar:state"]).toBe("false");
  });

  it("should handle function updater correctly", () => {
    const { getByTestId } = render(
      <SidebarProvider defaultOpen={true}>
        <TestComponent />
      </SidebarProvider>,
    );

    // Toggle from true to false
    fireEvent.click(getByTestId("toggle-btn"));
    expect(cookieStore["sidebar:state"]).toBe("false");

    // Toggle from false to true
    fireEvent.click(getByTestId("toggle-btn"));
    expect(cookieStore["sidebar:state"]).toBe("true");
  });

  it("should persist state across multiple toggles", () => {
    const { getByTestId } = render(
      <SidebarProvider defaultOpen={false}>
        <TestComponent />
      </SidebarProvider>,
    );

    // Multiple toggles
    fireEvent.click(getByTestId("toggle-btn")); // -> true
    expect(cookieStore["sidebar:state"]).toBe("true");

    fireEvent.click(getByTestId("toggle-btn")); // -> false
    expect(cookieStore["sidebar:state"]).toBe("false");

    fireEvent.click(getByTestId("toggle-btn")); // -> true
    expect(cookieStore["sidebar:state"]).toBe("true");
  });

  it("should name the default sidebar trigger", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger />
      </SidebarProvider>,
    );

    expect(
      screen.getByRole("button", { name: /toggle sidebar|ui\.toggleSidebar/i }),
    ).toBeInTheDocument();
  });

  it("should keep a fallback name when custom children replace the default icon", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger>
          <span data-testid="custom-sidebar-icon" aria-hidden="true" />
        </SidebarTrigger>
      </SidebarProvider>,
    );

    expect(screen.getByTestId("custom-sidebar-icon")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /toggle sidebar|ui\.toggleSidebar/i }),
    ).toBeInTheDocument();
  });

  it("should use an explicit accessible name when provided", () => {
    render(
      <SidebarProvider>
        <SidebarTrigger aria-label="Open workspace navigation">
          <span aria-hidden="true" />
        </SidebarTrigger>
      </SidebarProvider>,
    );

    expect(
      screen.getByRole("button", { name: "Open workspace navigation" }),
    ).toBeInTheDocument();
  });

  it("should expose labeled sidebars as complementary landmarks", () => {
    render(
      <SidebarProvider>
        <Sidebar aria-label="Project navigation">Project folders</Sidebar>
      </SidebarProvider>,
    );

    expect(
      screen.getByRole("complementary", { name: "Project navigation" }),
    ).toBeInTheDocument();
  });

  it("should not expose unlabeled shared sidebars as landmarks", () => {
    render(
      <SidebarProvider>
        <Sidebar>Template filters</Sidebar>
      </SidebarProvider>,
    );

    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  describe("persist={false}", () => {
    it("should not write the shared cookie when toggled", () => {
      cookieStore["sidebar:state"] = "true";

      const { getByTestId } = render(
        <SidebarProvider defaultOpen={false} persist={false}>
          <TestComponent />
        </SidebarProvider>,
      );

      fireEvent.click(getByTestId("set-closed-btn"));

      // The page-level sidebar state must survive a local provider's writes.
      expect(cookieStore["sidebar:state"]).toBe("true");
      expect(getByTestId("sidebar-state")).toHaveTextContent("closed");
    });

    it("should honour its own defaultOpen instead of the shared cookie", () => {
      cookieStore["sidebar:state"] = "true";

      const { getByTestId } = render(
        <SidebarProvider defaultOpen={false} persist={false}>
          <TestComponent />
        </SidebarProvider>,
      );

      expect(getByTestId("sidebar-state")).toHaveTextContent("closed");
    });

    it("should not let a mounted Sidebar clobber the shared cookie", () => {
      cookieStore["sidebar:state"] = "true";

      // `Sidebar`'s mount effects call `setOpen` — the exact path that let the
      // TemplatesModal overwrite the flow page's sidebar state.
      render(
        <SidebarProvider defaultOpen={false} persist={false}>
          <Sidebar>Template filters</Sidebar>
        </SidebarProvider>,
      );

      expect(cookieStore["sidebar:state"]).toBe("true");
    });
  });
});
