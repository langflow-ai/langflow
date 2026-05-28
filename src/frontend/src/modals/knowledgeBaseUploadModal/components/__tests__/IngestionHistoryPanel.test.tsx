import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

const mockUseGetIngestionRuns = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-ingestion-runs",
  () => ({
    useGetIngestionRuns: (...args: unknown[]) =>
      mockUseGetIngestionRuns(...args),
  }),
);

import { IngestionHistoryPanel } from "../IngestionHistoryPanel";

const makeRun = (overrides = {}) => ({
  id: "run-1",
  kb_name: "my_kb",
  kb_id: null,
  job_id: null,
  source_type: "file_upload",
  source_name: null as string | null,
  status: "succeeded",
  error_message: null,
  total_items: 3,
  succeeded: 3,
  failed: 0,
  skipped: 0,
  total_bytes: 1024,
  chunks_created: 12,
  started_at: new Date(Date.now() - 60_000).toISOString(),
  finished_at: null,
  ...overrides,
});

describe("IngestionHistoryPanel", () => {
  beforeEach(() => {
    mockUseGetIngestionRuns.mockReset();
  });

  it("shows empty state when no runs exist", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: { runs: [], total: 0, page: 1, limit: 10, total_pages: 0 },
      isLoading: false,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    expect(
      screen.getByTestId("kb-ingestion-history-empty"),
    ).toBeInTheDocument();
  });

  it("shows loading state", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    expect(
      screen.getByTestId("kb-ingestion-history-loading"),
    ).toBeInTheDocument();
  });

  it("shows error state when fetch fails", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    expect(
      screen.getByText("Unable to load ingestion history."),
    ).toBeInTheDocument();
  });

  it("falls back to type label when source_name missing", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: {
        runs: [
          makeRun({
            id: "r1",
            status: "succeeded",
            source_type: "file_upload",
            source_name: null,
          }),
          makeRun({
            id: "r2",
            status: "partial",
            source_type: "google_drive",
            source_name: null,
          }),
        ],
        total: 2,
        page: 1,
        limit: 10,
        total_pages: 1,
      },
      isLoading: false,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    const rows = screen.getAllByTestId("kb-ingestion-history-row");
    expect(rows).toHaveLength(2);
    expect(screen.getByText("File Upload")).toBeInTheDocument();
    expect(screen.getByText("Google Drive")).toBeInTheDocument();
    expect(screen.getByText("succeeded")).toBeInTheDocument();
    expect(screen.getByText("partial")).toBeInTheDocument();
  });

  it("prefers user-typed source_name over type label, with type as subtitle", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: {
        runs: [
          makeRun({
            id: "r1",
            source_type: "file_upload",
            source_name: "Test6",
          }),
        ],
        total: 1,
        page: 1,
        limit: 10,
        total_pages: 1,
      },
      isLoading: false,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    const sourceLabel = screen.getByTestId("kb-ingestion-history-source-name");
    expect(sourceLabel).toHaveTextContent("Test6");
    expect(screen.getAllByText("File Upload").length).toBeGreaterThan(0);
  });

  it("treats whitespace-only source_name as missing", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: {
        runs: [
          makeRun({
            id: "r1",
            source_type: "file_upload",
            source_name: "   ",
          }),
        ],
        total: 1,
        page: 1,
        limit: 10,
        total_pages: 1,
      },
      isLoading: false,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    const sourceLabel = screen.getByTestId("kb-ingestion-history-source-name");
    expect(sourceLabel).toHaveTextContent("File Upload");
    // Whitespace-only source_name → no subtitle, only the primary label has it.
    expect(screen.getAllByText("File Upload")).toHaveLength(1);
  });

  it("collapses and expands when header is toggled", async () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: {
        runs: [makeRun()],
        total: 1,
        page: 1,
        limit: 10,
        total_pages: 1,
      },
      isLoading: false,
      isError: false,
    });
    const user = userEvent.setup();
    render(<IngestionHistoryPanel kbName="my_kb" />);

    expect(screen.getByTestId("kb-ingestion-history-row")).toBeInTheDocument();

    await user.click(screen.getByTestId("kb-ingestion-history-toggle"));

    expect(
      screen.queryByTestId("kb-ingestion-history-row"),
    ).not.toBeInTheDocument();
  });

  it("calls useGetIngestionRuns with kbName + fresh-data options", () => {
    mockUseGetIngestionRuns.mockReturnValue({
      data: { runs: [], total: 0, page: 1, limit: 10, total_pages: 0 },
      isLoading: false,
      isError: false,
    });
    render(<IngestionHistoryPanel kbName="my_kb" />);
    expect(mockUseGetIngestionRuns).toHaveBeenCalledWith(
      expect.objectContaining({ kb_name: "my_kb", page: 1, limit: 10 }),
      expect.objectContaining({ staleTime: 0, refetchOnMount: "always" }),
    );
  });
});
