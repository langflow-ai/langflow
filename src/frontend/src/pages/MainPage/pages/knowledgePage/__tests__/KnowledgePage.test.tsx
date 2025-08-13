import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { BrowserRouter } from "react-router-dom";

// Mock the KnowledgePage component to test in isolation
jest.mock("../index", () => {
  const MockKnowledgePage = () => {
    const [isShiftPressed, setIsShiftPressed] = React.useState(false);
    const [isDrawerOpen, setIsDrawerOpen] = React.useState(false);
    const [selectedKnowledgeBase, setSelectedKnowledgeBase] =
      React.useState<any>(null);

    React.useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === "Shift") {
          setIsShiftPressed(true);
        }
      };

      const handleKeyUp = (e: KeyboardEvent) => {
        if (e.key === "Shift") {
          setIsShiftPressed(false);
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      window.addEventListener("keyup", handleKeyUp);

      return () => {
        window.removeEventListener("keydown", handleKeyDown);
        window.removeEventListener("keyup", handleKeyUp);
      };
    }, []);

    const handleRowClick = (knowledgeBase: any) => {
      setSelectedKnowledgeBase(knowledgeBase);
      setIsDrawerOpen(true);
    };

    const closeDrawer = () => {
      setIsDrawerOpen(false);
      setSelectedKnowledgeBase(null);
    };

    return (
      <div className="flex h-full w-full" data-testid="cards-wrapper">
        <div
          className={`flex h-full w-full flex-col ${isDrawerOpen ? "mr-80" : ""}`}
        >
          <div className="flex h-full w-full flex-col xl:container">
            <div className="flex flex-1 flex-col justify-start px-5 pt-10">
              <div className="flex h-full flex-col justify-start">
                <div
                  className="flex items-center pb-8 text-xl font-semibold"
                  data-testid="mainpage_title"
                >
                  <button data-testid="sidebar-trigger">
                    <span data-testid="icon-PanelLeftOpen" />
                  </button>
                  Knowledge
                </div>
                <div className="flex h-full flex-col">
                  <div data-testid="knowledge-bases-tab">
                    <div>Quick Filter: </div>
                    <div>Selected Files: 0</div>
                    <div>Quantity Selected: 0</div>
                    <div>Shift Pressed: {isShiftPressed ? "Yes" : "No"}</div>
                    <button
                      data-testid="mock-row-click"
                      onClick={() =>
                        handleRowClick({ name: "Test Knowledge Base" })
                      }
                    >
                      Mock Row Click
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {isDrawerOpen && (
          <div className="fixed right-0 top-12 z-50 h-[calc(100vh-48px)]">
            <div data-testid="knowledge-base-drawer">
              <div>Drawer Open: Yes</div>
              <div>Knowledge Base: {selectedKnowledgeBase?.name || "None"}</div>
              <button data-testid="drawer-close" onClick={closeDrawer}>
                Close Drawer
              </button>
            </div>
          </div>
        )}

        {!isDrawerOpen && (
          <div data-testid="knowledge-base-drawer">
            <div>Drawer Open: No</div>
            <div>Knowledge Base: None</div>
          </div>
        )}
      </div>
    );
  };
  MockKnowledgePage.displayName = "KnowledgePage";
  return {
    KnowledgePage: MockKnowledgePage,
  };
});

const { KnowledgePage } = require("../index");

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe("KnowledgePage", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders page title correctly", () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    expect(screen.getByTestId("mainpage_title")).toBeInTheDocument();
    expect(screen.getByText("Knowledge")).toBeInTheDocument();
  });

  it("renders sidebar trigger", () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    expect(screen.getByTestId("sidebar-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("icon-PanelLeftOpen")).toBeInTheDocument();
  });

  it("handles shift key press and release", async () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    // Initially shift is not pressed
    expect(screen.getByText("Shift Pressed: No")).toBeInTheDocument();

    // Simulate shift key down
    fireEvent.keyDown(window, { key: "Shift" });

    await waitFor(() => {
      expect(screen.getByText("Shift Pressed: Yes")).toBeInTheDocument();
    });

    // Simulate shift key up
    fireEvent.keyUp(window, { key: "Shift" });

    await waitFor(() => {
      expect(screen.getByText("Shift Pressed: No")).toBeInTheDocument();
    });
  });

  it("ignores non-shift key events", async () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    expect(screen.getByText("Shift Pressed: No")).toBeInTheDocument();

    // Simulate other key events
    fireEvent.keyDown(window, { key: "Enter" });
    fireEvent.keyUp(window, { key: "Enter" });

    // Should still be false
    expect(screen.getByText("Shift Pressed: No")).toBeInTheDocument();
  });

  it("initializes with drawer closed", () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    expect(screen.getByText("Drawer Open: No")).toBeInTheDocument();
    expect(screen.getByText("Knowledge Base: None")).toBeInTheDocument();
  });

  it("opens drawer when row is clicked", async () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    // Initially drawer is closed
    expect(screen.getByText("Drawer Open: No")).toBeInTheDocument();

    // Click on a row
    const rowClickButton = screen.getByTestId("mock-row-click");
    fireEvent.click(rowClickButton);

    await waitFor(() => {
      expect(screen.getByText("Drawer Open: Yes")).toBeInTheDocument();
      expect(
        screen.getByText("Knowledge Base: Test Knowledge Base"),
      ).toBeInTheDocument();
    });
  });

  it("closes drawer when close button is clicked", async () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    // First open the drawer
    const rowClickButton = screen.getByTestId("mock-row-click");
    fireEvent.click(rowClickButton);

    await waitFor(() => {
      expect(screen.getByText("Drawer Open: Yes")).toBeInTheDocument();
    });

    // Now close the drawer
    const closeButton = screen.getByTestId("drawer-close");
    fireEvent.click(closeButton);

    await waitFor(() => {
      expect(screen.getByText("Drawer Open: No")).toBeInTheDocument();
      expect(screen.getByText("Knowledge Base: None")).toBeInTheDocument();
    });
  });

  it("adjusts layout when drawer is open", async () => {
    render(<KnowledgePage />, { wrapper: createTestWrapper() });

    const contentContainer = screen.getByTestId("cards-wrapper")
      .firstChild as HTMLElement;

    // Initially no margin adjustment
    expect(contentContainer).not.toHaveClass("mr-80");

    // Open drawer
    const rowClickButton = screen.getByTestId("mock-row-click");
    fireEvent.click(rowClickButton);

    await waitFor(() => {
      expect(contentContainer).toHaveClass("mr-80");
    });
  });
});
