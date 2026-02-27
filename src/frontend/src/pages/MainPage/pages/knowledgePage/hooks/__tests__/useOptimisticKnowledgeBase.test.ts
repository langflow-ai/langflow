import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import React from "react";
import type { KnowledgeBaseInfo } from "@/controllers/API/queries/knowledge-bases/use-get-knowledge-bases";
import { useOptimisticKnowledgeBase } from "../useOptimisticKnowledgeBase";

const makeKb = (
  overrides: Partial<KnowledgeBaseInfo> = {},
): KnowledgeBaseInfo => ({
  id: "kb-1",
  dir_name: "existing_kb",
  name: "Existing KB",
  embedding_provider: "OpenAI",
  embedding_model: "text-embedding-3-small",
  size: 0,
  words: 0,
  characters: 0,
  chunks: 0,
  avg_chunk_size: 0,
  status: "empty",
  ...overrides,
});

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("useOptimisticKnowledgeBase", () => {
  describe("captureSubmit", () => {
    it("stores submitted form data for later use", () => {
      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper: createWrapper(),
      });

      act(() => {
        result.current.captureSubmit({
          sourceName: "TestKB",
          files: [],
          embeddingModel: null,
        });
      });

      // After capturing, applyOptimisticUpdate should use the data
      let returnValue: boolean = false;
      act(() => {
        returnValue = result.current.applyOptimisticUpdate();
      });
      expect(returnValue).toBe(false); // no files
    });
  });

  describe("applyOptimisticUpdate", () => {
    it("returns false and does nothing when no submit has been captured", () => {
      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper: createWrapper(),
      });

      let returnValue: boolean = true;
      act(() => {
        returnValue = result.current.applyOptimisticUpdate();
      });
      expect(returnValue).toBe(false);
    });

    it('appends a new KB with "empty" status when no files were submitted', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [],
      );

      const wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(
          QueryClientProvider,
          { client: queryClient },
          children,
        );

      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper,
      });

      act(() => {
        result.current.captureSubmit({
          sourceName: "NewKB",
          files: [],
          embeddingModel: null,
        });
        result.current.applyOptimisticUpdate();
      });

      const cache = queryClient.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache).toHaveLength(1);
      expect(cache![0]).toMatchObject({
        dir_name: "NewKB",
        status: "empty",
        name: "NewKB",
      });
    });

    it('appends a new KB with "ingesting" status when files were submitted', () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [],
      );

      const wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(
          QueryClientProvider,
          { client: queryClient },
          children,
        );

      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper,
      });

      const mockFile = new File(["content"], "doc.txt", { type: "text/plain" });

      act(() => {
        result.current.captureSubmit({
          sourceName: "FilledKB",
          files: [mockFile],
          embeddingModel: null,
        });
        result.current.applyOptimisticUpdate();
      });

      const cache = queryClient.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache![0]).toMatchObject({ status: "ingesting" });
    });

    it("returns true when files were submitted", () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [],
      );

      const wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(
          QueryClientProvider,
          { client: queryClient },
          children,
        );

      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper,
      });

      const mockFile = new File(["data"], "report.pdf");
      let returnValue = false;

      act(() => {
        result.current.captureSubmit({
          sourceName: "KB",
          files: [mockFile],
          embeddingModel: null,
        });
        returnValue = result.current.applyOptimisticUpdate();
      });

      expect(returnValue).toBe(true);
    });

    it("updates existing KB status in add-sources mode", () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [makeKb({ dir_name: "existing_kb", status: "empty" })],
      );

      const wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(
          QueryClientProvider,
          { client: queryClient },
          children,
        );

      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper,
      });
      const mockFile = new File(["data"], "new.txt");

      act(() => {
        result.current.captureSubmit({
          sourceName: "existing kb", // spaces → dir_name = 'existing_kb'
          files: [mockFile],
          embeddingModel: null,
        });
        result.current.applyOptimisticUpdate();
      });

      const cache = queryClient.getQueryData<KnowledgeBaseInfo[]>([
        "useGetKnowledgeBases",
      ]);
      expect(cache).toHaveLength(1);
      expect(cache![0]).toMatchObject({
        dir_name: "existing_kb",
        status: "ingesting",
      });
    });

    it("clears the stored submit data after applying the update", () => {
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
      });
      queryClient.setQueryData<KnowledgeBaseInfo[]>(
        ["useGetKnowledgeBases"],
        [],
      );

      const wrapper = ({ children }: { children: React.ReactNode }) =>
        React.createElement(
          QueryClientProvider,
          { client: queryClient },
          children,
        );

      const { result } = renderHook(() => useOptimisticKnowledgeBase(), {
        wrapper,
      });

      act(() => {
        result.current.captureSubmit({
          sourceName: "KB",
          files: [],
          embeddingModel: null,
        });
        result.current.applyOptimisticUpdate();
      });

      // Second call should be a no-op (ref cleared)
      let secondCallReturn = true;
      act(() => {
        secondCallReturn = result.current.applyOptimisticUpdate();
      });
      expect(secondCallReturn).toBe(false);
    });
  });
});
