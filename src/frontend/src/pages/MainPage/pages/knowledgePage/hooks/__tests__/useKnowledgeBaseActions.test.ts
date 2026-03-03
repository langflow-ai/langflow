import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import React from "react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockCancelMutate = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-cancel-ingestion",
  () => ({
    useCancelIngestion: ({ onSuccess, onError }: any) => ({
      mutate: (args: any) => {
        mockCancelMutate(args);
      },
      isPending: false,
      _onSuccess: onSuccess,
      _onError: onError,
    }),
  }),
);

const mockDeleteMutate = jest.fn();
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-delete-knowledge-base",
  () => ({
    useDeleteKnowledgeBase: ({ onSuccess, onError }: any) => ({
      mutate: (args: any) => {
        mockDeleteMutate(args);
      },
      isPending: false,
      _onSuccess: onSuccess,
      _onError: onError,
    }),
  }),
);

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => {
  const store = jest.fn((selector) => {
    const state = {
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    };
    return typeof selector === "function" ? selector(state) : state;
  });
  return { __esModule: true, default: store };
});

// ── Utilities ────────────────────────────────────────────────────────────────

import { useKnowledgeBaseActions } from "../useKnowledgeBaseActions";

const makeKb = (
  overrides: Partial<KnowledgeBaseInfo> = {},
): KnowledgeBaseInfo => ({
  id: "kb-1",
  dir_name: "my_kb",
  name: "My KB",
  embedding_provider: "OpenAI",
  embedding_model: "text-embedding-3-small",
  size: 0,
  words: 0,
  characters: 0,
  chunks: 0,
  avg_chunk_size: 0,
  status: "ready",
  ...overrides,
});

const createWrapper =
  (queryClient: QueryClient) =>
  ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);

const makeQueryClient = () =>
  new QueryClient({ defaultOptions: { queries: { retry: false } } });

const defaultOptions = {
  refetch: jest.fn(),
  selectedFiles: [] as KnowledgeBaseInfo[],
  clearSelection: jest.fn(),
};

beforeEach(() => jest.clearAllMocks());

// ── Tests ────────────────────────────────────────────────────────────────────

describe("useKnowledgeBaseActions", () => {
  describe("handleDelete", () => {
    it("sets knowledgeBaseToDelete and opens the delete modal", () => {
      const qc = makeQueryClient();
      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      const kb = makeKb();
      act(() => result.current.handleDelete(kb));

      expect(result.current.knowledgeBaseToDelete).toEqual(kb);
      expect(result.current.isDeleteModalOpen).toBe(true);
    });
  });

  describe("confirmDelete", () => {
    it("optimistically removes the KB from the query cache", () => {
      const qc = makeQueryClient();
      const kb = makeKb({ dir_name: "target_kb" });
      qc.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [kb, makeKb({ dir_name: "other_kb" })],
      );

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleDelete(kb));
      act(() => result.current.confirmDelete());

      const cache = qc.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache?.map((k) => k.dir_name)).not.toContain("target_kb");
      expect(cache?.map((k) => k.dir_name)).toContain("other_kb");
    });

    it("calls deleteKnowledgeBase.mutate with the dir_name", () => {
      const qc = makeQueryClient();
      const kb = makeKb({ dir_name: "to_delete" });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleDelete(kb));
      act(() => result.current.confirmDelete());

      expect(mockDeleteMutate).toHaveBeenCalledWith({ kb_names: "to_delete" });
    });

    it("resets delete modal state after confirming", () => {
      const qc = makeQueryClient();
      const kb = makeKb();
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleDelete(kb));
      act(() => result.current.confirmDelete());

      expect(result.current.isDeleteModalOpen).toBe(false);
      expect(result.current.knowledgeBaseToDelete).toBeNull();
    });
  });

  describe("confirmBulkDelete", () => {
    it("calls mutate with all non-busy selected KB dir_names", () => {
      const qc = makeQueryClient();
      const readyKb = makeKb({ dir_name: "ready_kb", status: "ready" });
      const ingestingKb = makeKb({
        dir_name: "ingesting_kb",
        status: "ingesting",
      });
      qc.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [readyKb, ingestingKb],
      );

      const { result } = renderHook(
        () =>
          useKnowledgeBaseActions({
            ...defaultOptions,
            selectedFiles: [readyKb, ingestingKb],
          }),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.confirmBulkDelete());

      expect(mockDeleteMutate).toHaveBeenCalledWith({
        kb_names: ["ready_kb"],
      });
    });

    it("does not call mutate when all selected KBs are busy", () => {
      const qc = makeQueryClient();
      const ingestingKb = makeKb({
        dir_name: "ingesting_kb",
        status: "ingesting",
      });

      const { result } = renderHook(
        () =>
          useKnowledgeBaseActions({
            ...defaultOptions,
            selectedFiles: [ingestingKb],
          }),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.confirmBulkDelete());
      expect(mockDeleteMutate).not.toHaveBeenCalled();
    });

    it("calls clearSelection after confirming bulk delete", () => {
      const qc = makeQueryClient();
      const clearSelection = jest.fn();
      const readyKb = makeKb({ dir_name: "r", status: "ready" });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [readyKb]);

      const { result } = renderHook(
        () =>
          useKnowledgeBaseActions({
            ...defaultOptions,
            selectedFiles: [readyKb],
            clearSelection,
          }),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.confirmBulkDelete());
      expect(clearSelection).toHaveBeenCalledTimes(1);
    });
  });

  describe("handleStopIngestion", () => {
    it('sets the KB status to "cancelling" in the query cache', () => {
      const qc = makeQueryClient();
      const kb = makeKb({ dir_name: "ingesting_kb", status: "ingesting" });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleStopIngestion(kb));

      const cache = qc.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache![0].status).toBe("cancelling");
    });

    it("calls cancelIngestionMutation.mutate with the dir_name", () => {
      const qc = makeQueryClient();
      const kb = makeKb({ dir_name: "my_ingesting_kb", status: "ingesting" });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleStopIngestion(kb));
      expect(mockCancelMutate).toHaveBeenCalledWith({
        kb_name: "my_ingesting_kb",
      });
    });
  });

  describe("handleAddSources", () => {
    it("sets knowledgeBaseForAddSources to the selected KB", () => {
      const qc = makeQueryClient();
      const kb = makeKb({ dir_name: "add_sources_kb" });

      const { result } = renderHook(
        () => useKnowledgeBaseActions(defaultOptions),
        { wrapper: createWrapper(qc) },
      );

      act(() => result.current.handleAddSources(kb));
      expect(result.current.knowledgeBaseForAddSources).toEqual(kb);
    });
  });

  describe("deletableSelected", () => {
    it("excludes KBs with busy status from the deletable set", () => {
      const qc = makeQueryClient();
      const readyKb = makeKb({ dir_name: "r", status: "ready" });
      const ingestingKb = makeKb({ dir_name: "i", status: "ingesting" });
      const cancellingKb = makeKb({ dir_name: "c", status: "cancelling" });

      const { result } = renderHook(
        () =>
          useKnowledgeBaseActions({
            ...defaultOptions,
            selectedFiles: [readyKb, ingestingKb, cancellingKb],
          }),
        { wrapper: createWrapper(qc) },
      );

      expect(result.current.deletableSelected).toEqual([readyKb]);
    });
  });
});
