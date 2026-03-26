import { act, renderHook } from "@testing-library/react";

const apiGetMock = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => apiGetMock(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `http://localhost/api/v1/${key.toLowerCase()}`,
}));

import { useFlowEvents } from "../use-flow-events";

const EMPTY_RESPONSE = { data: { events: [], settled: true } };

describe("useFlowEvents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    apiGetMock.mockResolvedValue(EMPTY_RESPONSE);
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  async function mountHook(flowId: string | undefined = "flow-1") {
    const hook = renderHook(
      ({ id }: { id: string | undefined }) => useFlowEvents(id),
      { initialProps: { id: flowId } },
    );
    // Flush the immediate initial poll
    await act(async () => {});
    return hook;
  }

  it("should start in idle state", async () => {
    const { result } = await mountHook();

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.events).toEqual([]);
    expect(result.current.lastSettledAt).toBeNull();
  });

  it("should not poll when flowId is undefined", async () => {
    apiGetMock.mockClear();
    renderHook(() => useFlowEvents(undefined));

    await act(async () => {
      jest.advanceTimersByTime(10000);
    });

    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("should poll immediately on mount", async () => {
    await mountHook();

    // Initial poll should have fired already
    expect(apiGetMock).toHaveBeenCalledTimes(1);
  });

  it("should poll at idle interval (5s)", async () => {
    await mountHook();

    const initialCalls = apiGetMock.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(initialCalls + 1);

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(initialCalls + 2);
  });

  it("should detect agent working when events arrive", async () => {
    const { result } = await mountHook();

    // Next poll returns events
    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "component_added",
            timestamp: Date.now() / 1000,
            summary: "Added OpenAI",
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isAgentWorking).toBe(true);
    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0].type).toBe("component_added");
  });

  it("should accumulate events across polls", async () => {
    const { result } = await mountHook();

    const ts = Date.now() / 1000;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts, summary: "Added A" },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "connection_added",
            timestamp: ts + 1,
            summary: "Connected A to B",
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[0].summary).toBe("Added A");
    expect(result.current.events[1].summary).toBe("Connected A to B");
  });

  it("should settle and clear events", async () => {
    const { result } = await mountHook();

    const ts = Date.now() / 1000;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts, summary: "Added A" },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isAgentWorking).toBe(true);

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [{ type: "flow_settled", timestamp: ts + 1, summary: "Done" }],
        settled: true,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    // Advance past MIN_BANNER_DISPLAY_MS for delayed settle
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.lastSettledAt).not.toBeNull();
    // Events are preserved for consumer to read, then cleared via clearEvents
    expect(result.current.events).toHaveLength(2);

    act(() => {
      result.current.clearEvents();
    });
    expect(result.current.events).toEqual([]);
  });

  it("should pass since cursor in poll requests", async () => {
    await mountHook();

    expect(apiGetMock).toHaveBeenCalledWith(
      expect.stringContaining("/flow-1/events"),
      expect.objectContaining({
        params: { since: expect.any(Number) },
      }),
    );
  });

  it("should reset state when flowId changes", async () => {
    const { result, rerender } = await mountHook();

    const ts = Date.now() / 1000;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts, summary: "Added A" },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.events).toHaveLength(1);

    await act(async () => {
      rerender({ id: "flow-2" });
    });

    expect(result.current.events).toEqual([]);
    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.lastSettledAt).toBeNull();
  });

  it("should continue polling at idle interval after settle", async () => {
    const { result } = await mountHook();

    const ts = Date.now() / 1000;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts, summary: "Added A" },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [{ type: "flow_settled", timestamp: ts + 1, summary: "Done" }],
        settled: true,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    // Advance past MIN_BANNER_DISPLAY_MS for delayed settle
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.isAgentWorking).toBe(false);
    const callCountAfterSettle = apiGetMock.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(apiGetMock.mock.calls.length).toBeGreaterThan(callCountAfterSettle);
  });

  it("should handle events and settled arriving in same poll", async () => {
    const { result } = await mountHook();

    const ts = Date.now() / 1000;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts, summary: "Added A" },
          { type: "flow_settled", timestamp: ts + 0.1, summary: "Done" },
        ],
        settled: true,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    // Banner shows briefly (MIN_BANNER_DISPLAY_MS)
    expect(result.current.isAgentWorking).toBe(true);

    // Advance past MIN_BANNER_DISPLAY_MS for delayed settle
    await act(async () => {
      jest.advanceTimersByTime(2000);
    });

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.lastSettledAt).not.toBeNull();
    expect(result.current.events).toHaveLength(2);
  });

  it("should handle API errors gracefully", async () => {
    const { result } = await mountHook();

    apiGetMock.mockRejectedValueOnce(new Error("Network error"));

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.events).toEqual([]);
  });
});
