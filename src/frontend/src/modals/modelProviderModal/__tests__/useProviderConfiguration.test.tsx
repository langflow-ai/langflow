import { renderHook } from "@testing-library/react";
import { act } from "react";
import { useGetEnabledModels } from "@/controllers/API/queries/models/use-get-enabled-models";
import type { Provider } from "../components/types";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";

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
  invalidateQueries: jest.fn(() => Promise.resolve()),
};

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => trackingQueryClient,
}));

// ---------------------------------------------------------------------------
// All other hook dependencies are mocked to no-ops so the test stays scoped
// to ``handleModelToggle``'s cache-cancellation behavior.
// ---------------------------------------------------------------------------
jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({ data: [], isFetching: false }),
}));

// The hook subscribes to ``useGetEnabledModels`` so the re-overlay effect can
// react when a refetch lands. The shared mock starts with the same baseline
// the trackingQueryClient holds. Individual tests can override the return
// value to simulate a refetch.
jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: jest.fn(() => ({
    data: { enabled_models: { OpenAI: { "gpt-4": true } } },
  })),
}));

jest.mock(
  "@/controllers/API/queries/models/use-get-provider-variables",
  () => ({
    useGetProviderVariables: () => ({ data: {} }),
  }),
);

// Mutation mock — tests can read the recorded payloads to assert that each
// flush sends ONLY the unsent slice, never re-sending an in-flight overlay.
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

jest.mock("@/controllers/API/queries/models/use-validate-provider", () => ({
  useValidateProvider: () => ({ mutateAsync: jest.fn() }),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useDeleteGlobalVariables: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
  useGetGlobalVariables: () => ({ data: [] }),
  usePatchGlobalVariables: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
  usePostGlobalVariables: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
}));

jest.mock("@/hooks/use-debounce", () => ({
  // Synchronous pass-through so the test can drive the debounced callback
  // directly. We don't care about timing here — only call ordering.
  useDebounce: (fn: (...args: unknown[]) => unknown) => {
    const wrapped = (...args: unknown[]) => fn(...args);
    (wrapped as unknown as { cancel: () => void }).cancel = jest.fn();
    return wrapped;
  },
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: jest.fn(() => Promise.resolve()),
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
    }),
}));

const provider: Provider = {
  provider: "OpenAI",
  is_enabled: true,
  is_configured: true,
  models: [
    {
      model_name: "gpt-4",
      metadata: { model_type: "llm" },
    },
  ],
} as Provider;

const providerWithBoth: Provider = {
  provider: "OpenAI",
  is_enabled: true,
  is_configured: true,
  models: [
    {
      model_name: "gpt-4",
      metadata: { model_type: "llm" },
    },
    {
      model_name: "gpt-3.5-turbo",
      metadata: { model_type: "llm" },
    },
  ],
} as Provider;

describe("useProviderConfiguration.handleModelToggle", () => {
  beforeEach(() => {
    recordedCalls.length = 0;
    mutationCalls.length = 0;
    mutationCallbacks.length = 0;
    trackingQueryClient.cancelQueries.mockClear();
    trackingQueryClient.setQueryData.mockClear();
    trackingQueryClient.getQueryData.mockClear();
    trackingQueryClient.invalidateQueries.mockClear();
  });

  it("cancels in-flight useGetEnabledModels refetches before the optimistic cache update", () => {
    const { result } = renderHook(() =>
      useProviderConfiguration({ selectedProvider: provider }),
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
      useProviderConfiguration({ selectedProvider: null }),
    );

    act(() => {
      result.current.handleModelToggle("gpt-4", false);
    });

    expect(trackingQueryClient.cancelQueries).not.toHaveBeenCalled();
    expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
  });

  it("re-applies the pending overlay when a refetch surfaces stale data", () => {
    const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
      typeof useGetEnabledModels
    >;

    // Initial render: gpt-4 enabled on the server.
    mockedEnabled.mockReturnValue({
      data: { enabled_models: { OpenAI: { "gpt-4": true } } },
    } as unknown as ReturnType<typeof useGetEnabledModels>);

    const { result, rerender } = renderHook(() =>
      useProviderConfiguration({ selectedProvider: provider }),
    );

    // User toggles gpt-4 off — pending now holds {gpt-4: false}.
    act(() => {
      result.current.handleModelToggle("gpt-4", false);
    });
    expect(trackingQueryClient.setQueryData).toHaveBeenCalled();

    // Drain the call log so we can detect the re-overlay specifically.
    recordedCalls.length = 0;
    trackingQueryClient.setQueryData.mockClear();

    // Simulate a refetch that lands inside the debounce window. The mock
    // now reports the still-stale server state (gpt-4: true) — the same
    // state the optimistic toggle just overwrote.
    mockedEnabled.mockReturnValue({
      data: { enabled_models: { OpenAI: { "gpt-4": true } } },
    } as unknown as ReturnType<typeof useGetEnabledModels>);
    rerender();

    // The re-overlay effect must detect the drift between pending
    // ({gpt-4: false}) and the refetched data ({gpt-4: true}) and re-apply
    // the optimistic overlay.
    expect(trackingQueryClient.setQueryData).toHaveBeenCalledWith(
      ["useGetEnabledModels"],
      expect.any(Function),
    );

    // The overlay updater applied to old data must yield the pending state.
    const updater = trackingQueryClient.setQueryData.mock.calls[0][1] as (
      old: unknown,
    ) => unknown;
    const result2 = updater({
      enabled_models: { OpenAI: { "gpt-4": true, "gpt-3.5-turbo": true } },
    }) as { enabled_models: { OpenAI: Record<string, boolean> } };
    expect(result2.enabled_models.OpenAI["gpt-4"]).toBe(false);
    expect(result2.enabled_models.OpenAI["gpt-3.5-turbo"]).toBe(true);
  });

  it("does not resend in-flight toggles when a new toggle is flushed", () => {
    const { result } = renderHook(() =>
      useProviderConfiguration({ selectedProvider: providerWithBoth }),
    );

    // Toggle A → debounced flush (synchronous via test mock) sends only A.
    act(() => {
      result.current.handleModelToggle("gpt-4", false);
    });
    expect(mutationCalls).toHaveLength(1);
    expect(mutationCalls[0].updates).toEqual([
      { provider: "OpenAI", model_id: "gpt-4", enabled: false },
    ]);

    // Toggle B while A's mutation is still in flight (we haven't fired
    // onSettled yet). The next flush MUST send ONLY B — re-sending A would
    // be a duplicate request with non-deterministic ordering vs the original.
    act(() => {
      result.current.handleModelToggle("gpt-3.5-turbo", false);
    });
    expect(mutationCalls).toHaveLength(2);
    expect(mutationCalls[1].updates).toEqual([
      { provider: "OpenAI", model_id: "gpt-3.5-turbo", enabled: false },
    ]);
  });

  it("re-sends a model when the user re-toggles it after the previous flush fired", () => {
    const { result } = renderHook(() =>
      useProviderConfiguration({ selectedProvider: provider }),
    );

    // Toggle A → false.
    act(() => {
      result.current.handleModelToggle("gpt-4", false);
    });
    expect(mutationCalls).toHaveLength(1);
    expect(mutationCalls[0].updates).toEqual([
      { provider: "OpenAI", model_id: "gpt-4", enabled: false },
    ]);

    // User re-toggles A → true before the first mutation settles. The
    // re-toggle is a fresh intent and must be sent.
    act(() => {
      result.current.handleModelToggle("gpt-4", true);
    });
    expect(mutationCalls).toHaveLength(2);
    expect(mutationCalls[1].updates).toEqual([
      { provider: "OpenAI", model_id: "gpt-4", enabled: true },
    ]);
  });

  it("does not re-overlay when no toggles are pending", () => {
    const mockedEnabled = useGetEnabledModels as jest.MockedFunction<
      typeof useGetEnabledModels
    >;
    mockedEnabled.mockReturnValue({
      data: { enabled_models: { OpenAI: { "gpt-4": true } } },
    } as unknown as ReturnType<typeof useGetEnabledModels>);

    renderHook(() => useProviderConfiguration({ selectedProvider: provider }));

    // No toggle was performed — the mount effect must NOT call setQueryData.
    expect(trackingQueryClient.setQueryData).not.toHaveBeenCalled();
  });
});
