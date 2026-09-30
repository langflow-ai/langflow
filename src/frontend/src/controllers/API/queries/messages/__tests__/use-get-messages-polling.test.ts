import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import {
  MessagesPollingManager,
  useGetMessagesPollingMutation,
} from "../use-get-messages-polling";

const FLOW_ID = "flow-id-15023";
const MOCK_MESSAGES = [
  {
    id: "msg-1",
    flow_id: FLOW_ID,
    session_id: "s1",
    text: "hello",
    sender: "User",
  },
];
const RESPONSE = { rows: MOCK_MESSAGES, columns: [] };
const mockSetMessages = jest.fn();
jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: { getState: () => ({ setMessages: mockSetMessages }) },
}));
const mockApiGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));
jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));
jest.mock("@/utils/utils", () => ({
  extractColumnsFromRows: jest.fn(() => []),
  prepareSessionIdForAPI: (id: string) => encodeURIComponent(id),
}));

function wrapper() {
  const client = new QueryClient();
  return ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
}

describe("useGetMessagesPollingMutation", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockApiGet.mockResolvedValue({ data: MOCK_MESSAGES });
  });
  afterEach(() => {
    MessagesPollingManager.stopAll();
    jest.useRealTimers();
  });

  it("resolves the initial bounded request and calls success handlers once", async () => {
    const onSuccess = jest.fn();
    const onError = jest.fn();
    const onPollSuccess = jest.fn();
    const { result } = renderHook(
      () => useGetMessagesPollingMutation({ onSuccess, onError }),
      { wrapper: wrapper() },
    );
    await act(async () => {
      await expect(
        result.current.mutateAsync({
          id: FLOW_ID,
          mode: "union",
          onSuccess: onPollSuccess,
        }),
      ).resolves.toEqual(RESPONSE);
    });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages", {
      params: { flow_id: FLOW_ID, limit: 100 },
    });
    expect(mockSetMessages).toHaveBeenCalledWith(MOCK_MESSAGES);
    expect(onSuccess).toHaveBeenCalledTimes(1);
    expect(onPollSuccess).toHaveBeenCalledTimes(1);
    expect(onPollSuccess).toHaveBeenCalledWith(RESPONSE);
    expect(onError).not.toHaveBeenCalled();
  });

  it("passes an explicit limit on every polling cycle", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation(), {
      wrapper: wrapper(),
    });
    await act(async () => {
      await result.current.mutateAsync({ id: FLOW_ID, mode: "union" });
      await jest.advanceTimersByTimeAsync(10000);
    });
    expect(mockApiGet).toHaveBeenCalledTimes(3);
    for (const call of mockApiGet.mock.calls) {
      expect(call[1].params).toEqual({ flow_id: FLOW_ID, limit: 100 });
    }
  });

  it.each([
    [{}, { limit: 100 }],
    [
      { params: { limit: 25, session_id: "session / one" } },
      { limit: 25, session_id: "session%20%2F%20one" },
    ],
  ])(
    "supports polling without a flow and explicit parameter overrides (%j)",
    async (payload, params) => {
      const { result } = renderHook(() => useGetMessagesPollingMutation(), {
        wrapper: wrapper(),
      });
      await act(async () => {
        await result.current.mutateAsync({ mode: "union", ...payload });
      });
      expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages", { params });
    },
  );

  it("reports an API failure and stops the failed initial poll", async () => {
    const error = new Error("Network failure");
    mockApiGet.mockRejectedValue(error);
    const onSuccess = jest.fn();
    const onError = jest.fn();
    const { result } = renderHook(
      () => useGetMessagesPollingMutation({ onSuccess, onError }),
      { wrapper: wrapper() },
    );
    await act(async () => {
      await expect(
        result.current.mutateAsync({ id: FLOW_ID, mode: "union" }),
      ).rejects.toBe(error);
    });
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError.mock.calls[0][0]).toBe(error);
    expect(onSuccess).not.toHaveBeenCalled();
    expect(mockSetMessages).not.toHaveBeenCalled();
    expect(MessagesPollingManager.activePolls.size).toBe(0);
  });

  it("honors the stop predicate on the initial response", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation(), {
      wrapper: wrapper(),
    });
    await act(async () => {
      await result.current.mutateAsync({
        id: FLOW_ID,
        mode: "union",
        stopPollingOn: () => true,
      });
      await jest.advanceTimersByTimeAsync(10000);
    });
    expect(mockApiGet).toHaveBeenCalledTimes(1);
    expect(MessagesPollingManager.activePolls.size).toBe(0);
  });
});
