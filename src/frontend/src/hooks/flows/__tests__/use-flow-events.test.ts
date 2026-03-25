import { act, renderHook } from "@testing-library/react";

const apiGetMock = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => apiGetMock(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `http://localhost/api/v1/${key.toLowerCase()}`,
}));

import { useFlowEvents } from "../use-flow-events";

describe("useFlowEvents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    apiGetMock.mockResolvedValue({
      data: { events: [], settled: true },
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("should start in idle state", () => {
    const { result } = renderHook(() => useFlowEvents("flow-1"));

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.events).toEqual([]);
    expect(result.current.lastSettledAt).toBeNull();
  });

  it("should not poll when flowId is undefined", () => {
    renderHook(() => useFlowEvents(undefined));

    act(() => {
      jest.advanceTimersByTime(10000);
    });

    expect(apiGetMock).not.toHaveBeenCalled();
  });

  it("should poll at idle interval (5s)", async () => {
    renderHook(() => useFlowEvents("flow-1"));

    // First poll at 5s
    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(1);

    // Second poll at 10s
    await act(async () => {
      jest.advanceTimersByTime(5000);
    });
    expect(apiGetMock).toHaveBeenCalledTimes(2);
  });

  it("should detect agent working when events arrive", async () => {
    const { result } = renderHook(() => useFlowEvents("flow-1"));

    // First poll returns no events
    apiGetMock.mockResolvedValueOnce({
      data: { events: [], settled: true },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isAgentWorking).toBe(false);

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
    const { result } = renderHook(() => useFlowEvents("flow-1"));

    const ts1 = Date.now() / 1000;

    // First poll with event
    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "component_added", timestamp: ts1, summary: "Added A" },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    // Second poll with another event (now at active interval)
    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "connection_added",
            timestamp: ts1 + 1,
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

  it("should settle when flow_settled event arrives", async () => {
    const { result } = renderHook(() => useFlowEvents("flow-1"));

    const ts = Date.now() / 1000;

    // First poll: agent starts working
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

    // Second poll: settled
    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [{ type: "flow_settled", timestamp: ts + 1, summary: "Done" }],
        settled: true,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.lastSettledAt).not.toBeNull();
  });

  it("should pass since cursor in poll requests", async () => {
    renderHook(() => useFlowEvents("flow-1"));

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(apiGetMock).toHaveBeenCalledWith(
      expect.stringContaining("/flow-1/events"),
      expect.objectContaining({
        params: { since: expect.any(Number) },
      }),
    );
  });

  it("should reset state when flowId changes", async () => {
    const { result, rerender } = renderHook(
      ({ id }: { id: string | undefined }) => useFlowEvents(id),
      { initialProps: { id: "flow-1" as string | undefined } },
    );

    const ts = Date.now() / 1000;

    // Get some events
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

    // Change flowId
    rerender({ id: "flow-2" });

    expect(result.current.events).toEqual([]);
    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.lastSettledAt).toBeNull();
  });

  it("should handle API errors gracefully", async () => {
    const { result } = renderHook(() => useFlowEvents("flow-1"));

    apiGetMock.mockRejectedValueOnce(new Error("Network error"));

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    // Should not crash, stays in idle state
    expect(result.current.isAgentWorking).toBe(false);
    expect(result.current.events).toEqual([]);
  });
});
