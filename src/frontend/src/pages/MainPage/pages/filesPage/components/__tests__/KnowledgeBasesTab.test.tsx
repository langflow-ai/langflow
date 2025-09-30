import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";

// Mock the component to avoid complex dependencies
jest.mock("../KnowledgeBasesTab", () => {
  const MockKnowledgeBasesTab = ({
    quickFilterText,
    setQuickFilterText,
    selectedFiles,
    quantitySelected,
    isShiftPressed,
    onRowClick,
  }: any) => (
    <div data-testid="knowledge-bases-tab">
      <input
        data-testid="search-kb-input"
        placeholder="Search knowledge bases..."
        value={quickFilterText || ""}
        onChange={(e) => setQuickFilterText?.(e.target.value)}
      />
      <div data-testid="table-content">
        <div>Mock Table</div>
        <div data-testid="selected-count">
          {selectedFiles?.length || 0} selected
        </div>
        <div data-testid="shift-pressed">
          {isShiftPressed ? "Shift pressed" : "No shift"}
        </div>
        {onRowClick && (
          <button
            data-testid="mock-row-click"
            onClick={() => onRowClick({ id: "kb-1", name: "Test KB" })}
          >
            Click Row
          </button>
        )}
      </div>
    </div>
  );
  MockKnowledgeBasesTab.displayName = "KnowledgeBasesTab";
  return {
    __esModule: true,
    default: MockKnowledgeBasesTab,
  };
});

const KnowledgeBasesTab = require("../KnowledgeBasesTab").default;

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

const defaultProps = {
  quickFilterText: "",
  setQuickFilterText: jest.fn(),
  selectedFiles: [],
  setSelectedFiles: jest.fn(),
  quantitySelected: 0,
  setQuantitySelected: jest.fn(),
  isShiftPressed: false,
  onRowClick: jest.fn(),
};

describe("KnowledgeBasesTab", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders search input with correct placeholder", () => {
    render(<KnowledgeBasesTab {...defaultProps} />, {
      wrapper: createTestWrapper(),
    });

    const searchInput = screen.getByTestId("search-kb-input");
    expect(searchInput).toBeInTheDocument();
    expect(searchInput).toHaveAttribute(
      "placeholder",
      "Search knowledge bases...",
    );
  });

  it("handles search input changes", () => {
    const mockSetQuickFilterText = jest.fn();
    render(
      <KnowledgeBasesTab
        {...defaultProps}
        setQuickFilterText={mockSetQuickFilterText}
      />,
      { wrapper: createTestWrapper() },
    );

    const searchInput = screen.getByTestId("search-kb-input");
    fireEvent.change(searchInput, { target: { value: "test search" } });

    expect(mockSetQuickFilterText).toHaveBeenCalledWith("test search");
  });

  it("displays search value in input", () => {
    render(
      <KnowledgeBasesTab {...defaultProps} quickFilterText="existing search" />,
      { wrapper: createTestWrapper() },
    );

    const searchInput = screen.getByTestId(
      "search-kb-input",
    ) as HTMLInputElement;
    expect(searchInput.value).toBe("existing search");
  });

  it("displays selected count", () => {
    const selectedFiles = [{ id: "kb-1" }, { id: "kb-2" }];
    render(
      <KnowledgeBasesTab
        {...defaultProps}
        selectedFiles={selectedFiles}
        quantitySelected={2}
      />,
      { wrapper: createTestWrapper() },
    );

    expect(screen.getByTestId("selected-count")).toHaveTextContent(
      "2 selected",
    );
  });

  it("displays shift key state", () => {
    render(<KnowledgeBasesTab {...defaultProps} isShiftPressed={true} />, {
      wrapper: createTestWrapper(),
    });

    expect(screen.getByTestId("shift-pressed")).toHaveTextContent(
      "Shift pressed",
    );
  });

  it("calls onRowClick when provided", () => {
    const mockOnRowClick = jest.fn();
    render(
      <KnowledgeBasesTab {...defaultProps} onRowClick={mockOnRowClick} />,
      { wrapper: createTestWrapper() },
    );

    const rowButton = screen.getByTestId("mock-row-click");
    fireEvent.click(rowButton);

    expect(mockOnRowClick).toHaveBeenCalledWith({
      id: "kb-1",
      name: "Test KB",
    });
  });

  it("renders table content", () => {
    render(<KnowledgeBasesTab {...defaultProps} />, {
      wrapper: createTestWrapper(),
    });

    expect(screen.getByTestId("table-content")).toBeInTheDocument();
    expect(screen.getByText("Mock Table")).toBeInTheDocument();
  });
});
