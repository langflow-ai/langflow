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
        params: { limit: 20, order: "DESC" },
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
      offset: 0,
    });
  });
});
