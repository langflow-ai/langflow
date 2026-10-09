import { act, renderHook, waitFor } from "@testing-library/react";
import { useSessionManagerStore } from "@/stores/sessionManagerStore";
import { useSessionManager } from "../use-session-manager";

let mockSessions: string[] | undefined;
const mockFetchNextPage = jest.fn();
jest.mock(
  "@/controllers/API/queries/messages/use-get-sessions-from-flow",
  () => ({
    useGetSessionsFromFlowQuery: () => ({
      data: mockSessions ? { sessions: mockSessions } : undefined,
      hasNextPage: true,
      isFetching: false,
      isFetchingNextPage: false,
      fetchNextPage: mockFetchNextPage,
    }),
  }),
);
jest.mock("@/controllers/API/queries/messages/use-delete-sessions", () => ({
  useDeleteSession: () => ({ mutate: jest.fn() }),
}));
jest.mock(
  "@/controllers/API/queries/messages/use-bulk-delete-sessions",
  () => ({
    useBulkDeleteSessions: () => ({ mutate: jest.fn() }),
  }),
);
jest.mock("@/controllers/API/queries/messages/use-rename-session", () => ({
  useUpdateSessionName: () => ({ mutateAsync: jest.fn() }),
}));
jest.mock("@/stores/messagesStore", () => ({
  useMessagesStore: (
    selector: (state: { deleteSession: jest.Mock }) => unknown,
  ) => selector({ deleteSession: jest.fn() }),
}));
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: { setErrorData: jest.Mock }) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));
jest.mock("../../chat-view/utils/message-utils", () => ({
  clearSessionMessages: jest.fn(),
}));
jest.mock("uuid", () => ({ v4: () => "unique-session-id" }));

beforeEach(() => {
  useSessionManagerStore.getState().reset();
  sessionStorage.clear();
  mockFetchNextPage.mockClear();
  mockSessions = ["flow", "recent"];
});

it("renders appended pages and clears server sessions while a new scope loads", async () => {
  const { result, rerender } = renderHook(() =>
    useSessionManager({ flowId: "flow" }),
  );
  await waitFor(() =>
    expect(result.current.sessions).toEqual(["flow", "recent"]),
  );
  mockSessions = ["flow", "recent", "older"];
  rerender();
  await waitFor(() =>
    expect(result.current.sessions).toEqual(["flow", "recent", "older"]),
  );
  act(() => result.current.loadMoreSessions());
  expect(mockFetchNextPage).toHaveBeenCalledTimes(1);
  mockSessions = undefined;
  rerender();
  await waitFor(() => expect(result.current.sessions).toEqual(["flow"]));
});

it("creates a new session without relying on names in unloaded pages", async () => {
  const { result } = renderHook(() => useSessionManager({ flowId: "flow" }));
  await waitFor(() => expect(result.current.sessions).toContain("recent"));
  act(() => result.current.createSession());
  expect(result.current.activeSessionId).toBe("New Session unique-session-id");
  expect(useSessionManagerStore.getState().sessions).toContainEqual({
    id: "New Session unique-session-id",
    isLocal: true,
  });
});
