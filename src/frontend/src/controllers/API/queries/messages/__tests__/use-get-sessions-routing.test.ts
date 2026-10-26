/**
 * Tests for useGetSessionsFromFlowQuery: which data source each context reads,
 * that the default session (flow ID) stays first on the playground, and how
 * pages of older sessions are detected, requested and merged.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { createElement, type PropsWithChildren } from "react";
import { useGetSessionsFromFlowQuery } from "../use-get-sessions-from-flow";

const FLOW_ID = "virtual-flow-id-123";
const SOURCE_FLOW_ID = "real-flow-id-456";

let mockPlaygroundPage = false;
let mockAuthenticated = false;

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: { getState: () => ({ playgroundPage: mockPlaygroundPage }) },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: { getState: () => ({ currentFlowId: SOURCE_FLOW_ID }) },
}));

jest.mock("@/modals/IOModal/helpers/playground-auth", () => ({
  isAuthenticatedPlayground: () => mockAuthenticated,
}));

const mockApiGet = jest.fn();
jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => mockApiGet(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `api/v1/${key.toLowerCase()}`,
}));

const sessionIds = (count: number) =>
  Array.from({ length: count }, (_, i) => `session-${i}`);

// Serves `sessions` (newest first) the way the backend pages them.
function serve(sessions: string[]) {
  mockApiGet.mockImplementation(
    async (
      _url: string,
      { params }: { params: { limit: number; offset: number } },
    ) => ({
      data: sessions.slice(params.offset, params.offset + params.limit),
    }),
  );
}

function renderSessions() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: PropsWithChildren) =>
    createElement(QueryClientProvider, { client }, children);
  return renderHook(() => useGetSessionsFromFlowQuery({ id: FLOW_ID }), {
    wrapper,
  });
}

beforeEach(() => {
  mockApiGet.mockReset();
  window.sessionStorage.clear();
  mockPlaygroundPage = false;
  mockAuthenticated = false;
});

describe("useGetSessionsFromFlowQuery - routing", () => {
  it("should_request_the_first_page_with_one_lookahead_row_in_the_editor", async () => {
    serve(["session-a"]);

    const { result } = renderSessions();

    await waitFor(() => expect(result.current.data).toEqual(["session-a"]));
    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages/sessions", {
      params: { limit: 101, offset: 0, flow_id: FLOW_ID },
    });
  });

  it("should_call_shared_sessions_api_when_authenticated_playground", async () => {
    mockPlaygroundPage = true;
    mockAuthenticated = true;
    serve(["session-1", "session-2"]);

    const { result } = renderSessions();

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(mockApiGet).toHaveBeenCalledWith("api/v1/messages/shared/sessions", {
      params: { limit: 101, offset: 0, source_flow_id: SOURCE_FLOW_ID },
    });
  });

  it("should_put_default_session_first_when_it_exists_in_middle", async () => {
    mockPlaygroundPage = true;
    mockAuthenticated = true;
    serve(["other-session", FLOW_ID, "another"]);

    const { result } = renderSessions();

    await waitFor(() =>
      expect(result.current.data).toEqual([
        FLOW_ID,
        "other-session",
        "another",
      ]),
    );
  });

  it("should_prepend_default_session_when_missing_from_list", async () => {
    mockPlaygroundPage = true;
    mockAuthenticated = true;
    serve(["session-a", "session-b"]);

    const { result } = renderSessions();

    await waitFor(() =>
      expect(result.current.data).toEqual([FLOW_ID, "session-a", "session-b"]),
    );
  });

  it("should_use_sessionStorage_as_a_single_page_when_anonymous_playground", async () => {
    mockPlaygroundPage = true;
    window.sessionStorage.setItem(
      FLOW_ID,
      JSON.stringify([
        { session_id: "session-a" },
        { session_id: "session-b" },
        { session_id: "session-a" },
        { session_id: null },
      ]),
    );

    const { result } = renderSessions();

    await waitFor(() =>
      expect(result.current.data).toEqual([FLOW_ID, "session-a", "session-b"]),
    );
    expect(result.current.hasNextPage).toBe(false);
    expect(mockApiGet).not.toHaveBeenCalled();
  });
});

describe("useGetSessionsFromFlowQuery - pagination", () => {
  it("should_report_no_next_page_when_exactly_one_page_exists", async () => {
    serve(sessionIds(100));

    const { result } = renderSessions();

    await waitFor(() => expect(result.current.data).toHaveLength(100));
    expect(result.current.hasNextPage).toBe(false);
  });

  it("should_keep_the_lookahead_row_out_of_the_list_when_another_page_exists", async () => {
    serve(sessionIds(101));

    const { result } = renderSessions();

    await waitFor(() => expect(result.current.hasNextPage).toBe(true));
    expect(result.current.data).toEqual(sessionIds(100));
  });

  it("should_load_older_pages_by_offset_until_the_last_one", async () => {
    serve(sessionIds(250));
    const { result } = renderSessions();
    await waitFor(() => expect(result.current.data).toHaveLength(100));

    await act(() => result.current.fetchNextPage());
    await waitFor(() => expect(result.current.data).toHaveLength(200));
    await act(() => result.current.fetchNextPage());

    await waitFor(() => expect(result.current.data).toEqual(sessionIds(250)));
    expect(result.current.hasNextPage).toBe(false);
    expect(
      mockApiGet.mock.calls.map(([, config]) => config.params.offset),
    ).toEqual([0, 100, 200]);
  });

  it("should_drop_a_repeated_id_when_a_new_session_shifts_the_next_page", async () => {
    const sessions = sessionIds(150);
    serve(sessions);
    const { result } = renderSessions();
    await waitFor(() => expect(result.current.data).toHaveLength(100));

    // A new session becomes the most recent: session-99 moves onto page 2.
    sessions.unshift("brand-new");
    await act(() => result.current.fetchNextPage());

    await waitFor(() => expect(result.current.data).toEqual(sessionIds(150)));
  });
});
