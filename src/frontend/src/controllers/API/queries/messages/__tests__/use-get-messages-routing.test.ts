/**
 * Tests for useGetMessagesQuery routing logic.
 *
 * Verifies that the query routes to the correct data source:
 * - Standard API (regular playground)
 * - Shared API (authenticated shareable playground)
 * - sessionStorage (anonymous/auto-login shareable playground)
 */

const FLOW_ID = "virtual-flow-id-123";
const SOURCE_FLOW_ID = "real-flow-id-456";
const MOCK_MESSAGES = [
  {
    id: "msg-1",
    flow_id: FLOW_ID,
    session_id: "s1",
    text: "hello",
    sender: "User",
  },
  {
    id: "msg-2",
    flow_id: FLOW_ID,
    session_id: "s1",
    text: "hi",
    sender: "Machine",
  },
];

// Mock all external dependencies
jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: jest.fn() },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: { getState: jest.fn(() => ({ currentFlowId: SOURCE_FLOW_ID })) },
}));

jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: {
    getState: jest.fn(() => ({
      messages: [],
      setMessages: jest.fn(),
    })),
  },
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: jest.fn(),
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
  prepareSessionIdForAPI: (id: string) => id,
}));

jest.mock("@/controllers/API/services/request-processor", () => ({
  UseRequestProcessor: jest.fn(() => ({
    query: jest.fn((_key: unknown, fn: () => Promise<unknown>) => {
      void fn();
      return { data: null, isFetched: false, refetch: jest.fn() };
    }),
  })),
}));

import useFlowStore from "@/stores/flowStore";
import { useMessagesStore } from "@/stores/messagesStore";
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import { useGetMessagesQuery } from "../use-get-messages";

const mockFlowStore = useFlowStore as unknown as { getState: jest.Mock };
const mockIsAuth = isAuthenticatedPlayground as jest.MockedFunction<
  typeof isAuthenticatedPlayground
>;

describe("useGetMessagesQuery - Routing Logic", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockApiGet.mockResolvedValue({ data: MOCK_MESSAGES });
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);
    window.sessionStorage.clear();
  });

  it("should_call_standard_api_when_not_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);

    useGetMessagesQuery({ id: FLOW_ID, mode: "union" }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockApiGet).toHaveBeenCalledWith(
      "api/v1/messages",
      expect.objectContaining({
        params: expect.objectContaining({ flow_id: FLOW_ID }),
      }),
    );
  });

  it("should_call_shared_api_when_authenticated_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(true);

    useGetMessagesQuery({ id: FLOW_ID, mode: "union" }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockApiGet).toHaveBeenCalledWith(
      "api/v1/messages/shared",
      expect.objectContaining({ params: { source_flow_id: SOURCE_FLOW_ID } }),
    );
  });

  it("should_use_sessionStorage_when_anonymous_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(false);

    window.sessionStorage.setItem(FLOW_ID, JSON.stringify(MOCK_MESSAGES));

    useGetMessagesQuery({ id: FLOW_ID, mode: "union" }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    // Should NOT call API
    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("should_sync_messages_to_zustand_store_when_authenticated_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(true);

    const mockSetMessages = jest.fn();
    (useMessagesStore.getState as jest.Mock).mockReturnValue({
      messages: [],
      setMessages: mockSetMessages,
    });

    useGetMessagesQuery({ id: FLOW_ID, mode: "union" }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockSetMessages).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ id: "msg-1" }),
        expect.objectContaining({ id: "msg-2" }),
      ]),
    );
  });
});
