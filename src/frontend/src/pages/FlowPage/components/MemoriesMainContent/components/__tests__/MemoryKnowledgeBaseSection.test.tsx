import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryKnowledgeBaseSection } from "../MemoryKnowledgeBaseSection";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div>loading...</div>,
}));

describe("MemoryKnowledgeBaseSection", () => {
  const makeProps = (overrides: Partial<any> = {}) => {
    const doc = {
      message_id: "msg-1",
      session_id: "session-1",
      sender: "user",
      content: "hello",
      timestamp: "2025-01-01T10:00:00.000Z",
    };
    return {
      docsData: {
        total: 1,
        sessions: ["session-1"],
        documents: [doc],
      },
      docsLoading: false,
      searchQuery: "",
      setSearchQuery: jest.fn(),
      activeSearch: "",
      setActiveSearch: jest.fn(),
      selectedSession: null,
      setSelectedSession: jest.fn(),
      handleSearch: jest.fn(),
      groupedBySession: new Map([["session-1", [doc]]]),
      handleOpenDocumentPanel: jest.fn(),
      totalChunks: 1,
      ...overrides,
    } as any;
  };

  it("shows loading state", () => {
    const props = makeProps();
    render(<MemoryKnowledgeBaseSection {...props} docsLoading />);
    expect(screen.getByText("loading...")).toBeInTheDocument();
  });

  it("opens document panel when row is clicked", () => {
    const props = makeProps();
    render(<MemoryKnowledgeBaseSection {...props} />);

    fireEvent.click(screen.getByText("hello"));
    expect(props.handleOpenDocumentPanel).toHaveBeenCalled();
  });

  it("clears active search", () => {
    const props = makeProps({ activeSearch: "abc", searchQuery: "abc" });
    render(<MemoryKnowledgeBaseSection {...props} />);

    const clearButton = screen.getByRole("button", { name: /clear search/i });
    fireEvent.click(clearButton);
    expect(props.setSearchQuery).toHaveBeenCalledWith("");
    expect(props.setActiveSearch).toHaveBeenCalledWith("");
  });
});
