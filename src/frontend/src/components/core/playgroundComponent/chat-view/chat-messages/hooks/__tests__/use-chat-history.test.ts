import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import React from "react";

const mockGetMessages = jest.fn();
const mockUseGetMessagesQuery = jest.fn();

jest.mock("@/controllers/API/queries/messages", () => ({
  getMessages: (...args: unknown[]) => mockGetMessages(...args),
  useGetMessagesQuery: (...args: unknown[]) => mockUseGetMessagesQuery(...args),
}));

jest.mock(
  "@/components/core/playgroundComponent/hooks/use-get-flow-id",
  () => ({
    useGetFlowId: () => "flow-1",
  }),
);

jest.mock("@/stores/playgroundStore", () => ({
  usePlaygroundStore: (selector: (state: { isOpen: boolean }) => unknown) =>
    selector({ isOpen: true }),
}));

import { findHumanInputContent } from "@/controllers/API/agui/human-input-card";
import type { Message } from "@/types/messages";
import { useChatHistory } from "../use-chat-history";

const createWrapper = (queryClient: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: queryClient }, children);
};

describe("useChatHistory message ordering", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseGetMessagesQuery.mockReturnValue({ data: undefined });
    mockGetMessages.mockResolvedValue({ data: [] });
  });

  it("requests the newest initial page explicitly", () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });

    expect(mockUseGetMessagesQuery).toHaveBeenCalledWith(
      {
        id: "flow-1",
        mode: "union",
        params: { session_id: "session-1", limit: 20, order: "DESC" },
      },
      { enabled: true },
    );
  });

  it("requests older pages through the shared message fetcher in descending order", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockGetMessages).toHaveBeenCalledWith("flow-1", {
      session_id: "session-1",
      limit: 20,
      order: "DESC",
    });
  });

  const page = (from: number) =>
    Array.from({ length: 20 }, (_, index) => ({
      id: `message-${from + index}`,
      timestamp: `timestamp-${from + index}`,
      flow_id: "flow-1",
      session_id: "session-1",
    }));
  const sessionCacheKey = [
    "useGetMessagesQuery",
    { id: "flow-1", session_id: "session-1" },
  ];

  it("continues from the oldest row of the initial page", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mockUseGetMessagesQuery.mockReturnValue({
      data: { rows: { data: page(0) } },
      isPlaceholderData: false,
    });
    mockGetMessages.mockResolvedValueOnce({ data: page(20) });

    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });
    await act(async () => {
      await result.current.loadMore();
    });
    await act(async () => {
      await result.current.loadMore();
    });

    expect(
      mockGetMessages.mock.calls.map(([, params]) => [
        params.before_timestamp,
        params.before_id,
      ]),
    ).toEqual([
      ["timestamp-19", "message-19"],
      ["timestamp-39", "message-39"],
    ]);
  });

  it("stops when a server ignores the cursor and repeats a page", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(sessionCacheKey, page(0));
    mockUseGetMessagesQuery.mockReturnValue({
      data: { rows: { data: page(0) } },
      isPlaceholderData: false,
    });
    mockGetMessages.mockResolvedValue({ data: page(0) });

    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });
    let prepended = -1;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(0);
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
    expect(result.current.hasMore).toBe(false);
  });

  it("does not anchor on placeholder rows from the previous session", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    mockUseGetMessagesQuery.mockReturnValue({
      data: { rows: { data: page(0) } },
      isPlaceholderData: true,
    });

    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });
    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockGetMessages.mock.calls[0][1]).not.toHaveProperty("before_id");
  });

  it("walks past cached pages after a remount instead of stalling", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(sessionCacheKey, page(0));
    mockGetMessages
      .mockResolvedValueOnce({ data: page(0) })
      .mockResolvedValueOnce({ data: page(20).slice(0, 5) });

    const { result } = renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });

    let prepended = -1;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(5);
    expect(
      mockGetMessages.mock.calls.map(([, params]) => params.before_id),
    ).toEqual([undefined, "message-19"]);
    expect(result.current.hasMore).toBe(false);
  });
});

describe("useChatHistory answered HITL cards", () => {
  const sessionCacheKey = [
    "useGetMessagesQuery",
    { id: "flow-1", session_id: "session-1" },
  ];

  const card = (submittedAction?: string) => ({
    id: "card-1",
    flow_id: "flow-1",
    session_id: "session-1",
    sender: "Machine",
    text: "",
    content_blocks: [
      {
        type: "group",
        contents: [
          {
            type: "human_input",
            request_id: "HumanInput-x:run-1",
            options: [{ action_id: "tibia", label: "Tibia" }],
            ...(submittedAction ? { submitted_action: submittedAction } : {}),
          },
        ],
      },
    ],
  });

  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMessages.mockResolvedValue({ data: [] });
  });

  it("adopts the answered state when the decision was made on another surface", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    // The playground was open before the pause, so its cache already holds the
    // unanswered card; the decision was then taken from the canvas badge and only
    // the backend knows about it.
    queryClient.setQueryData(sessionCacheKey, [card()]);
    mockUseGetMessagesQuery.mockReturnValue({
      data: { rows: { data: [card("world_of_warcraft")] } },
    });

    renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {});

    const cached = queryClient.getQueryData<Message[]>(sessionCacheKey) ?? [];
    expect(
      findHumanInputContent(cached[0]?.content_blocks)?.submitted_action,
    ).toBe("world_of_warcraft");
  });

  it("does not clobber a card the cache already answered", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    queryClient.setQueryData(sessionCacheKey, [card("tibia")]);
    mockUseGetMessagesQuery.mockReturnValue({
      data: { rows: { data: [card()] } },
    });

    renderHook(() => useChatHistory("session-1"), {
      wrapper: createWrapper(queryClient),
    });

    await act(async () => {});

    const cached = queryClient.getQueryData<Message[]>(sessionCacheKey) ?? [];
    expect(
      findHumanInputContent(cached[0]?.content_blocks)?.submitted_action,
    ).toBe("tibia");
  });
});
