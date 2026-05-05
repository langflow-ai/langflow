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
  const makeBaseProps = () => {
    const documents = [
      {
        message_id: "msg-1",
        session_id: "session-1",
        sender: "user",
        content: "hello",
        timestamp: "2025-01-01T10:00:00.000Z",
      },
    ];

    return {
      docsData: {
        total: 1,
        sessions: ["session-1"],
        documents,
      },
      docsLoading: false,
      searchQuery: "",
      setSearchQuery: jest.fn(),
      activeSearch: "",
      setActiveSearch: jest.fn(),
      selectedSession: null,
      setSelectedSession: jest.fn(),
      handleSearch: jest.fn(),
      groupedBySession: new Map([["session-1", documents]]),
      handleOpenDocumentPanel: jest.fn(),
      totalChunks: 1,
    } as any;
  };

  it("shows loading state", () => {
    const props = makeBaseProps();
    render(<MemoryKnowledgeBaseSection {...props} docsLoading />);
    expect(screen.getByText("loading...")).toBeInTheDocument();
  });

  it("opens document panel when row is clicked", () => {
    const props = makeBaseProps();
    render(<MemoryKnowledgeBaseSection {...props} />);

    fireEvent.click(screen.getByText("hello"));
    expect(props.handleOpenDocumentPanel).toHaveBeenCalled();
  });

  it("clears active search", () => {
    const props = makeBaseProps();
    render(
      <MemoryKnowledgeBaseSection
        {...props}
        activeSearch="abc"
        searchQuery="abc"
      />,
    );

    const clearButton = screen.getByRole("button", { name: /clear/i });
    fireEvent.click(clearButton);
    expect(props.setSearchQuery).toHaveBeenCalledWith("");
    expect(props.setActiveSearch).toHaveBeenCalledWith("");
  });
});
