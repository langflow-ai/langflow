import { fireEvent, render, screen } from "@testing-library/react";
import type { StorageUpgradeStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { useGetStorageStatus } from "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status";
import { usePostStorageRetry } from "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry";
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

jest.mock(
  "@/controllers/API/queries/knowledge-base-storage/use-get-storage-status",
  () => ({ useGetStorageStatus: jest.fn() }),
);
jest.mock(
  "@/controllers/API/queries/knowledge-base-storage/use-post-storage-retry",
  () => ({ usePostStorageRetry: jest.fn() }),
);

let status: StorageUpgradeStatus;
beforeEach(() => {
  status = {
    is_admin: false,
    running: false,
    revision: "first",
    stores: [],
    inventory: { complete: true, issues: 0 },
  };
  jest
    .mocked(useGetStorageStatus)
    .mockImplementation(
      () => ({ data: status }) as ReturnType<typeof useGetStorageStatus>,
    );
  jest.mocked(usePostStorageRetry).mockReturnValue({
    mutate: jest.fn(),
    mutateAsync: jest.fn(),
    reset: jest.fn(),
    data: undefined,
    error: null,
    isPending: false,
    isError: false,
    isIdle: true,
    isSuccess: false,
    isPaused: false,
    status: "idle",
    variables: undefined,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    context: undefined,
  });
});

describe("MemoryKnowledgeBaseSection", () => {
  it("keeps existing message history visible beside the upgrade banner", () => {
    render(
      <MemoryKnowledgeBaseSection
        {...makeBaseProps()}
        storageState="migrating"
      />,
    );
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(
      screen.getByText(/upgrading this base automatically/i),
    ).toBeInTheDocument();
  });
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

  it.each(["migrating", "needs_attention"] as const)(
    "shows a single guidance message for a %s Memory Base",
    (storageState) => {
      status.stores = [
        {
          kb_id: "memory-kb",
          name: "My memory",
          storage_state: storageState,
          phase:
            storageState === "migrating" ? "snapshotting" : "needs_attention",
          migration_id: "migration",
          can_retry: false,
          error_code: "single_host_required",
        },
      ];
      render(
        <MemoryKnowledgeBaseSection
          {...makeBaseProps()}
          storageState={storageState}
          storageKbId="memory-kb"
        />,
      );
      const guidance =
        storageState === "migrating"
          ? /become available when the upgrade finishes/
          : /Contact your administrator/;
      expect(screen.getAllByText(guidance)).toHaveLength(1);
      expect(screen.getByText("hello")).toBeInTheDocument();
    },
  );

  it("shows administrator recovery guidance without telling the administrator to contact themselves", () => {
    status.is_admin = true;
    status.stores = [
      {
        kb_id: "memory-kb",
        name: "My memory",
        storage_state: "needs_attention",
        phase: "needs_attention",
        migration_id: "migration",
        can_retry: true,
        error_code: "legacy_workers_running",
      },
    ];
    render(
      <MemoryKnowledgeBaseSection
        {...makeBaseProps()}
        storageState="needs_attention"
        storageKbId="memory-kb"
      />,
    );
    expect(
      screen.getByText(/Stop the other Langflow instance/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /retry upgrade/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Contact your administrator/),
    ).not.toBeInTheDocument();
  });

  it.each([undefined, "missing-from-status"])(
    "keeps fallback guidance when the detailed inventory has no entry for %s",
    (storageKbId) => {
      render(
        <MemoryKnowledgeBaseSection
          {...makeBaseProps()}
          storageState="needs_attention"
          storageKbId={storageKbId}
        />,
      );
      expect(screen.getAllByText(/Contact your administrator/)).toHaveLength(1);
    },
  );

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
