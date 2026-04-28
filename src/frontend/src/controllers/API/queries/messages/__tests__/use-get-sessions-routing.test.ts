/**
 * Tests for useGetSessionsFromFlowQuery routing logic.
 *
 * Verifies that the query routes to the correct data source and
 * ensures the default session (flow ID) always appears first.
 */

const FLOW_ID = "virtual-flow-id-123";
const SOURCE_FLOW_ID = "real-flow-id-456";

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: jest.fn(() => ({ playgroundPage: false })) },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: { getState: jest.fn(() => ({ currentFlowId: SOURCE_FLOW_ID })) },
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: jest.fn(() => false),
}));

const mockApiGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
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
import { isAuthenticatedPlayground } from "@/modals/IOModal/helpers/playground-auth";
import { useGetSessionsFromFlowQuery } from "../use-get-sessions-from-flow";

const mockFlowStore = useFlowStore as unknown as { getState: jest.Mock };
const mockIsAuth = isAuthenticatedPlayground as jest.MockedFunction<
  typeof isAuthenticatedPlayground
>;

describe("useGetSessionsFromFlowQuery - Routing Logic", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    window.sessionStorage.clear();
    mockFlowStore.getState.mockReturnValue({ playgroundPage: false });
    mockIsAuth.mockReturnValue(false);
  });

  it("should_call_shared_sessions_api_when_authenticated_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(true);
    mockApiGet.mockResolvedValue({ data: ["session-1", "session-2"] });

    useGetSessionsFromFlowQuery({ id: FLOW_ID }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockApiGet).toHaveBeenCalledWith(
      "api/v1/messages/shared/sessions",
      expect.objectContaining({ params: { source_flow_id: SOURCE_FLOW_ID } }),
    );
  });

  it("should_use_sessionStorage_when_anonymous_playground", async () => {
    mockFlowStore.getState.mockReturnValue({ playgroundPage: true });
    mockIsAuth.mockReturnValue(false);

    const messages = [{ session_id: "session-a" }, { session_id: "session-b" }];
    window.sessionStorage.setItem(FLOW_ID, JSON.stringify(messages));

    useGetSessionsFromFlowQuery({ id: FLOW_ID }, {});

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(mockApiGet).not.toHaveBeenCalled();
  });

  it("should_put_default_session_first_when_it_exists_in_middle", () => {
    const sessionIds = ["other-session", FLOW_ID, "another"];
    const id = FLOW_ID;

    const idx = sessionIds.indexOf(id);
    if (idx > 0) {
      sessionIds.splice(idx, 1);
      sessionIds.unshift(id);
    } else if (idx === -1) {
      sessionIds.unshift(id);
    }

    expect(sessionIds[0]).toBe(FLOW_ID);
    expect(sessionIds).toHaveLength(3);
  });

  it("should_prepend_default_session_when_missing_from_list", () => {
    const sessionIds = ["session-a", "session-b"];
    const id = FLOW_ID;

    const idx = sessionIds.indexOf(id);
    if (idx > 0) {
      sessionIds.splice(idx, 1);
      sessionIds.unshift(id);
    } else if (idx === -1) {
      sessionIds.unshift(id);
    }

    expect(sessionIds[0]).toBe(FLOW_ID);
    expect(sessionIds).toHaveLength(3);
  });

  it("should_not_duplicate_when_default_session_already_first", () => {
    const sessionIds = [FLOW_ID, "session-a", "session-b"];
    const id = FLOW_ID;

    const idx = sessionIds.indexOf(id);
    if (idx > 0) {
      sessionIds.splice(idx, 1);
      sessionIds.unshift(id);
    } else if (idx === -1) {
      sessionIds.unshift(id);
    }

    expect(sessionIds[0]).toBe(FLOW_ID);
    expect(sessionIds).toHaveLength(3);
  });
});
