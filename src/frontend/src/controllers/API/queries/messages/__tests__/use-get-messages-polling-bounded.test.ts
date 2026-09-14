/**
 * Tests that useGetMessagesPollingMutation reads bounded pages.
 *
 * The mutation re-fetches message history every few seconds, so an unbounded
 * request would re-download a flow's whole history on every cycle.
 */

import { renderHook } from "@testing-library/react";

const FLOW_ID = "flow-id-bounded-polling";

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
    mutate: jest.fn((_key: unknown, fn: (payload: unknown) => unknown) => ({
      mutate: fn,
    })),
  })),
}));

import { MESSAGE_HISTORY_PAGE_SIZE } from "../constants";
import {
  MessagesPollingManager,
  useGetMessagesPollingMutation,
} from "../use-get-messages-polling";

type PollingMutation = {
  mutate: (payload: Record<string, unknown>) => unknown;
};

const startPolling = async (
  mutation: unknown,
  payload: Record<string, unknown>,
) => {
  await Promise.resolve((mutation as PollingMutation).mutate(payload)).catch(
    () => undefined,
  );
};

describe("useGetMessagesPollingMutation - bounded history reads", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    MessagesPollingManager.stopAll();
    mockApiGet.mockResolvedValue({ data: [] });
  });

  afterEach(() => {
    MessagesPollingManager.stopAll();
  });

  it("should_request_a_bounded_page_when_polling_a_flow", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, { id: FLOW_ID, mode: "union" });

    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages", {
      params: { limit: MESSAGE_HISTORY_PAGE_SIZE, flow_id: FLOW_ID },
    });
  });

  it("should_request_a_bounded_page_when_no_flow_id_is_given", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, { mode: "union" });

    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages", {
      params: { limit: MESSAGE_HISTORY_PAGE_SIZE },
    });
  });

  it("should_let_caller_params_override_the_default_page_size", async () => {
    const { result } = renderHook(() => useGetMessagesPollingMutation());

    await startPolling(result.current, {
      id: FLOW_ID,
      mode: "union",
      params: { limit: 20, session_id: "session-1" },
    });

    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages", {
      params: { limit: 20, flow_id: FLOW_ID, session_id: "session-1" },
    });
  });
});
