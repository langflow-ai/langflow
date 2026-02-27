import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import React from "react";

// ── Mocks ────────────────────────────────────────────────────────────────────

jest.mock("react-router-dom", () => ({
  useParams: () => ({ sourceId: "my_knowledge_base" }),
}));

const mockNavigate = jest.fn();
jest.mock("@/customization/hooks/use-custom-navigate", () => ({
  useCustomNavigate: () => mockNavigate,
}));

const mockGetChunks = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-knowledge-base-chunks",
  () => ({
    useGetKnowledgeBaseChunks: (params: any) => mockGetChunks(params),
  }),
);

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`} />
  ),
}));

jest.mock("@/components/ui/loading", () => ({
  __esModule: true,
  default: () => <div data-testid="loading-spinner" />,
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children }: any) => <div>{children}</div>,
}));

// ── Utilities ────────────────────────────────────────────────────────────────

import { SourceChunksPage } from "../SourceChunksPage";

const makeChunk = (id: string, content: string) => ({
  id,
  content,
  char_count: content.length,
  metadata: null,
});

const makePaginatedResponse = (overrides = {}) => ({
  chunks: [],
  total: 0,
  page: 1,
  limit: 10,
  total_pages: 0,
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("SourceChunksPage", () => {
  describe("Loading state", () => {
    it("shows a loading spinner while data is fetching", () => {
      mockGetChunks.mockReturnValue({
        isLoading: true,
        data: undefined,
        error: null,
      });
      render(<SourceChunksPage />);
      expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
      expect(screen.getByText("Loading Chunks...")).toBeInTheDocument();
    });
  });

  describe("Error state", () => {
    it('shows "Failed to load chunks" when the query errors', () => {
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: undefined,
        error: new Error("Network error"),
      });
      render(<SourceChunksPage />);
      expect(screen.getByText("Failed to load chunks")).toBeInTheDocument();
    });
  });

  describe("Empty state", () => {
    it('shows "No chunks found" when the response has zero chunks', () => {
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse({ chunks: [], total: 0, total_pages: 0 }),
        error: null,
      });
      render(<SourceChunksPage />);
      expect(screen.getByText("No chunks found")).toBeInTheDocument();
    });
  });

  describe("With data", () => {
    const chunks = [
      makeChunk("c1", "First chunk content"),
      makeChunk("c2", "Second chunk content"),
    ];

    beforeEach(() => {
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse({ chunks, total: 2, total_pages: 1 }),
        error: null,
      });
    });

    it("renders a card for each chunk", () => {
      render(<SourceChunksPage />);
      expect(screen.getByText("First chunk content")).toBeInTheDocument();
      expect(screen.getByText("Second chunk content")).toBeInTheDocument();
    });

    it("displays the sourceId in the page header", () => {
      render(<SourceChunksPage />);
      expect(screen.getByText("my_knowledge_base")).toBeInTheDocument();
    });

    it("renders the search input", () => {
      render(<SourceChunksPage />);
      expect(screen.getByTestId("chunks-search-input")).toBeInTheDocument();
    });
  });

  describe("Navigation", () => {
    it("navigates to /assets/knowledge-bases when Back button is clicked", () => {
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse(),
        error: null,
      });
      render(<SourceChunksPage />);

      // The back button contains the ArrowLeft icon (mocked with data-testid)
      const backBtn = screen.getByTestId("icon-ArrowLeft").closest("button")!;
      fireEvent.click(backBtn);
      expect(mockNavigate).toHaveBeenCalledWith("/assets/knowledge-bases");
    });
  });

  describe("Pagination", () => {
    it("shows pagination controls when totalPages > 1", () => {
      const chunks = Array.from({ length: 10 }, (_, i) =>
        makeChunk(`c${i}`, `Chunk ${i} content`),
      );
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse({
          chunks,
          total: 25,
          total_pages: 3,
          page: 1,
        }),
        error: null,
      });
      render(<SourceChunksPage />);
      expect(screen.getByTestId("chunks-page-size-select")).toBeInTheDocument();
      expect(screen.getByText(/of 3/)).toBeInTheDocument();
    });

    it("does not show pagination controls when there is only one page", () => {
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse({
          chunks: [makeChunk("c1", "content")],
          total: 1,
          total_pages: 1,
        }),
        error: null,
      });
      render(<SourceChunksPage />);
      expect(
        screen.queryByTestId("chunks-page-size-select"),
      ).not.toBeInTheDocument();
    });
  });

  describe("Search", () => {
    it("debounces search and passes the query to the API after 300 ms", async () => {
      jest.useFakeTimers();
      mockGetChunks.mockReturnValue({
        isLoading: false,
        data: makePaginatedResponse(),
        error: null,
      });

      render(<SourceChunksPage />);
      const searchInput = screen.getByTestId("chunks-search-input");

      // Simulate typing via fireEvent to avoid clipboard conflict with userEvent
      fireEvent.change(searchInput, { target: { value: "hello" } });

      // Before debounce fires the search param should still be undefined
      const callsBefore = mockGetChunks.mock.calls.filter(
        ([p]) => p.search === "hello",
      );
      expect(callsBefore).toHaveLength(0);

      // After debounce window the query should include the search term
      act(() => jest.advanceTimersByTime(350));
      await waitFor(() => {
        const callsAfter = mockGetChunks.mock.calls.filter(
          ([p]) => p.search === "hello",
        );
        expect(callsAfter.length).toBeGreaterThan(0);
      });

      jest.useRealTimers();
    });
  });
});
