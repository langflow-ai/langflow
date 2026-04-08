import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryKnowledgeBaseSection } from "../MemoryKnowledgeBaseSection";
import type { MemoryKnowledgeBaseSectionProps } from "../../types";
import type { MemoryDocumentItem } from "@/controllers/API/queries/memories/types";

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
    const documents: MemoryDocumentItem[] = [
      {
        message_id: "msg-1",
        session_id: "session-1",
        sender: "user",
        ingestion_job_id: "job-1",
        ingestion_timestamp: "2025-01-01T10:00:01.000Z",
        content: "hello",
        timestamp: "2025-01-01T10:00:00.000Z",
      },
    ];

    const base: MemoryKnowledgeBaseSectionProps = {
      docsData: {
        total: 1,
        sessions: ["session-1"],
        documents,
      },
      docsLoading: false,
      fetchNextMessagesPage: jest.fn(),
      hasNextMessagesPage: false,
      isFetchingNextMessagesPage: false,
      selectedSession: null,
      setSelectedSession: jest.fn(),
      groupedBySession: new Map([["session-1", documents]]),
      handleOpenDocumentPanel: jest.fn(),
    };

    return base;
  };

  it("shows loading state", () => {
    const props = makeBaseProps();
    render(<MemoryKnowledgeBaseSection {...props} docsLoading />);
    expect(screen.getByText("loading...")).toBeInTheDocument();
  });

  it("shows empty state message when there are no documents", () => {
    const props = {
      ...makeBaseProps(),
      docsData: {
        total: 0,
        sessions: [],
        documents: [],
      },
      groupedBySession: new Map(),
    };

    render(<MemoryKnowledgeBaseSection {...props} />);

    expect(screen.getByText("No chunks yet.")).toBeInTheDocument();
 
  });

  it("opens document panel when row is clicked", () => {
    const props = makeBaseProps();
    render(<MemoryKnowledgeBaseSection {...props} />);

    fireEvent.click(screen.getByText("hello"));
    expect(props.handleOpenDocumentPanel).toHaveBeenCalled();
  });
});
