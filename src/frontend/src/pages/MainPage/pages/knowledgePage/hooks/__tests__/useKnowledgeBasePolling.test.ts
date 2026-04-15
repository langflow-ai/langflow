import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import React from "react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";

// ── Mocks ────────────────────────────────────────────────────────────────────

const mockApiGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: any[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: () => "/api/v1/knowledge_bases",
}));

// ── Utilities ────────────────────────────────────────────────────────────────

import { useKnowledgeBasePolling } from "../useKnowledgeBasePolling";

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

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

// ── Tests ────────────────────────────────────────────────────────────────────

describe("useKnowledgeBasePolling", () => {
  describe("pollingRef state", () => {
    it("sets pollingRef.current to true when any KB is in a busy status", () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kbs = [
        makeKb({ status: "ingesting" }),
        makeKb({ dir_name: "kb2", status: "ready" }),
      ];

      const { result } = renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: kbs, tableRef }),
        { wrapper: createWrapper(qc) },
      );

      expect(result.current.pollingRef.current).toBe(true);
    });

    it("sets pollingRef.current to false when no KB is busy", () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kbs = [
        makeKb({ status: "ready" }),
        makeKb({ dir_name: "kb2", status: "empty" }),
      ];

      const { result } = renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: kbs, tableRef }),
        { wrapper: createWrapper(qc) },
      );

      expect(result.current.pollingRef.current).toBe(false);
    });

    it("does not call api.get when pollingRef is false", async () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kbs = [makeKb({ status: "ready" })];

      renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: kbs, tableRef }),
        { wrapper: createWrapper(qc) },
      );

      await act(async () => {
        jest.advanceTimersByTime(6000);
      });

      expect(mockApiGet).not.toHaveBeenCalled();
    });
  });

  describe("polling behavior", () => {
    it("calls api.get after the polling interval when a KB is busy", async () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kb = makeKb({ dir_name: "my_kb", status: "ingesting" });

      mockApiGet.mockResolvedValue({ data: [{ ...kb, status: "ingesting" }] });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: [kb], tableRef }),
        { wrapper: createWrapper(qc) },
      );

      await act(async () => {
        jest.advanceTimersByTime(6000);
        await Promise.resolve();
      });

      expect(mockApiGet).toHaveBeenCalledWith(
        expect.stringContaining("knowledge_bases"),
      );
    });

    it("updates the React Query cache when a KB status changes", async () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kb = makeKb({ dir_name: "my_kb", status: "ingesting" });
      const updatedKb = { ...kb, status: "ready" };

      mockApiGet.mockResolvedValue({ data: [updatedKb] });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: [kb], tableRef }),
        { wrapper: createWrapper(qc) },
      );

      await act(async () => {
        jest.advanceTimersByTime(6000);
        await Promise.resolve();
        await Promise.resolve();
      });

      const cache = qc.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache![0].status).toBe("ready");
    });

    it("calls onStatusChange with the transition when status changes", async () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kb = makeKb({ dir_name: "my_kb", status: "ingesting" });
      const updatedKb = { ...kb, status: "ready" };

      mockApiGet.mockResolvedValue({ data: [updatedKb] });
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      const onStatusChange = jest.fn();

      renderHook(
        () =>
          useKnowledgeBasePolling({
            knowledgeBases: [kb],
            tableRef,
            onStatusChange,
          }),
        { wrapper: createWrapper(qc) },
      );

      await act(async () => {
        jest.advanceTimersByTime(6000);
        await Promise.resolve();
        await Promise.resolve();
      });

      expect(onStatusChange).toHaveBeenCalledWith([
        expect.objectContaining({
          kb: expect.objectContaining({ status: "ready" }),
          previousStatus: "ingesting",
        }),
      ]);
    });

    it("silently ignores polling errors without throwing", async () => {
      const qc = makeQueryClient();
      const tableRef = { current: null };
      const kb = makeKb({ dir_name: "my_kb", status: "ingesting" });

      mockApiGet.mockRejectedValue(new Error("Network error"));
      qc.setQueryData<KnowledgeBaseInfo[]>(["useGetKnowledgeBases"], [kb]);

      renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: [kb], tableRef }),
        { wrapper: createWrapper(qc) },
      );

      await expect(
        act(async () => {
          jest.advanceTimersByTime(6000);
          await Promise.resolve();
          await Promise.resolve();
        }),
      ).resolves.not.toThrow();
    });
  });

  describe("cleanup", () => {
    it("clears the interval on unmount", () => {
      const clearIntervalSpy = jest.spyOn(global, "clearInterval");
      const qc = makeQueryClient();
      const tableRef = { current: null };

      const { unmount } = renderHook(
        () => useKnowledgeBasePolling({ knowledgeBases: [], tableRef }),
        { wrapper: createWrapper(qc) },
      );

      unmount();
      expect(clearIntervalSpy).toHaveBeenCalled();
    });
  });
});
