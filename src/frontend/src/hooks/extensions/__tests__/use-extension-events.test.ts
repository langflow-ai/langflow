import { act, renderHook } from "@testing-library/react";

const apiGetMock = jest.fn();
const invalidateQueriesMock = jest.fn();
const setErrorDataMock = jest.fn();
const setSuccessDataMock = jest.fn();
const setNoticeDataMock = jest.fn();
const setTypesMock = jest.fn();

jest.mock("@/controllers/API/api", () => ({
  api: { get: (...args: unknown[]) => apiGetMock(...args) },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: (key: string) => `http://localhost/api/v1/${key.toLowerCase()}`,
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({ invalidateQueries: invalidateQueriesMock }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setErrorData: setErrorDataMock,
      setSuccessData: setSuccessDataMock,
      setNoticeData: setNoticeDataMock,
    }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  __esModule: true,
  useTypesStore: {
    getState: () => ({ setTypes: setTypesMock }),
  },
}));

import { _resetOwnReloadDedup, markOwnReload } from "../reload-dedup";
import { useExtensionEvents } from "../use-extension-events";

const EMPTY_RESPONSE = { data: { events: [], settled: true } };

describe("useExtensionEvents", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    apiGetMock.mockResolvedValue(EMPTY_RESPONSE);
    _resetOwnReloadDedup();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  async function mountHook() {
    const hook = renderHook(() => useExtensionEvents());
    await act(async () => {});
    return hook;
  }

  it("should start in settled/idle state", async () => {
    const { result } = await mountHook();

    expect(result.current.isSettled).toBe(true);
    expect(result.current.events).toEqual([]);
  });

  it("should poll immediately on mount", async () => {
    await mountHook();
    expect(apiGetMock).toHaveBeenCalledTimes(1);
  });

  it("should use a lookback cursor on mount (not Date.now)", async () => {
    await mountHook();
    const callArgs = apiGetMock.mock.calls[0];
    const params = callArgs[1]?.params;
    // cursor should be ~30s behind now, not at now
    expect(params.since).toBeLessThan(Date.now() / 1000 - 25);
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

  it("should become active and switch to fast polling when events arrive", async () => {
    const { result } = await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isSettled).toBe(false);
    expect(result.current.events).toHaveLength(1);
  });

  it("should advance cursor to the max timestamp of new events", async () => {
    await mountHook();
    const ts1 = Date.now() / 1000 + 1;
    const ts2 = ts1 + 2;

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          { type: "bundle_reloaded", timestamp: ts1, payload: {} },
          { type: "flow_migrated", timestamp: ts2, payload: {} },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    // Next poll should use ts2 as the cursor
    apiGetMock.mockResolvedValueOnce(EMPTY_RESPONSE);
    await act(async () => {
      jest.advanceTimersByTime(1000);
    });

    const lastCallParams = apiGetMock.mock.calls.at(-1)?.[1]?.params;
    expect(lastCallParams?.since).toBe(ts2);
  });

  it("should call invalidateQueries on bundle_reloaded", async () => {
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["useGetTypes"],
    });
  });

  it("should surface payload.warnings on bundle_reloaded (parity with click path)", async () => {
    // Regression guard: previously the hook ignored payload.warnings, so a
    // tab that picked up a warning-bearing reload via the 30s mount-lookback
    // saw only the green success toast while the clicking tab saw green +
    // blue. The hook must mirror bundleHeaderActions.onSuccess and emit
    // both setSuccessData (with the diagnostics inline) and setNoticeData.
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: {
              bundle: "a",
              components_added: [],
              components_removed: [],
              components_changed: [],
              warnings: [
                {
                  code: "reload-post-swap-hook-failed",
                  message: "Component cache rebuild raised",
                  hint: "Restart the worker if the palette looks stale",
                  location: null,
                  content: null,
                  ref_url: null,
                },
              ],
            },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    const successCall = setSuccessDataMock.mock.calls[0]?.[0];
    expect(successCall.title).toContain("Reloaded a");
    // Diagnostics must be inlined on the success toast so a user who only
    // glances at the green toast still sees the warning.
    expect(successCall.list).toEqual(
      expect.arrayContaining([
        "[reload-post-swap-hook-failed] Component cache rebuild raised",
        "  Restart the worker if the palette looks stale",
      ]),
    );

    // And the separate blue notice must fire so the warning lands in the
    // notification center -- the click path emits both, and the polled
    // path now matches.
    expect(setNoticeDataMock).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Reloaded a with warnings",
        list: expect.arrayContaining([
          "[reload-post-swap-hook-failed] Component cache rebuild raised",
        ]),
      }),
    );
  });

  it("should NOT emit a warnings notice when payload.warnings is empty or missing", async () => {
    // Negative case: a clean reload (no warnings) must not produce a blue
    // notice -- otherwise the user gets a spurious second toast on every
    // successful reload picked up via polling.
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a", warnings: [] },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    const successCall = setSuccessDataMock.mock.calls[0]?.[0];
    expect(successCall.title).toContain("Reloaded a");
    expect(successCall.list).toBeUndefined();
    expect(setNoticeDataMock).not.toHaveBeenCalled();
  });

  it("should tolerate malformed payload.warnings without crashing", async () => {
    // Defensive: an older server (or a payload that drifted from the typed
    // shape) must not be able to break the toast pipeline for every other
    // event in the batch.
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: {
              bundle: "a",
              warnings: ["not-an-object", { code: 42 }, null],
            },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setSuccessDataMock).toHaveBeenCalled();
    // None of the malformed entries pass the {code: string, message: string}
    // gate, so no notice fires.
    expect(setNoticeDataMock).not.toHaveBeenCalled();
  });

  it("should clear typesStore on bundle_reloaded (match UI Reload onSuccess)", async () => {
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setTypesMock).toHaveBeenCalledWith({});
  });

  it("should skip events whose reload_id was marked as self-originated", async () => {
    markOwnReload("rid-self");
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a", reload_id: "rid-self" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setSuccessDataMock).not.toHaveBeenCalled();
    expect(setTypesMock).not.toHaveBeenCalled();
    expect(invalidateQueriesMock).not.toHaveBeenCalled();
  });

  it("should still process events whose reload_id is not marked", async () => {
    markOwnReload("rid-other");
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: { bundle: "a", reload_id: "rid-foreign" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setSuccessDataMock).toHaveBeenCalled();
    expect(setTypesMock).toHaveBeenCalledWith({});
    expect(invalidateQueriesMock).toHaveBeenCalledWith({
      queryKey: ["useGetTypes"],
    });
  });

  it("should call setErrorData on bundle_reload_failed", async () => {
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reload_failed",
            timestamp: Date.now() / 1000,
            payload: { message: "Reload blew up" },
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setErrorDataMock).toHaveBeenCalledWith(
      expect.objectContaining({
        list: expect.arrayContaining(["Reload blew up"]),
      }),
    );
  });

  it("should fall back to event type in error message when payload has no message", async () => {
    await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "extension_error",
            timestamp: Date.now() / 1000,
            payload: {},
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(setErrorDataMock).toHaveBeenCalledWith(
      expect.objectContaining({
        list: expect.arrayContaining([
          "extension_error: check server logs for details",
        ]),
      }),
    );
  });

  it("should settle and return to idle polling after settled=true", async () => {
    const { result } = await mountHook();

    const ts = Date.now() / 1000;
    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [{ type: "bundle_reloaded", timestamp: ts, payload: {} }],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.isSettled).toBe(false);

    apiGetMock.mockResolvedValue({ data: { events: [], settled: true } });

    await act(async () => {
      jest.advanceTimersByTime(MIN_BANNER_DISPLAY_MS + 1000);
    });

    expect(result.current.isSettled).toBe(true);
  });

  it("should stop polling on 401", async () => {
    await mountHook();
    const callsAfterMount = apiGetMock.mock.calls.length;

    apiGetMock.mockRejectedValueOnce({ response: { status: 401 } });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    const callsAfter401 = apiGetMock.mock.calls.length;

    // No more calls after terminal error
    await act(async () => {
      jest.advanceTimersByTime(30000);
    });

    expect(apiGetMock.mock.calls.length).toBe(callsAfter401);
    expect(apiGetMock.mock.calls.length).toBeGreaterThan(callsAfterMount);
  });

  it("should stop polling on 403", async () => {
    await mountHook();

    apiGetMock.mockRejectedValueOnce({ response: { status: 403 } });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    const callsAfter403 = apiGetMock.mock.calls.length;

    await act(async () => {
      jest.advanceTimersByTime(30000);
    });

    expect(apiGetMock.mock.calls.length).toBe(callsAfter403);
  });

  it("clearEvents resets the events list", async () => {
    const { result } = await mountHook();

    apiGetMock.mockResolvedValueOnce({
      data: {
        events: [
          {
            type: "bundle_reloaded",
            timestamp: Date.now() / 1000,
            payload: {},
          },
        ],
        settled: false,
      },
    });

    await act(async () => {
      jest.advanceTimersByTime(5000);
    });

    expect(result.current.events).toHaveLength(1);

    act(() => {
      result.current.clearEvents();
    });

    expect(result.current.events).toHaveLength(0);
  });
});

const MIN_BANNER_DISPLAY_MS = 2000;
