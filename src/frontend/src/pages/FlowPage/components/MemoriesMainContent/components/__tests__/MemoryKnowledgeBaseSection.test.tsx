import { fireEvent, render, screen } from "@testing-library/react";
import type { MemoryDocumentItem } from "@/controllers/API/queries/memories/types";
import type { MemoryKnowledgeBaseSectionProps } from "../../types";
import { MemoryKnowledgeBaseSection } from "../MemoryKnowledgeBaseSection";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div>loading...</div>,
}));

jest.mock("@/components/common/stringReaderComponent", () => ({
  __esModule: true,
  default: ({ string }: { string: string }) => <span>{string}</span>,
}));

jest.mock("@/components/ui/tooltip", () => ({
  Tooltip: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  TooltipContent: ({ children }: { children: React.ReactNode }) => (
    <div role="tooltip">{children}</div>
  ),
  TooltipProvider: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
  TooltipTrigger: ({ children }: { children: React.ReactNode }) => (
    <>{children}</>
  ),
}));

describe("MemoryKnowledgeBaseSection", () => {
  const makeBaseProps = () => {
    const documents: MemoryDocumentItem[] = [
      {
        message_id: "msg-1",
        session_id: "session-1",
        sender: "user",
        job_id: "job-1",
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

    expect(screen.getByText("No chunks yet")).toBeInTheDocument();
  });

  it("shows learn more link in empty state with correct href", () => {
    const props = {
      ...makeBaseProps(),
      docsData: { total: 0, sessions: [], documents: [] },
      groupedBySession: new Map(),
    };
    render(<MemoryKnowledgeBaseSection {...props} />);

    const link = screen.getByRole("link", {
      name: /learn more about memory bases/i,
    });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute(
      "href",
      "https://docs.langflow.org/memory-bases",
    );
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("shows tooltip description for the Memory Base heading", () => {
    render(<MemoryKnowledgeBaseSection {...makeBaseProps()} />);
    expect(
      screen.getByText(/store of processed conversation chunks/i),
    ).toBeInTheDocument();
  });

  it("shows read the docs link in Memory Base heading tooltip", () => {
    render(<MemoryKnowledgeBaseSection {...makeBaseProps()} />);
    const links = screen.getAllByRole("link", { name: /read the docs/i });
    expect(links[0]).toHaveAttribute(
      "href",
      "https://docs.langflow.org/memory-bases",
    );
    expect(links[0]).toHaveAttribute("target", "_blank");
  });

  it("shows tooltip description for the chunks count", () => {
    render(<MemoryKnowledgeBaseSection {...makeBaseProps()} />);
    expect(
      screen.getByText(/units of processed conversation content/i),
    ).toBeInTheDocument();
  });

  it("opens document panel when row is clicked", () => {
    const props = makeBaseProps();
    render(<MemoryKnowledgeBaseSection {...props} />);

    // Cells stop propagation so clicking cell text does not open the panel.
    // Click the row element itself to trigger handleOpenDocumentPanel.
    const row = screen.getByText("hello").closest("tr")!;
    fireEvent.click(row);
    expect(props.handleOpenDocumentPanel).toHaveBeenCalled();
  });
});
