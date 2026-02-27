import { fireEvent, render, screen } from "@testing-library/react";
import { Sidebar, SidebarProvider, SidebarRail, useSidebar } from "../sidebar";

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
});

describe("SidebarRail and Resizing", () => {
  const MIN_SIDEBAR_WIDTH = 275;
  const MAX_SIDEBAR_WIDTH = 800;
  const DEFAULT_WIDTH = "21rem";

  it("should update width on drag and honor constraints", () => {
    const { container } = render(
      <SidebarProvider>
        <Sidebar>
          <SidebarRail data-testid="sidebar-rail" />
        </Sidebar>
      </SidebarProvider>,
    );

    const rail = screen.getByTestId("sidebar-rail");
    const wrapper = container.querySelector(
      ".group\\/sidebar-wrapper",
    ) as HTMLElement;

    // Initial width
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe(
      DEFAULT_WIDTH,
    );

    // Mock parent width for calculation (21rem approx 336px)
    const sidebarElement = rail.parentElement!;
    jest.spyOn(sidebarElement, "getBoundingClientRect").mockReturnValue({
      width: 336,
    } as DOMRect);

    // 1. Start drag
    fireEvent.mouseDown(rail, { clientX: 336 });
    expect(wrapper.getAttribute("data-resizing")).toBe("true");

    // 2. Drag to 436 (+100px)
    fireEvent.mouseMove(window, { clientX: 436 });
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe("436px");

    // 3. Drag to MAX_SIDEBAR_WIDTH + 100
    fireEvent.mouseMove(window, { clientX: 336 + MAX_SIDEBAR_WIDTH + 100 });
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe(
      `${MAX_SIDEBAR_WIDTH}px`,
    );

    // 4. Drag to MIN_SIDEBAR_WIDTH - 100
    fireEvent.mouseMove(window, { clientX: 336 - 200 });
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe(
      `${MIN_SIDEBAR_WIDTH}px`,
    );

    // 5. Release
    fireEvent.mouseUp(window);
    expect(wrapper.getAttribute("data-resizing")).toBe("false");
  });

  it("should reset to default width on double click", () => {
    const { container } = render(
      <SidebarProvider>
        <Sidebar>
          <SidebarRail data-testid="sidebar-rail" />
        </Sidebar>
      </SidebarProvider>,
    );

    const rail = screen.getByTestId("sidebar-rail");
    const wrapper = container.querySelector(
      ".group\\/sidebar-wrapper",
    ) as HTMLElement;

    // Change width first
    const sidebarElement = rail.parentElement!;
    jest.spyOn(sidebarElement, "getBoundingClientRect").mockReturnValue({
      width: 336,
    } as DOMRect);
    fireEvent.mouseDown(rail, { clientX: 336 });
    fireEvent.mouseMove(window, { clientX: 500 });
    fireEvent.mouseUp(window);
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe("500px");

    // Double click to reset
    fireEvent.mouseDown(rail, { detail: 2 });
    expect(wrapper.style.getPropertyValue("--sidebar-width")).toBe(
      DEFAULT_WIDTH,
    );
  });

  it("should toggle sidebar on click when not dragging", () => {
    const Test = () => {
      const { open } = useSidebar();
      return (
        <>
          <SidebarRail data-testid="sidebar-rail" />
          <span>{open ? "open" : "closed"}</span>
        </>
      );
    };

    render(
      <SidebarProvider>
        <Sidebar>
          <Test />
        </Sidebar>
      </SidebarProvider>,
    );

    const rail = screen.getByTestId("sidebar-rail");
    expect(screen.getByText("open")).toBeInTheDocument();

    fireEvent.click(rail);
    expect(screen.getByText("closed")).toBeInTheDocument();

    fireEvent.click(rail);
    expect(screen.getByText("open")).toBeInTheDocument();
  });
});
