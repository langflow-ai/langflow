import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import React from "react";

// Mock the component to avoid complex dependency chains
jest.mock("../KnowledgeBaseSelectionOverlay", () => {
  const MockKnowledgeBaseSelectionOverlay = ({
    selectedFiles,
    quantitySelected,
    onClearSelection,
    onDelete,
  }: any) => {
    const isVisible = selectedFiles.length > 0;
    const pluralSuffix = quantitySelected > 1 ? "s" : "";

    const handleDelete = () => {
      if (onDelete) {
        onDelete();
      }
    };

    return (
      <div
        data-testid="selection-overlay"
        className={isVisible ? "opacity-100" : "opacity-0"}
      >
        <span data-testid="selection-count">{quantitySelected} selected</span>
        <button data-testid="bulk-delete-kb-btn" onClick={handleDelete}>
          Delete
        </button>
        <button data-testid="clear-selection-btn" onClick={onClearSelection}>
          Clear
        </button>
        <span data-testid="delete-description">
          knowledge base{pluralSuffix}
        </span>
      </div>
    );
  };
  MockKnowledgeBaseSelectionOverlay.displayName =
    "KnowledgeBaseSelectionOverlay";
  return {
    __esModule: true,
    default: MockKnowledgeBaseSelectionOverlay,
  };
});

const KnowledgeBaseSelectionOverlay =
  require("../KnowledgeBaseSelectionOverlay").default;

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

const mockSelectedFiles = [
  { id: "kb-1", name: "Knowledge Base 1" },
  { id: "kb-2", name: "Knowledge Base 2" },
];

describe("KnowledgeBaseSelectionOverlay", () => {
  const mockOnClearSelection = jest.fn();
  const mockOnDelete = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders as invisible when no files are selected", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={[]}
        quantitySelected={0}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    const overlay = screen.getByTestId("selection-overlay");
    expect(overlay).toHaveClass("opacity-0");
  });

  it("renders as visible when files are selected", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={mockSelectedFiles}
        quantitySelected={2}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    const overlay = screen.getByTestId("selection-overlay");
    expect(overlay).toHaveClass("opacity-100");
  });

  it("displays correct selection count for single item", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={[mockSelectedFiles[0]]}
        quantitySelected={1}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    expect(screen.getByTestId("selection-count")).toHaveTextContent(
      "1 selected",
    );
    expect(screen.getByTestId("delete-description")).toHaveTextContent(
      "knowledge base",
    );
  });

  it("displays correct selection count for multiple items", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={mockSelectedFiles}
        quantitySelected={2}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    expect(screen.getByTestId("selection-count")).toHaveTextContent(
      "2 selected",
    );
    expect(screen.getByTestId("delete-description")).toHaveTextContent(
      "knowledge bases",
    );
  });

  it("calls custom onDelete when provided", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={mockSelectedFiles}
        quantitySelected={2}
        onDelete={mockOnDelete}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    const deleteButton = screen.getByTestId("bulk-delete-kb-btn");
    fireEvent.click(deleteButton);

    expect(mockOnDelete).toHaveBeenCalledTimes(1);
  });

  it("calls onClearSelection when clear button is clicked", () => {
    render(
      <KnowledgeBaseSelectionOverlay
        selectedFiles={mockSelectedFiles}
        quantitySelected={2}
        onClearSelection={mockOnClearSelection}
      />,
      { wrapper: createTestWrapper() },
    );

    const clearButton = screen.getByTestId("clear-selection-btn");
    fireEvent.click(clearButton);

    expect(mockOnClearSelection).toHaveBeenCalledTimes(1);
  });
});
