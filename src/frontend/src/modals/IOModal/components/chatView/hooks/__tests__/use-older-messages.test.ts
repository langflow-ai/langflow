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

  it("should_keep_paging_when_a_page_is_entirely_already_in_the_store", async () => {
    // The view opens on the newest page, so offset 0 returns what it already
    // has; returning 0 here would stall the scroll trigger permanently.
    const firstPage = page(0, PAGE_SIZE);
    useMessagesStore.getState().setMessages(firstPage as never);
    mockGetMessages
      .mockResolvedValueOnce({ data: firstPage })
      .mockResolvedValueOnce({ data: page(100, PAGE_SIZE) });

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    let prepended = 0;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(PAGE_SIZE);
    expect(mockGetMessages).toHaveBeenCalledTimes(2);
    expect(mockGetMessages).toHaveBeenNthCalledWith(1, FLOW_ID, {
      session_id: "s1",
      limit: PAGE_SIZE,
      order: "DESC",
      offset: 0,
    });
    // The cursor advanced by what the server returned, not by what was new.
    expect(mockGetMessages).toHaveBeenNthCalledWith(2, FLOW_ID, {
      session_id: "s1",
      limit: PAGE_SIZE,
      order: "DESC",
      offset: PAGE_SIZE,
    });
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

  it("should_stop_paging_when_the_request_fails", async () => {
    mockGetMessages.mockRejectedValueOnce(new Error("network down"));
    const consoleError = jest
      .spyOn(console, "error")
      .mockImplementation(() => {});

    const { result } = renderHook(() => useOlderMessages(FLOW_ID, "s1"));
    let prepended = 1;
    await act(async () => {
      prepended = await result.current.loadMore();
    });

    expect(prepended).toBe(0);
    expect(result.current.hasMore).toBe(false);
    consoleError.mockRestore();
  });
});
