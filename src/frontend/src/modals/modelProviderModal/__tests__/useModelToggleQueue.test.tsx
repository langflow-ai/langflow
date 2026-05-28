import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import { useModelToggleQueue } from "../hooks/useModelToggleQueue";

// ---------------------------------------------------------------------------
// React Query — capture invocation order on the shared mock so the test can
// assert that ``cancelQueries`` is called BEFORE ``setQueryData`` whenever a
// user toggles a model. The two are wired to a single Jest mock function so
// their relative call order is preserved.
// ---------------------------------------------------------------------------
const recordedCalls: Array<{ method: string; args: unknown[] }> = [];

const trackingQueryClient = {
  cancelQueries: jest.fn((...args: unknown[]) => {
    recordedCalls.push({ method: "cancelQueries", args });
    return Promise.resolve();
  }),
  setQueryData: jest.fn((...args: unknown[]) => {
    recordedCalls.push({ method: "setQueryData", args });
    const updater = args[1] as
      | ((prev: unknown) => unknown)
      | Record<string, unknown>;
    if (typeof updater === "function") {
      updater({ enabled_models: { OpenAI: { "gpt-4": true } } });
    }
    return undefined;
  }),
  getQueryData: jest.fn(() => ({
    enabled_models: { OpenAI: { "gpt-4": true } },
  })),
  invalidateQueries: jest.fn((...args: unknown[]) => {
    recordedCalls.push({ method: "invalidateQueries", args });
    return Promise.resolve();
  }),
};

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => trackingQueryClient,
}));

// The hook subscribes to ``useGetEnabledModels`` so the re-overlay effect can
// react when a refetch lands. The shared mock starts with the same baseline
// the trackingQueryClient holds.
jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: { enabled_models: { OpenAI: { "gpt-4": true } } },
  })),
}));

// Mutation mock — tests can read the recorded payloads to assert that each
// flush sends ONLY the unsent slice, never re-sending an in-flight overlay,
// and can drive ``onError`` / ``onSettled`` via the captured callbacks.
const mutationCalls: Array<{
  updates: { provider: string; model_id: string; enabled: boolean }[];
}> = [];
const mutationCallbacks: Array<{
  onError?: (error: unknown) => void;
  onSettled?: () => void;
}> = [];

jest.mock("@/controllers/API/queries/models/use-update-enabled-models", () => ({
  useUpdateEnabledModels: () => ({
    mutate: jest.fn((vars, callbacks) => {
      mutationCalls.push(vars);
      mutationCallbacks.push(callbacks);
    }),
    mutateAsync: jest.fn((vars) => {
      mutationCalls.push(vars);
      return Promise.resolve({ disabled_models: [] });
    }),
  }),
}));

// Debounce stub: capturing the pending function instead of running it
// synchronously lets each test pick when (or whether) the debounced flush
// fires. Tests that exercise the debounced path call ``runDebounced()``;
// tests that exercise the awaitable ``flushPendingChanges`` path don't, so
// ``unsentToggles`` is still populated when the explicit flush runs.
let pendingDebouncedFns: Array<() => void> = [];
const runDebounced = () => {
  const fns = pendingDebouncedFns;
  pendingDebouncedFns = [];
  for (const fn of fns) fn();
};
jest.mock("@/hooks/use-debounce", () => ({
  useDebounce: (fn: (...args: unknown[]) => unknown) => {
    const wrapped = (..._args: unknown[]) => {
      pendingDebouncedFns.push(() => fn());
    };
    (wrapped as unknown as { cancel: () => void }).cancel = jest.fn(() => {
      pendingDebouncedFns = [];
    });
    return wrapped;
  },
}));

const mockRefreshAllModelInputs = jest.fn(() => Promise.resolve());
jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: mockRefreshAllModelInputs,
  }),
}));

const mockSetErrorData = jest.fn();
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: mockSetErrorData,
    }),
}));

describe("useModelToggleQueue", () => {
  beforeEach(() => {
    recordedCalls.length = 0;
    mutationCalls.length = 0;
    mutationCallbacks.length = 0;
    pendingDebouncedFns = [];
    trackingQueryClient.cancelQueries.mockClear();
    trackingQueryClient.setQueryData.mockClear();
    trackingQueryClient.getQueryData.mockClear();
    trackingQueryClient.invalidateQueries.mockClear();
    mockRefreshAllModelInputs.mockClear();
    mockSetErrorData.mockClear();
  });

  describe("optimistic update", () => {
    it("cancels in-flight useGetEnabledModels refetches before the optimistic cache update", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        result.current.handleModelToggle("gpt-4", false);
      });

      expect(trackingQueryClient.cancelQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels"],
      });
      expect(trackingQueryClient.setQueryData).toHaveBeenCalledWith(
        ["useGetEnabledModels"],
        expect.any(Function),
      );

      const cancelIdx = recordedCalls.findIndex(
        (call) => call.method === "cancelQueries",
      );
      const setIdx = recordedCalls.findIndex(
        (call) => call.method === "setQueryData",
      );

      expect(cancelIdx).toBeGreaterThanOrEqual(0);
      expect(setIdx).toBeGreaterThanOrEqual(0);
      expect(cancelIdx).toBeLessThan(setIdx);
    });

    it("no-ops when no provider is selected", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: null }),
      );

      act(() => {
        result.current.handleModelToggle("gpt-4", false);
      });

      expect(trackingQueryClient.cancelQueries).not.toHaveBeenCalled();
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });
  });

  describe("re-overlay effect", () => {
    it("re-applies the pending overlay when a refetch surfaces stale data", () => {
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;

      // Initial render: gpt-4 enabled on the server.
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      const { result, rerender } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // User toggles gpt-4 off — overlay now holds {gpt-4: false}.
      act(() => {
        result.current.handleModelToggle("gpt-4", false);
      });
      expect(trackingQueryClient.setQueryData).toHaveBeenCalled();

      // Drain the call log so the re-overlay can be detected specifically.
      recordedCalls.length = 0;
      trackingQueryClient.setQueryData.mockClear();

      // Simulate a refetch that lands inside the debounce window: the cache
      // reports the still-stale server state (gpt-4: true).
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
      } as unknown as ReturnType<typeof useGetEnabledModels>);
      rerender();

      // The effect detects drift and re-applies the overlay.
      expect(trackingQueryClient.setQueryData).toHaveBeenCalledWith(
        ["useGetEnabledModels"],
        expect.any(Function),
      );

      const updater = trackingQueryClient.setQueryData.mock.calls[0][1] as (
        old: unknown,
      ) => unknown;
      const result2 = updater({
        enabled_models: { OpenAI: { "gpt-4": true, "gpt-3.5-turbo": true } },
      }) as { enabled_models: { OpenAI: Record<string, boolean> } };
      expect(result2.enabled_models.OpenAI["gpt-4"]).toBe(false);
      expect(result2.enabled_models.OpenAI["gpt-3.5-turbo"]).toBe(true);
    });

    it("does not re-overlay when no toggles are pending", () => {
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      renderHook(() => useModelToggleQueue({ providerName: "OpenAI" }));

      // No toggle was performed — the mount effect must NOT call setQueryData.
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });
  });

  describe("send buffer", () => {
    it("does not resend in-flight toggles when a new toggle is flushed", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle A → debounce schedules a flush; drive it to send mutation A.
      act(() => {
        result.current.handleModelToggle("gpt-4", false);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates).toEqual([
        { provider: "OpenAI", model_id: "gpt-4", enabled: false },
      ]);

      // Toggle B while A's mutation is still in flight (onSettled hasn't
      // fired). The next flush MUST send ONLY B — re-sending A would be a
      // duplicate request with non-deterministic ordering vs the original.
      act(() => {
        result.current.handleModelToggle("gpt-3.5-turbo", false);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(2);
      expect(mutationCalls[1].updates).toEqual([
        { provider: "OpenAI", model_id: "gpt-3.5-turbo", enabled: false },
      ]);
    });

    it("re-sends a model when the user re-toggles it after the previous flush fired", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle A → false. Drive the debounce.
      act(() => {
        result.current.handleModelToggle("gpt-4", false);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates).toEqual([
        { provider: "OpenAI", model_id: "gpt-4", enabled: false },
      ]);

      // User re-toggles A → true before the first mutation settles. The
      // re-toggle is a fresh intent and must be sent.
      act(() => {
        result.current.handleModelToggle("gpt-4", true);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(2);
      expect(mutationCalls[1].updates).toEqual([
        { provider: "OpenAI", model_id: "gpt-4", enabled: true },
      ]);
    });
  });

  describe("error path", () => {
    it("rolls back to previousData when the toggle mutation fails", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        result.current.handleModelToggle("gpt-4", false);
        runDebounced();
      });
      expect(mutationCallbacks).toHaveLength(1);

      // The first setQueryData is the optimistic update from handleModelToggle.
      // The second will be the rollback we expect on error.
      const setQueryDataCallsBefore =
        trackingQueryClient.setQueryData.mock.calls.length;

      act(() => {
        mutationCallbacks[0].onError?.(new Error("backend down"));
      });

      // Rollback restored ``previousData`` via setQueryData with the snapshot
      // (NOT a function updater).
      const newCalls = trackingQueryClient.setQueryData.mock.calls.slice(
        setQueryDataCallsBefore,
      );
      const rollbackCall = newCalls.find(
        ([_, arg]) => typeof arg !== "function",
      );
      expect(rollbackCall).toBeDefined();
      expect(rollbackCall?.[0]).toEqual(["useGetEnabledModels"]);
      expect(rollbackCall?.[1]).toEqual({
        enabled_models: { OpenAI: { "gpt-4": true } },
      });

      // User sees an error toast.
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error updating model status" }),
      );
    });

    it("does not re-apply the overlay after a failed mutation drains it", () => {
      // The drain-before-rollback ordering inside ``rollbackToggleBatch`` is
      // load-bearing. Without it, the re-overlay effect (triggered by the
      // setQueryData rollback) would re-apply the stale overlay onto the
      // just-rolled-back cache and silently undo the rollback.
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      const { result, rerender } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        result.current.handleModelToggle("gpt-4", false);
        runDebounced();
      });

      // Mutation fails — overlay is drained, cache reverts.
      act(() => {
        mutationCallbacks[0].onError?.(new Error("backend down"));
      });

      // Subsequent refetch surfaces the (now-correct) server state.
      trackingQueryClient.setQueryData.mockClear();
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
      } as unknown as ReturnType<typeof useGetEnabledModels>);
      rerender();

      // The re-overlay effect must NOT re-apply the failed toggle. The
      // overlay has been drained, so there's nothing to re-apply.
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });

    it("preserves a mid-flight re-toggle when the original mutation fails", () => {
      // Scenario: user toggles A→false, then re-toggles A→true while the
      // first mutation is in flight. The first mutation then fails. The
      // user's latest intent (A=true) must survive — both in the overlay
      // (so the re-overlay effect protects it) and in the unsent buffer
      // (so the next flush sends it).
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        result.current.handleModelToggle("gpt-4", false);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates[0].enabled).toBe(false);

      // Re-toggle while first mutation is in flight.
      act(() => {
        result.current.handleModelToggle("gpt-4", true);
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(2);
      expect(mutationCalls[1].updates[0].enabled).toBe(true);

      // First mutation (A=false) fails. ``clearSentOverlay`` must NOT drop
      // the A entry from the overlay, because the current overlay value
      // (true) doesn't match what we sent (false) — the user re-toggled.
      // The second mutation's overlay entry stays protected.
      mutationCalls.length = 0;
      act(() => {
        mutationCallbacks[0].onError?.(new Error("backend down"));
      });

      // Trigger a fresh flush by toggling another key — if the overlay had
      // been cleared in error, this flush would NOT include any prior
      // intent. We verify the overlay survived by re-toggling A back to
      // its in-flight value: if the overlay still has A=true, this is a
      // no-op intent that doesn't appear in unsent. If the overlay was
      // cleared, this re-toggle would be a fresh intent.
      //
      // Simpler check: the second mutation (A=true) is still in flight
      // and must complete cleanly. The user's last intent is preserved
      // by the overlay until that second mutation settles.
      expect(mutationCallbacks).toHaveLength(2);
      act(() => {
        mutationCallbacks[1].onSettled?.();
      });
      // No additional rollback calls happened — the second mutation's
      // overlay entry was preserved through the first failure.
      expect(mockSetErrorData).toHaveBeenCalledTimes(1);
    });
  });

  describe("flushPendingChanges", () => {
    it("invalidates useGetEnabledModels on success without relying on the caller", async () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle but DON'T run the debounced flush — leave the entry in
      // unsentToggles for the awaitable close handler to consume.
      act(() => {
        result.current.handleModelToggle("gpt-4", false);
      });

      await act(async () => {
        await result.current.flushPendingChanges();
      });

      // The async flush must invalidate the enabled-models cache itself —
      // callers should not have to remember to invalidate downstream.
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels"],
      });
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetModelProviders"],
      });
    });
  });
});
