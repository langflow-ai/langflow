import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import React from "react";

// Mock the axios instance the hooks talk to.
const mockApiGet = jest.fn();
const mockApiPost = jest.fn();
const mockApiDelete = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: {
    get: (...args: unknown[]) => mockApiGet(...args),
    post: (...args: unknown[]) => mockApiPost(...args),
    delete: (...args: unknown[]) => mockApiDelete(...args),
  },
}));

import {
  type CodeFile,
  type Message,
  type Project,
  useCode,
  useCreateProject,
  useDeleteProject,
  useMessages,
  useProjects,
  useSendMessage,
} from "../index";

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const invalidateSpy = jest.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
  return { queryClient, invalidateSpy, wrapper };
}

const PROJECT: Project = {
  id: "p1",
  user_id: "u1",
  name: "Demo",
  phase: "CLARIFICATION",
  prd_content: null,
  diagram_mmd: null,
  diagram_layout: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MESSAGE: Message = {
  id: "m1",
  project_id: "p1",
  role: "ASSISTANT",
  content: "hi",
  suggestions: [],
  phase: "CLARIFICATION",
  created_at: "2026-01-01T00:00:00Z",
};

const CODE_FILE: CodeFile = { path: "src/main.py", content: "print('hi')\n" };

describe("lothal queries", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("useProjects", () => {
    it("GETs the projects list", async () => {
      mockApiGet.mockResolvedValue({ data: [PROJECT] });
      const { wrapper } = setup();
      const { result } = renderHook(() => useProjects(), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockApiGet).toHaveBeenCalledWith("/api/v1/lothal/projects/");
      expect(result.current.data).toEqual([PROJECT]);
    });

    it("surfaces errors (e.g. the 501 stub) instead of throwing", async () => {
      mockApiGet.mockRejectedValue(new Error("Not Implemented"));
      const { wrapper } = setup();
      const { result } = renderHook(() => useProjects(), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.data).toBeUndefined();
    });
  });

  describe("useCreateProject", () => {
    it("POSTs the name and invalidates the projects list", async () => {
      mockApiPost.mockResolvedValue({ data: PROJECT });
      const { wrapper, invalidateSpy } = setup();
      const { result } = renderHook(() => useCreateProject(), { wrapper });

      await act(async () => {
        await result.current.mutateAsync("Demo");
      });

      expect(mockApiPost).toHaveBeenCalledWith("/api/v1/lothal/projects/", {
        name: "Demo",
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["lothal", "projects"],
      });
    });
  });

  describe("useDeleteProject", () => {
    it("DELETEs by id and invalidates the projects list", async () => {
      mockApiDelete.mockResolvedValue({});
      const { wrapper, invalidateSpy } = setup();
      const { result } = renderHook(() => useDeleteProject(), { wrapper });

      await act(async () => {
        await result.current.mutateAsync("p1");
      });

      expect(mockApiDelete).toHaveBeenCalledWith("/api/v1/lothal/projects/p1");
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["lothal", "projects"],
      });
    });
  });

  describe("useMessages", () => {
    it("GETs the per-project message history", async () => {
      mockApiGet.mockResolvedValue({ data: [MESSAGE] });
      const { wrapper } = setup();
      const { result } = renderHook(() => useMessages("p1"), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/lothal/projects/p1/messages",
      );
      expect(result.current.data).toEqual([MESSAGE]);
    });
  });

  describe("useCode", () => {
    it("GETs the project's files, unwrapping the `files` envelope", async () => {
      mockApiGet.mockResolvedValue({ data: { files: [CODE_FILE] } });
      const { wrapper } = setup();
      const { result } = renderHook(() => useCode("p1"), { wrapper });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      expect(mockApiGet).toHaveBeenCalledWith(
        "/api/v1/lothal/projects/p1/code",
      );
      expect(result.current.data).toEqual([CODE_FILE]);
    });

    it("surfaces the 501 stub as an error (without retrying it)", async () => {
      // The structured 501 is terminal — the hook must not retry it, so the
      // NotReady state appears immediately.
      mockApiGet.mockRejectedValue({ response: { status: 501 } });
      const { wrapper } = setup();
      const { result } = renderHook(() => useCode("p1"), { wrapper });

      await waitFor(() => expect(result.current.isError).toBe(true));
      expect(result.current.data).toBeUndefined();
      expect(mockApiGet).toHaveBeenCalledTimes(1);
    });
  });

  describe("useSendMessage", () => {
    it("POSTs chat content and invalidates both messages and projects", async () => {
      const reply: Message = { ...MESSAGE, id: "m2", content: "reply" };
      mockApiPost.mockResolvedValue({ data: reply });
      const { wrapper, invalidateSpy } = setup();
      const { result } = renderHook(() => useSendMessage("p1"), { wrapper });

      let returned: Message | undefined;
      await act(async () => {
        returned = await result.current.mutateAsync("hello");
      });

      expect(mockApiPost).toHaveBeenCalledWith(
        "/api/v1/lothal/projects/p1/chat",
        { content: "hello" },
      );
      expect(returned).toEqual(reply);
      // The reply may advance the phase, so both caches are refreshed.
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["lothal", "messages", "p1"],
      });
      expect(invalidateSpy).toHaveBeenCalledWith({
        queryKey: ["lothal", "projects"],
      });
    });
  });
});
