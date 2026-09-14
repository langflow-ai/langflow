/**
 * Tests for useOlderMessages (shared playground scroll-up pagination).
 *
 * History reads are bounded, so the view opens on the newest page; these cover
 * paging backwards from there without stalling on the page it already holds.
 */

import { act, renderHook } from "@testing-library/react";

const FLOW_ID = "flow-older-messages";
const PAGE_SIZE = 100;

const mockGetMessages = jest.fn();
jest.mock("@/controllers/API/queries/messages", () => ({
  getMessages: (...args: unknown[]) => mockGetMessages(...args),
  MESSAGE_HISTORY_PAGE_SIZE: 100,
}));

import { useMessagesStore } from "@/stores/messagesStore";
import { useOlderMessages } from "../use-older-messages";

const page = (from: number, count: number) =>
  Array.from({ length: count }, (_, index) => ({
    id: `m${from + index}`,
    flow_id: FLOW_ID,
    session_id: "s1",
    text: `message ${from + index}`,
    sender: "User",
    timestamp: `2026-01-01T00:00:${String(index).padStart(2, "0")}Z`,
  }));

describe("useOlderMessages", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useMessagesStore.getState().setMessages([]);
  });

  it("should_prepend_older_messages_into_the_store", async () => {
    useMessagesStore.getState().setMessages(page(0, PAGE_SIZE) as never);
    mockGetMessages.mockResolvedValueOnce({ data: page(100, PAGE_SIZE) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    let prepended = 0;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(PAGE_SIZE);
    const stored = useMessagesStore.getState().messages;
    expect(stored).toHaveLength(2 * PAGE_SIZE);
    // Older messages land ahead of the page the view already held.
    expect(stored[0].id).toBe("m100");
    expect(stored[PAGE_SIZE].id).toBe("m0");
  });

  it("should_start_past_the_page_the_view_already_holds", async () => {
    // The view opens on the newest page. Asking for offset 0 would re-fetch it,
    // and the API layer aborts a second GET to the same path within 300ms —
    // which used to cancel the follow-up page and stall the scroll trigger.
    useMessagesStore.getState().setMessages(page(0, PAGE_SIZE) as never);
    mockGetMessages.mockResolvedValueOnce({ data: page(100, PAGE_SIZE) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockGetMessages).toHaveBeenCalledTimes(1);
    expect(mockGetMessages).toHaveBeenCalledWith(FLOW_ID, {
      session_id: "s1",
      limit: PAGE_SIZE,
      order: "DESC",
      offset: PAGE_SIZE,
    });
  });

  it("should_only_count_messages_of_the_visible_session_when_seeding_the_offset", async () => {
    const mine = page(0, 3).map((m) => ({ ...m, session_id: "s1" }));
    const other = page(50, 4).map((m) => ({ ...m, session_id: "s2" }));
    useMessagesStore.getState().setMessages([...mine, ...other] as never);
    mockGetMessages.mockResolvedValueOnce({ data: page(100, 2) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(mockGetMessages).toHaveBeenCalledWith(
      FLOW_ID,
      expect.objectContaining({ offset: 3 }),
    );
  });

  it("should_keep_paging_when_a_page_is_entirely_already_in_the_store", async () => {
    const held = page(0, PAGE_SIZE);
    useMessagesStore.getState().setMessages(held as never);
    // A page of rows the store already holds must not end pagination: the
    // trigger only re-fires on prepended content.
    mockGetMessages
      .mockResolvedValueOnce({ data: held })
      .mockResolvedValueOnce({ data: page(200, PAGE_SIZE) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    let prepended = 0;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(PAGE_SIZE);
    expect(mockGetMessages).toHaveBeenCalledTimes(2);
    // The cursor advanced by what the server returned, not by what was new.
    expect(mockGetMessages).toHaveBeenLastCalledWith(
      FLOW_ID,
      expect.objectContaining({ offset: 2 * PAGE_SIZE }),
    );
  });

  it("should_stop_paging_once_a_short_page_arrives", async () => {
    mockGetMessages.mockResolvedValueOnce({ data: page(0, 4) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    await act(async () => {
      await result.current.loadMore();
    });

    expect(result.current.hasMore).toBe(false);

    await act(async () => {
      await result.current.loadMore();
    });
    expect(mockGetMessages).toHaveBeenCalledTimes(1);
  });

  it("should_keep_paging_available_when_a_request_fails", async () => {
    // A cancelled or failed request is transient; clearing hasMore here would
    // disable scroll-up for the rest of the session.
    mockGetMessages.mockRejectedValueOnce(new Error("canceled"));
    const consoleError = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    let prepended = 1;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(0);
    expect(result.current.hasMore).toBe(true);
    consoleError.mockRestore();
  });
});
