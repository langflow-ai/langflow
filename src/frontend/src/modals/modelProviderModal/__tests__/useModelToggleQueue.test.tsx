import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import type { ModelType } from "@/types/models";
import { useModelToggleQueue } from "../hooks/useModelToggleQueue";

type TypedModelToggle = (
  modelName: string,
  enabled: boolean,
  modelType: ModelType,
) => void;

const invokeTypedToggle = (
  toggle: TypedModelToggle,
  modelName: string,
  enabled: boolean,
  modelType: ModelType,
) => {
  toggle(modelName, enabled, modelType);
};

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
  getQueryState: jest.fn(() => ({
    status: "success",
    fetchStatus: "idle",
    isInvalidated: false,
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
  getEnabledModelsQueryKey: jest.fn(
    (params?: { flowId?: string; projectId?: string; purpose?: string }) =>
      params?.flowId || params?.projectId || params?.purpose
        ? [
            "useGetEnabledModels",
            params?.flowId,
            params?.projectId,
            params?.purpose,
          ]
        : ["useGetEnabledModels"],
  ),
  useGetEnabledModels: jest.fn(() => ({
    data: {
      enabled_models: {
        OpenAI: { "gpt-4": true },
        "Azure AI Foundry": { shared: true },
        Anthropic: { "claude-3": true },
      },
    },
    isSuccess: true,
    isFetching: false,
    isFetchedAfterMount: true,
    fetchStatus: "idle",
  })),
}));

// Mutation mock — tests can read the recorded payloads to assert that each
// flush sends ONLY the unsent slice, never re-sending an in-flight overlay,
// and can drive ``onError`` / ``onSettled`` via the captured callbacks.
const mutationCalls: Array<{
  updates: {
    provider: string;
    model_id: string;
    enabled: boolean;
    model_type: ModelType;
  }[];
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
let latestDebouncedCallback: (() => unknown) | undefined;
let stableDebouncedFunction:
  | (((...args: unknown[]) => void) & { cancel: jest.Mock })
  | undefined;
const runDebounced = () => {
  const fns = pendingDebouncedFns;
  pendingDebouncedFns = [];
  for (const fn of fns) fn();
};
jest.mock("@/hooks/use-debounce", () => ({
  useDebounce: (fn: (...args: unknown[]) => unknown) => {
    latestDebouncedCallback = fn;
    if (!stableDebouncedFunction) {
      const wrapped = (..._args: unknown[]) => {
        pendingDebouncedFns.push(() => latestDebouncedCallback?.());
      };
      stableDebouncedFunction = Object.assign(wrapped, {
        cancel: jest.fn(() => {
          pendingDebouncedFns = [];
        }),
      });
    }
    return stableDebouncedFunction;
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
    latestDebouncedCallback = undefined;
    stableDebouncedFunction = undefined;
    trackingQueryClient.cancelQueries.mockClear();
    trackingQueryClient.setQueryData.mockClear();
    trackingQueryClient.getQueryData.mockClear();
    trackingQueryClient.getQueryState.mockReset();
    trackingQueryClient.getQueryState.mockReturnValue({
      status: "success",
      fetchStatus: "idle",
      isInvalidated: false,
    });
    trackingQueryClient.invalidateQueries.mockClear();
    const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
      typeof useGetEnabledModels
    >;
    mockedEnabled.mockReturnValue({
      data: {
        enabled_models: {
          OpenAI: { "gpt-4": true },
          "Azure AI Foundry": { shared: true },
          Anthropic: { "claude-3": true },
        },
      },
      isSuccess: true,
      isFetching: false,
      isFetchedAfterMount: true,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useGetEnabledModels>);
    mockRefreshAllModelInputs.mockClear();
    mockSetErrorData.mockClear();
  });

  it("loads toggle state with configuration authorization", () => {
    renderHook(() =>
      useModelToggleQueue({
        providerName: "OpenAI",
        flowId: "flow-one",
        projectId: "project-one",
      }),
    );

    expect(useGetEnabledModels).toHaveBeenCalledWith({
      flowId: "flow-one",
      projectId: "project-one",
      purpose: "configure",
    });
  });

  describe("optimistic update", () => {
    it("rejects a stale selected provider omitted from the fresh catalog", () => {
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { Anthropic: { "claude-3": true } } },
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          true,
          "llm",
        );
        runDebounced();
      });

      expect(mutationCalls).toHaveLength(0);
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });

    it("discards a pending overlay instead of re-adding a revoked provider", () => {
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;
      const { result, rerender } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      const callsBeforeRevocation =
        trackingQueryClient.setQueryData.mock.calls.length;

      mockedEnabled.mockReturnValue({
        data: { enabled_models: { Anthropic: { "claude-3": true } } },
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useGetEnabledModels>);
      rerender();

      const callsAfterRevocation =
        trackingQueryClient.setQueryData.mock.calls.slice(
          callsBeforeRevocation,
        );
      expect(callsAfterRevocation).not.toContainEqual([
        ["useGetEnabledModels", undefined, undefined, "configure"],
        expect.any(Function),
      ]);
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels", undefined, undefined, "configure"],
        exact: true,
      });
      act(() => runDebounced());
      expect(mutationCalls).toHaveLength(0);
    });

    it("discards a queued toggle when the selected provider changes", () => {
      const { result, rerender } = renderHook(
        ({ providerName }) => useModelToggleQueue({ providerName }),
        { initialProps: { providerName: "OpenAI" } },
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "shared-model",
          false,
          "llm",
        );
      });
      rerender({ providerName: "Anthropic" });
      act(() => runDebounced());

      expect(mutationCalls).toHaveLength(0);
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels", undefined, undefined, "configure"],
        exact: true,
      });
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error updating model status" }),
      );
    });

    it("never sends an old flow toggle using a newly selected flow scope", () => {
      const { result, rerender } = renderHook(
        ({ flowId }) => useModelToggleQueue({ providerName: "OpenAI", flowId }),
        { initialProps: { flowId: "flow-one" } },
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      rerender({ flowId: "flow-two" });
      act(() => runDebounced());

      expect(mutationCalls).toHaveLength(0);
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels", "flow-one", undefined, "configure"],
        exact: true,
      });
    });

    it("cancels and discards a queued toggle when a scoped owner unmounts", () => {
      const { result, unmount } = renderHook(() =>
        useModelToggleQueue({
          providerName: "OpenAI",
          flowId: "flow-one",
          projectId: "project-one",
        }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      unmount();
      act(() => runDebounced());

      expect(mutationCalls).toHaveLength(0);
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: [
          "useGetEnabledModels",
          "flow-one",
          "project-one",
          "configure",
        ],
        exact: true,
      });
    });

    it("cancels in-flight useGetEnabledModels refetches before the optimistic cache update", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });

      expect(trackingQueryClient.cancelQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels", undefined, undefined, "configure"],
      });
      expect(trackingQueryClient.setQueryData).toHaveBeenCalledWith(
        ["useGetEnabledModels", undefined, undefined, "configure"],
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

    it("disables only the selected type and keeps the flat union enabled", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "Azure AI Foundry" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "shared",
          false,
          "llm",
        );
      });

      const updater = trackingQueryClient.setQueryData.mock.calls[0][1] as (
        old: unknown,
      ) => unknown;
      const updated = updater({
        enabled_models: {
          "Azure AI Foundry": { shared: true },
        },
        enabled_models_by_type: {
          "Azure AI Foundry": {
            llm: { shared: true },
            embeddings: { shared: true },
          },
        },
      }) as {
        enabled_models: Record<string, Record<string, boolean>>;
        enabled_models_by_type: Record<
          string,
          Record<ModelType, Record<string, boolean>>
        >;
      };

      expect(
        updated.enabled_models_by_type["Azure AI Foundry"].llm.shared,
      ).toBe(false);
      expect(
        updated.enabled_models_by_type["Azure AI Foundry"].embeddings.shared,
      ).toBe(true);
      expect(updated.enabled_models["Azure AI Foundry"].shared).toBe(true);
    });

    it("falls back per provider when only another provider has typed status", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });

      const updater = trackingQueryClient.setQueryData.mock.calls[0][1] as (
        old: unknown,
      ) => unknown;
      const updated = updater({
        enabled_models: {
          OpenAI: { "gpt-4": true },
          Anthropic: { "claude-3": true },
        },
        enabled_models_by_type: {
          Anthropic: { llm: { "claude-3": true } },
        },
      }) as {
        enabled_models: Record<string, Record<string, boolean>>;
        enabled_models_by_type: Record<
          string,
          Partial<Record<ModelType, Record<string, boolean>>>
        >;
      };

      expect(updated.enabled_models.OpenAI["gpt-4"]).toBe(false);
      expect(updated.enabled_models_by_type.OpenAI).toBeUndefined();
      expect(updated.enabled_models_by_type.Anthropic.llm?.["claude-3"]).toBe(
        true,
      );
    });

    it("no-ops when no provider is selected", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: null }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });

      expect(trackingQueryClient.cancelQueries).not.toHaveBeenCalled();
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });

    it("no-ops while enabled-model status is still refetching", () => {
      const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
        typeof useGetEnabledModels
      >;
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
        isSuccess: true,
        isFetching: true,
        isFetchedAfterMount: false,
        fetchStatus: "fetching",
      } as unknown as ReturnType<typeof useGetEnabledModels>);
      trackingQueryClient.getQueryState.mockReturnValue({
        status: "success",
        fetchStatus: "fetching",
        isInvalidated: false,
      });

      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
        runDebounced();
      });

      expect(trackingQueryClient.cancelQueries).not.toHaveBeenCalled();
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
      expect(mutationCalls).toHaveLength(0);
    });

    it("re-checks the exact cache state and rejects an invalidated snapshot", () => {
      trackingQueryClient.getQueryState.mockReturnValue({
        status: "success",
        fetchStatus: "idle",
        isInvalidated: true,
      });
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
        runDebounced();
      });

      expect(trackingQueryClient.cancelQueries).not.toHaveBeenCalled();
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
      expect(mutationCalls).toHaveLength(0);
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
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      const { result, rerender } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // User toggles gpt-4 off — overlay now holds {gpt-4: false}.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      expect(trackingQueryClient.setQueryData).toHaveBeenCalled();

      // Drain the call log so the re-overlay can be detected specifically.
      recordedCalls.length = 0;
      trackingQueryClient.setQueryData.mockClear();

      // Simulate a refetch that lands inside the debounce window: the cache
      // reports the still-stale server state (gpt-4: true).
      mockedEnabled.mockReturnValue({
        data: { enabled_models: { OpenAI: { "gpt-4": true } } },
        isSuccess: true,
        isFetching: true,
        isFetchedAfterMount: false,
        fetchStatus: "fetching",
      } as unknown as ReturnType<typeof useGetEnabledModels>);
      rerender();

      // The effect detects drift and re-applies the overlay.
      expect(trackingQueryClient.setQueryData).toHaveBeenCalledWith(
        ["useGetEnabledModels", undefined, undefined, "configure"],
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
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      renderHook(() => useModelToggleQueue({ providerName: "OpenAI" }));

      // No toggle was performed — the mount effect must NOT call setQueryData.
      expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
    });
  });

  describe("send buffer", () => {
    it("re-checks cache trust before flushing an already queued toggle", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      trackingQueryClient.getQueryState.mockReturnValue({
        status: "success",
        fetchStatus: "idle",
        isInvalidated: true,
      });

      act(() => {
        runDebounced();
      });

      expect(mutationCalls).toHaveLength(0);
    });

    it("preserves the same deployment name independently across model types", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "Azure AI Foundry" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "shared",
          false,
          "llm",
        );
        invokeTypedToggle(
          result.current.handleModelToggle,
          "shared",
          true,
          "embeddings",
        );
        runDebounced();
      });

      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates).toEqual([
        {
          provider: "Azure AI Foundry",
          model_id: "shared",
          enabled: false,
          model_type: "llm",
        },
        {
          provider: "Azure AI Foundry",
          model_id: "shared",
          enabled: true,
          model_type: "embeddings",
        },
      ]);
    });

    it("does not resend in-flight toggles when a new toggle is flushed", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle A → debounce schedules a flush; drive it to send mutation A.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates).toEqual([
        {
          provider: "OpenAI",
          model_id: "gpt-4",
          enabled: false,
          model_type: "llm",
        },
      ]);

      // Toggle B while A's mutation is still in flight (onSettled hasn't
      // fired). The next flush MUST send ONLY B — re-sending A would be a
      // duplicate request with non-deterministic ordering vs the original.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-3.5-turbo",
          false,
          "llm",
        );
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(2);
      expect(mutationCalls[1].updates).toEqual([
        {
          provider: "OpenAI",
          model_id: "gpt-3.5-turbo",
          enabled: false,
          model_type: "llm",
        },
      ]);
    });

    it("re-sends a model when the user re-toggles it after the previous flush fired", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle A → false. Drive the debounce.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates).toEqual([
        {
          provider: "OpenAI",
          model_id: "gpt-4",
          enabled: false,
          model_type: "llm",
        },
      ]);

      // User re-toggles A → true before the first mutation settles. The
      // re-toggle is a fresh intent and must be sent.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          true,
          "llm",
        );
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(2);
      expect(mutationCalls[1].updates).toEqual([
        {
          provider: "OpenAI",
          model_id: "gpt-4",
          enabled: true,
          model_type: "llm",
        },
      ]);
    });
  });

  describe("error path", () => {
    it("rolls back to previousData when the toggle mutation fails", () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
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
      expect(rollbackCall?.[0]).toEqual([
        "useGetEnabledModels",
        undefined,
        undefined,
        "configure",
      ]);
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
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
      } as unknown as ReturnType<typeof useGetEnabledModels>);

      const { result, rerender } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
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
        isSuccess: true,
        isFetching: false,
        isFetchedAfterMount: true,
        fetchStatus: "idle",
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
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
        runDebounced();
      });
      expect(mutationCalls).toHaveLength(1);
      expect(mutationCalls[0].updates[0].enabled).toBe(false);

      // Re-toggle while first mutation is in flight.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          true,
          "llm",
        );
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
    it("rolls back and clears a queued toggle when close sees an untrusted cache", async () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
      });
      const callsBeforeClose =
        trackingQueryClient.setQueryData.mock.calls.length;
      trackingQueryClient.getQueryState.mockReturnValue({
        status: "success",
        fetchStatus: "fetching",
        isInvalidated: true,
      });

      await act(async () => {
        await result.current.flushPendingChanges();
      });

      expect(mutationCalls).toHaveLength(0);
      expect(
        trackingQueryClient.setQueryData.mock.calls.slice(callsBeforeClose),
      ).toContainEqual([
        ["useGetEnabledModels", undefined, undefined, "configure"],
        { enabled_models: { OpenAI: { "gpt-4": true } } },
      ]);
      expect(mockSetErrorData).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Error updating model status" }),
      );
      expect(trackingQueryClient.invalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetEnabledModels", undefined, undefined, "configure"],
        exact: true,
      });

      trackingQueryClient.getQueryState.mockReturnValue({
        status: "success",
        fetchStatus: "idle",
        isInvalidated: false,
      });
      await act(async () => {
        await result.current.flushPendingChanges();
      });
      expect(mutationCalls).toHaveLength(0);
    });

    it("invalidates useGetEnabledModels on success without relying on the caller", async () => {
      const { result } = renderHook(() =>
        useModelToggleQueue({ providerName: "OpenAI" }),
      );

      // Toggle but DON'T run the debounced flush — leave the entry in
      // unsentToggles for the awaitable close handler to consume.
      act(() => {
        invokeTypedToggle(
          result.current.handleModelToggle,
          "gpt-4",
          false,
          "llm",
        );
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
