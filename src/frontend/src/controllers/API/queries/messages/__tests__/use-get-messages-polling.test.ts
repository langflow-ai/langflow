/**
 * Tests for useGetMessagesPollingMutation bounded polling.
 *
 * Verifies that every poll request carries an explicit limit so a large
 * message history is never fetched in full on each 5s cycle (issue #15023).
 */

import { renderHook } from "@testing-library/react";

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

jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: {
    getState: jest.fn(() => ({
      messages: [],
      setMessages: jest.fn(),
    })),
  },
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

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    mutate: jest.fn((_key: unknown, fn: (payload: unknown) => unknown) => fn),
  })),
}));

import { useGetMessagesPollingMutation } from "../use-get-messages-polling";

// MessagesPollingManager fires the first poll internally when the poll is
// enqueued, so the promise returned by the mutate call can reject benignly
// with "Request already in progress". The data still arrives via the
// manager-triggered fetch.
const startPolling = (
  mutation: unknown,
  payload: Record<string, unknown>,
): Promise<unknown> =>
  Promise.resolve(
    (mutation as (p: Record<string, unknown>) => Promise<unknown>)(payload),
  ).catch(() => undefined);

describe("useGetMessagesPollingMutation - bounded polling", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockApiGet.mockResolvedValue({ data: MOCK_MESSAGES });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("should_pass_explicit_limit_on_immediate_poll", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, { id: FLOW_ID, mode: "union" });
    await jest.advanceTimersByTimeAsync(0);

    expect(mockApiGet).toHaveBeenCalledWith(
      "api/v1/messages",
      expect.objectContaining({
        params: { flow_id: FLOW_ID, limit: 100 },
      }),
    );
  });

  it("should_pass_explicit_limit_on_every_poll_cycle", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, { id: FLOW_ID, mode: "union" });
    await jest.advanceTimersByTimeAsync(0);
    expect(mockApiGet).toHaveBeenCalledTimes(1);

    await jest.advanceTimersByTimeAsync(5000);
    expect(mockApiGet).toHaveBeenCalledTimes(2);

    await jest.advanceTimersByTimeAsync(5000);
    expect(mockApiGet).toHaveBeenCalledTimes(3);

    // Every poll request must include the limit param.
    for (const call of mockApiGet.mock.calls) {
      expect(call[1]).toEqual(
        expect.objectContaining({
          params: expect.objectContaining({ limit: 100 }),
        }),
      );
    }
  });

  it("should_still_apply_limit_when_no_flow_id_is_given", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, { mode: "union" });
    await jest.advanceTimersByTimeAsync(0);

    expect(mockApiGet).toHaveBeenCalledWith(
      "api/v1/messages",
      expect.objectContaining({
        params: { limit: 100 },
      }),
    );
  });
});
