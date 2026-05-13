import { renderHook } from "@testing-library/react";
import { act } from "react";
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

jest.mock(
  "@/controllers/API/queries/models/use-get-provider-variables",
  () => ({
    useGetProviderVariables: () => ({ data: {} }),
  }),
);

jest.mock("@/controllers/API/queries/models/use-update-enabled-models", () => ({
  useUpdateEnabledModels: () => ({
    mutate: jest.fn(),
    mutateAsync: jest.fn(() => Promise.resolve({ disabled_models: [] })),
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

describe("useProviderConfiguration.handleModelToggle", () => {
  beforeEach(() => {
    recordedCalls.length = 0;
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
});
