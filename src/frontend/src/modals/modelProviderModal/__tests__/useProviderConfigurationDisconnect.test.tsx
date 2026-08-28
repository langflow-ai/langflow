import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import type { Provider } from "../components/types";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";

// ---------------------------------------------------------------------------
// Shared mock plumbing
// ---------------------------------------------------------------------------

const mockGlobalVariables: Array<{
  id: string;
  name: string;
  value?: string;
  has_value?: boolean;
}> = [];
const mockProviderVariablesMapping: Record<
  string,
  Array<{
    variable_name: string;
    variable_key: string;
    required: boolean;
    is_secret: boolean;
    is_list: boolean;
    options: string[];
  }>
> = {};
let mockModelProviders: Array<{
  provider: string;
  is_enabled?: boolean;
  is_configured?: boolean;
  models?: unknown[];
}> = [];
let mockModelProvidersIsFetched = false;
let mockModelProvidersIsFetching = false;
let mockModelProvidersIsError = false;
let mockModelProvidersIsSuccess = true;
let mockModelProvidersFetchStatus: "idle" | "fetching" | "paused" = "idle";
let mockInvalidatedQueryKey: readonly unknown[] | null = null;

const deleteCalls: Array<{ id: string | undefined }> = [];
const mockDeleteMutateAsync = jest.fn((params: { id: string | undefined }) => {
  deleteCalls.push(params);
  return Promise.resolve();
});
const mockCreateMutateAsync = jest.fn();
const mockUpdateMutateAsync = jest.fn();
const mockValidateMutateAsync = jest.fn(() => Promise.resolve({ valid: true }));

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockInvalidateQueries = jest.fn();
const mockRefetchQueries = jest.fn();
const mockRefreshAllModelInputs = jest.fn(() => Promise.resolve());
const mockGetQueryState = jest.fn((queryKey: readonly unknown[]) => ({
  status: "success",
  fetchStatus: "idle",
  isInvalidated:
    JSON.stringify(queryKey) === JSON.stringify(mockInvalidatedQueryKey),
}));
const mockUseGetModelProviders = jest.fn(
  (_params?: unknown, _options?: unknown) => ({
    data: mockModelProviders,
    isFetched: mockModelProvidersIsFetched,
    isFetching: mockModelProvidersIsFetching,
    isError: mockModelProvidersIsError,
    isSuccess: mockModelProvidersIsSuccess,
    fetchStatus: mockModelProvidersFetchStatus,
  }),
);

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
    refetchQueries: mockRefetchQueries,
    getQueryState: mockGetQueryState,
  }),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  getGlobalVariablesQueryKey: (scope?: {
    flowId?: string;
    projectId?: string;
  }) => ["useGetGlobalVariables", scope?.flowId, scope?.projectId],
  useDeleteGlobalVariables: () => ({
    mutateAsync: mockDeleteMutateAsync,
    isPending: false,
  }),
  useGetGlobalVariables: () => ({ data: mockGlobalVariables }),
  usePatchGlobalVariables: () => ({
    mutateAsync: mockUpdateMutateAsync,
    isPending: false,
  }),
  usePostGlobalVariables: () => ({
    mutateAsync: mockCreateMutateAsync,
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  getModelProvidersQueryOptions: (params?: Record<string, unknown>) => ({
    queryKey: [
      "useGetModelProviders",
      params?.includeDeprecated,
      params?.includeUnsupported,
      params?.flowId,
      params?.projectId,
      params?.purpose,
    ],
  }),
  useGetModelProviders: (params?: unknown, options?: unknown) =>
    mockUseGetModelProviders(params, options),
}));

jest.mock(
  "@/controllers/API/queries/models/use-get-provider-variables",
  () => ({
    getProviderVariablesQueryKey: (scope?: {
      flowId?: string;
      projectId?: string;
    }) => ["useGetProviderVariables", scope?.flowId, scope?.projectId],
    useGetProviderVariables: () => ({ data: mockProviderVariablesMapping }),
  }),
);

jest.mock("@/controllers/API/queries/models/use-validate-provider", () => ({
  useValidateProvider: () => ({
    mutateAsync: mockValidateMutateAsync,
  }),
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: mockRefreshAllModelInputs,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("../hooks/useModelToggleQueue", () => ({
  useModelToggleQueue: () => ({
    handleModelToggle: jest.fn(),
    flushPendingChanges: jest.fn(() => Promise.resolve()),
  }),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const renderProviderConfiguration = (selectedProvider: Provider) =>
  // ``initialProps`` ensures the prop object reference is stable across
  // re-renders. Without this, every render of the hook would create a new
  // ``selectedProvider`` object and the syncedSelectedProvider useEffect
  // would never stabilise (setState → render → new prop → setState → ...).
  renderHook(
    ({ provider }: { provider: Provider }) =>
      useProviderConfiguration({ selectedProvider: provider }),
    { initialProps: { provider: selectedProvider } },
  );

const openAIProviderVariables = [
  {
    variable_name: "OpenAI API Key",
    variable_key: "OPENAI_API_KEY",
    required: true,
    is_secret: true,
    is_list: false,
    options: [],
  },
  {
    variable_name: "OpenAI Base URL",
    variable_key: "OPENAI_BASE_URL",
    required: false,
    is_secret: false,
    is_list: false,
    options: [],
  },
];

const renderConfiguredOpenAI = ({
  baseUrl = "https://example.com/v1",
  baseUrlHasValue = true,
}: {
  baseUrl?: string;
  baseUrlHasValue?: boolean;
} = {}) => {
  mockProviderVariablesMapping.OpenAI = openAIProviderVariables;
  mockGlobalVariables.push(
    { id: "var-key", name: "OPENAI_API_KEY", has_value: true },
    {
      id: "var-url",
      name: "OPENAI_BASE_URL",
      value: baseUrl,
      has_value: baseUrlHasValue,
    },
  );
  mockModelProviders = [
    {
      provider: "OpenAI",
      is_configured: true,
      is_enabled: true,
      models: [],
    },
  ];
  return renderProviderConfiguration({
    provider: "OpenAI",
    icon: "OpenAI",
    is_enabled: true,
    is_configured: true,
    models: [],
  });
};

const renderScopedProviderConfiguration = (
  selectedProvider: Provider,
  flowId: string,
  projectId: string,
) =>
  renderHook(
    ({ provider, flow, project }) =>
      useProviderConfiguration({
        selectedProvider: provider,
        flowId: flow,
        projectId: project,
      }),
    {
      initialProps: {
        provider: selectedProvider,
        flow: flowId,
        project: projectId,
      },
    },
  );

describe("useProviderConfiguration.handleDisconnect", () => {
  beforeEach(() => {
    mockGlobalVariables.length = 0;
    Object.keys(mockProviderVariablesMapping).forEach(
      (k) => delete mockProviderVariablesMapping[k],
    );
    mockModelProviders = [];
    mockModelProvidersIsFetched = true;
    mockModelProvidersIsFetching = false;
    mockModelProvidersIsError = false;
    mockModelProvidersIsSuccess = true;
    mockModelProvidersFetchStatus = "idle";
    mockInvalidatedQueryKey = null;
    mockValidateMutateAsync.mockReset();
    mockValidateMutateAsync.mockResolvedValue({ valid: true });
    deleteCalls.length = 0;
    mockDeleteMutateAsync.mockClear();
    mockDeleteMutateAsync.mockImplementation((params) => {
      deleteCalls.push(params);
      return Promise.resolve(undefined);
    });
    mockSetSuccessData.mockClear();
    mockSetErrorData.mockClear();
    mockInvalidateQueries.mockReset();
    mockInvalidateQueries.mockResolvedValue(undefined);
    mockRefetchQueries.mockReset();
    mockRefetchQueries.mockResolvedValue(undefined);
    mockRefreshAllModelInputs.mockClear();
    mockUseGetModelProviders.mockClear();
  });

  it("loads the configuration catalog with configure authorization", () => {
    renderHook(() =>
      useProviderConfiguration({
        selectedProvider: null,
        flowId: "flow-one",
        projectId: "project-one",
      }),
    );

    expect(mockUseGetModelProviders).toHaveBeenCalledWith(
      {
        includeDeprecated: true,
        flowId: "flow-one",
        projectId: "project-one",
        purpose: "configure",
      },
      expect.objectContaining({
        refetchInterval: false,
      }),
    );
  });

  it("deletes every variable for a multi-variable provider (OpenRouter)", async () => {
    // OpenRouter is the canonical multi-variable provider: API key + two
    // attribution headers. The pre-fix implementation looked up the variable
    // name via a static frontend constant that didn't include "OpenRouter",
    // so disconnect silently no-op'd. This regression test pins the new
    // behavior: every configured OpenRouter variable is deleted.
    mockProviderVariablesMapping["OpenRouter"] = [
      {
        variable_name: "OpenRouter API Key",
        variable_key: "OPENROUTER_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
      {
        variable_name: "Site URL",
        variable_key: "OPENROUTER_SITE_URL",
        required: false,
        is_secret: false,
        is_list: false,
        options: [],
      },
      {
        variable_name: "App Name",
        variable_key: "OPENROUTER_APP_NAME",
        required: false,
        is_secret: false,
        is_list: false,
        options: [],
      },
    ];
    mockGlobalVariables.push(
      { id: "var-key", name: "OPENROUTER_API_KEY" },
      { id: "var-url", name: "OPENROUTER_SITE_URL", value: "https://x.io" },
      { id: "var-name", name: "OPENROUTER_APP_NAME", value: "MyApp" },
      { id: "var-unrelated", name: "OPENAI_API_KEY" },
    );
    mockModelProviders = [
      {
        provider: "OpenRouter",
        is_configured: true,
        is_enabled: true,
        models: [],
      },
    ];

    const { result } = renderProviderConfiguration({
      provider: "OpenRouter",
      icon: "OpenRouter",
      is_enabled: true,
      is_configured: true,
      models: [],
    });

    await act(async () => {
      await result.current.handleDisconnect();
    });

    const deletedIds = deleteCalls.map((c) => c.id).sort();
    expect(deletedIds).toEqual(["var-key", "var-name", "var-url"]);
    // The unrelated OpenAI key must not be touched.
    expect(deleteCalls.map((c) => c.id)).not.toContain("var-unrelated");
    expect(mockSetSuccessData).toHaveBeenCalled();
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("falls back to the static mapping when the provider-variable API has not resolved", async () => {
    // If the API mapping is empty, disconnect for a known single-variable
    // provider (Anthropic) still works via the legacy static mapping. This
    // preserves the pre-fix behavior for providers like Anthropic that are
    // in the static map and have a single primary credential.
    mockGlobalVariables.push({ id: "var-1", name: "ANTHROPIC_API_KEY" });
    mockModelProviders = [
      {
        provider: "Anthropic",
        is_configured: true,
        is_enabled: true,
        models: [],
      },
    ];

    const { result } = renderProviderConfiguration({
      provider: "Anthropic",
      icon: "Anthropic",
      is_enabled: true,
      is_configured: true,
      models: [],
    });

    await act(async () => {
      await result.current.handleDisconnect();
    });

    expect(deleteCalls).toEqual([{ id: "var-1" }]);
    expect(mockSetSuccessData).toHaveBeenCalled();
  });

  it.each([
    { outcome: "resolves", rejects: false },
    { outcome: "rejects", rejects: true },
  ])(
    "ignores a disconnect that $outcome after the authorization scope changes",
    async ({ rejects }) => {
      const selectedProvider: Provider = {
        provider: "Anthropic",
        icon: "Anthropic",
        is_enabled: true,
        is_configured: true,
        models: [],
      };
      mockProviderVariablesMapping.Anthropic = [
        {
          variable_name: "API Key",
          variable_key: "ANTHROPIC_API_KEY",
          required: true,
          is_secret: true,
          is_list: false,
          options: [],
        },
      ];
      mockGlobalVariables.push({ id: "var-1", name: "ANTHROPIC_API_KEY" });
      mockModelProviders = [selectedProvider];

      let settleDeletion!: () => void;
      mockDeleteMutateAsync.mockImplementationOnce(
        () =>
          new Promise<void>((resolve, reject) => {
            settleDeletion = () => {
              if (rejects) {
                reject(new Error("late disconnect failure"));
              } else {
                resolve();
              }
            };
          }),
      );

      const { result, rerender } = renderScopedProviderConfiguration(
        selectedProvider,
        "flow-a",
        "project-a",
      );
      await waitFor(() =>
        expect(result.current.syncedSelectedProvider?.provider).toBe(
          "Anthropic",
        ),
      );

      let disconnectPromise!: Promise<void>;
      act(() => {
        disconnectPromise = result.current.handleDisconnect();
      });
      await waitFor(() => expect(mockDeleteMutateAsync).toHaveBeenCalled());

      rerender({
        provider: selectedProvider,
        flow: "flow-b",
        project: "project-b",
      });
      const modelProviderInvalidationsAfterScopeChange =
        mockInvalidateQueries.mock.calls.filter(
          ([{ queryKey }]) => queryKey[0] === "useGetModelProviders",
        ).length;

      await act(async () => {
        settleDeletion();
        await disconnectPromise;
      });

      expect(result.current.isFetchingAfterDisconnect).toBe(false);
      expect(result.current.hasUserMadeChanges()).toBe(false);
      expect(mockSetSuccessData).not.toHaveBeenCalled();
      expect(mockSetErrorData).not.toHaveBeenCalled();
      expect(mockRefreshAllModelInputs).not.toHaveBeenCalled();
      expect(
        mockInvalidateQueries.mock.calls.filter(
          ([{ queryKey }]) => queryKey[0] === "useGetModelProviders",
        ),
      ).toHaveLength(
        modelProviderInvalidationsAfterScopeChange + (rejects ? 0 : 1),
      );
    },
  );

  it("invalidates provider caches when disconnect finishes after unmount", async () => {
    const selectedProvider: Provider = {
      provider: "Anthropic",
      icon: "Anthropic",
      is_enabled: true,
      is_configured: true,
      models: [],
    };
    mockProviderVariablesMapping.Anthropic = [
      {
        variable_name: "API Key",
        variable_key: "ANTHROPIC_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockGlobalVariables.push({ id: "var-1", name: "ANTHROPIC_API_KEY" });
    mockModelProviders = [selectedProvider];

    let resolveDeletion!: () => void;
    mockDeleteMutateAsync.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveDeletion = resolve;
        }),
    );

    const { result, unmount } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("Anthropic"),
    );

    let disconnectPromise!: Promise<void>;
    act(() => {
      disconnectPromise = result.current.handleDisconnect();
    });
    await waitFor(() => expect(mockDeleteMutateAsync).toHaveBeenCalled());

    unmount();
    resolveDeletion();
    await disconnectPromise;

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetModelProviders"],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetEnabledModels"],
    });
    expect(mockSetSuccessData).not.toHaveBeenCalled();
    expect(mockSetErrorData).not.toHaveBeenCalled();
    expect(mockRefreshAllModelInputs).not.toHaveBeenCalled();
  });

  it("is a no-op when the provider has no configured variables", async () => {
    mockProviderVariablesMapping["OpenRouter"] = [
      {
        variable_name: "OpenRouter API Key",
        variable_key: "OPENROUTER_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockModelProviders = [
      {
        provider: "OpenRouter",
        is_configured: false,
        is_enabled: false,
        models: [],
      },
    ];

    const { result } = renderProviderConfiguration({
      provider: "OpenRouter",
      icon: "OpenRouter",
      is_enabled: false,
      is_configured: false,
      models: [],
    });

    await act(async () => {
      await result.current.handleDisconnect();
    });

    expect(deleteCalls).toHaveLength(0);
    expect(mockSetSuccessData).not.toHaveBeenCalled();
    expect(mockSetErrorData).not.toHaveBeenCalled();
  });

  it("surfaces an error toast when one of the deletions fails", async () => {
    mockProviderVariablesMapping["OpenRouter"] = [
      {
        variable_name: "OpenRouter API Key",
        variable_key: "OPENROUTER_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockGlobalVariables.push({ id: "var-key", name: "OPENROUTER_API_KEY" });
    mockModelProviders = [
      {
        provider: "OpenRouter",
        is_configured: true,
        is_enabled: true,
        models: [],
      },
    ];
    mockDeleteMutateAsync.mockImplementationOnce(() =>
      Promise.reject(new Error("network down")),
    );

    const { result } = renderProviderConfiguration({
      provider: "OpenRouter",
      icon: "OpenRouter",
      is_enabled: true,
      is_configured: true,
      models: [],
    });

    await act(async () => {
      await result.current.handleDisconnect();
    });

    await waitFor(() => expect(mockSetErrorData).toHaveBeenCalled());
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("invalidates provider caches after a partial multi-variable disconnect", async () => {
    mockProviderVariablesMapping.OpenRouter = [
      {
        variable_name: "OpenRouter API Key",
        variable_key: "OPENROUTER_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
      {
        variable_name: "Site URL",
        variable_key: "OPENROUTER_SITE_URL",
        required: false,
        is_secret: false,
        is_list: false,
        options: [],
      },
    ];
    mockGlobalVariables.push(
      { id: "var-key", name: "OPENROUTER_API_KEY" },
      { id: "var-url", name: "OPENROUTER_SITE_URL" },
    );
    mockModelProviders = [
      {
        provider: "OpenRouter",
        is_configured: true,
        is_enabled: true,
        models: [],
      },
    ];
    mockDeleteMutateAsync.mockImplementation(({ id }) => {
      deleteCalls.push({ id });
      return id === "var-key"
        ? Promise.resolve(undefined)
        : Promise.reject(new Error("site URL deletion failed"));
    });

    const { result } = renderProviderConfiguration({
      provider: "OpenRouter",
      icon: "OpenRouter",
      is_enabled: true,
      is_configured: true,
      models: [],
    });

    await act(async () => {
      await result.current.handleDisconnect();
    });

    expect(deleteCalls.map(({ id }) => id).sort()).toEqual([
      "var-key",
      "var-url",
    ]);
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetModelProviders"],
    });
    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetEnabledModels"],
    });
    expect(result.current.hasUserMadeChanges()).toBe(true);
    expect(result.current.isFetchingAfterDisconnect).toBe(false);
    expect(mockSetErrorData).toHaveBeenCalled();
    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });
});

describe("useProviderConfiguration policy refresh", () => {
  beforeEach(() => {
    mockGlobalVariables.length = 0;
    Object.keys(mockProviderVariablesMapping).forEach(
      (key) => delete mockProviderVariablesMapping[key],
    );
    mockDeleteMutateAsync.mockClear();
    mockModelProviders = [];
    mockModelProvidersIsFetched = false;
    mockModelProvidersIsFetching = false;
    mockModelProvidersIsError = false;
    mockModelProvidersIsSuccess = true;
    mockModelProvidersFetchStatus = "idle";
    mockInvalidatedQueryKey = null;
    mockCreateMutateAsync.mockClear();
    mockValidateMutateAsync.mockReset();
    mockValidateMutateAsync.mockResolvedValue({ valid: true });
    mockInvalidateQueries.mockReset();
    mockInvalidateQueries.mockResolvedValue(undefined);
    mockRefetchQueries.mockReset();
    mockRefetchQueries.mockResolvedValue(undefined);
    mockRefreshAllModelInputs.mockClear();
  });

  it.each([
    {
      state: "has not completed its first request",
      isFetched: false,
      isFetching: false,
      isError: false,
    },
    {
      state: "is refetching retained data",
      isFetched: true,
      isFetching: true,
      isError: false,
    },
    {
      state: "failed with retained data",
      isFetched: true,
      isFetching: false,
      isError: true,
    },
  ])(
    "withholds a stale selected provider while the scoped catalog $state",
    async ({ isFetched, isFetching, isError }) => {
      const selectedProvider: Provider = {
        provider: "OpenAI",
        icon: "OpenAI",
        is_enabled: true,
        is_configured: true,
        models: [],
      };
      mockModelProviders = [selectedProvider];
      mockModelProvidersIsFetched = isFetched;
      mockModelProvidersIsFetching = isFetching;
      mockModelProvidersIsError = isError;

      const { result } = renderProviderConfiguration(selectedProvider);

      await waitFor(() =>
        expect(result.current.syncedSelectedProvider).toBeNull(),
      );
    },
  );

  it("restores the selected provider only after a successful applicable catalog settles", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: true,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;
    mockModelProvidersIsFetching = true;

    const { result, rerender } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider).toBeNull(),
    );

    mockModelProvidersIsFetching = false;
    rerender({ provider: selectedProvider });

    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );
  });

  it("masks the open provider and blocks handlers while a cached catalog refresh is paused", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: true,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;

    const { result, rerender } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );

    mockModelProvidersFetchStatus = "paused";
    rerender({ provider: selectedProvider });

    expect(result.current.syncedSelectedProvider).toBeNull();
    await act(async () => result.current.handleDisconnect());
    expect(mockDeleteMutateAsync).not.toHaveBeenCalled();
  });

  it("blocks a credential handler when the exact policy query is invalidated", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: true,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;
    mockGlobalVariables.push({
      id: "openai-key",
      name: "OPENAI_API_KEY",
    });
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];

    const { result } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );
    mockInvalidatedQueryKey = [
      "useGetModelProviders",
      true,
      undefined,
      undefined,
      undefined,
      "configure",
    ];

    await act(async () => result.current.handleDisconnect());

    expect(mockDeleteMutateAsync).not.toHaveBeenCalled();
  });

  it("does not persist credentials when policy is invalidated during validation", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: false,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    let resolveValidation!: (value: { valid: boolean }) => void;
    mockValidateMutateAsync.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveValidation = resolve;
        }),
    );

    const { result } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );
    act(() => result.current.handleVariableChange("OPENAI_API_KEY", "secret"));

    let savePromise!: Promise<void>;
    act(() => {
      savePromise = result.current.handleSaveAllVariables();
    });
    await waitFor(() => expect(mockValidateMutateAsync).toHaveBeenCalled());
    mockInvalidatedQueryKey = [
      "useGetModelProviders",
      true,
      undefined,
      undefined,
      undefined,
      "configure",
    ];
    resolveValidation({ valid: true });
    await act(async () => savePromise);

    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  it("clears typed credentials when the same provider changes authorization scope", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: false,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];

    const { result, rerender } = renderScopedProviderConfiguration(
      selectedProvider,
      "flow-a",
      "project-a",
    );
    act(() =>
      result.current.handleVariableChange(
        "OPENAI_API_KEY",
        "placeholder-value", // pragma: allowlist secret
      ),
    );
    expect(result.current.variableValues).toEqual({
      OPENAI_API_KEY: "placeholder-value", // pragma: allowlist secret
    });

    rerender({
      provider: selectedProvider,
      flow: "flow-b",
      project: "project-b",
    });

    expect(result.current.variableValues).toEqual({});
    await act(async () => result.current.handleSaveAllVariables());
    expect(mockValidateMutateAsync).not.toHaveBeenCalled();
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
  });

  it("does not persist a captured credential after the scoped hook unmounts", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: false,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    let resolveValidation!: (value: { valid: boolean }) => void;
    mockValidateMutateAsync.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveValidation = resolve;
        }),
    );
    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);
    const { result, unmount } = renderScopedProviderConfiguration(
      selectedProvider,
      "flow-a",
      "project-a",
    );

    try {
      act(() =>
        result.current.handleVariableChange("OPENAI_API_KEY", "secret-a"),
      );
      let savePromise!: Promise<void>;
      act(() => {
        savePromise = result.current.handleSaveAllVariables();
      });
      await waitFor(() => expect(mockValidateMutateAsync).toHaveBeenCalled());

      unmount();
      resolveValidation({ valid: true });
      await savePromise;

      expect(mockCreateMutateAsync).not.toHaveBeenCalled();
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("clears an open provider when a settled refetch omits it", async () => {
    const selectedProvider: Provider = {
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: true,
      models: [],
    };
    mockModelProviders = [selectedProvider];
    mockModelProvidersIsFetched = true;

    const { result, rerender } = renderProviderConfiguration(selectedProvider);
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );

    // Enterprise revoked OpenAI in the same flow. The mounted query settled
    // successfully with no matching provider while the dialog remained open.
    mockModelProviders = [];
    rerender({ provider: selectedProvider });

    await waitFor(() =>
      expect(result.current.syncedSelectedProvider).toBeNull(),
    );

    mockModelProvidersIsFetching = true;
    rerender({ provider: selectedProvider });
    expect(result.current.syncedSelectedProvider).toBeNull();

    mockModelProvidersIsFetching = false;
    mockModelProvidersIsError = true;
    rerender({ provider: selectedProvider });
    expect(result.current.syncedSelectedProvider).toBeNull();

    mockModelProviders = [selectedProvider];
    mockModelProvidersIsError = false;
    rerender({ provider: selectedProvider });
    await waitFor(() =>
      expect(result.current.syncedSelectedProvider?.provider).toBe("OpenAI"),
    );
  });

  it("invalidates provider-variable mappings with the other provider caches", async () => {
    const { result } = renderProviderConfiguration({
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: true,
      is_configured: true,
      models: [],
    });

    await act(async () => result.current.invalidateProviderQueries());

    expect(mockInvalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetProviderVariables"],
    });
  });
});

describe("useProviderConfiguration.handleSaveAllVariables", () => {
  beforeEach(() => {
    mockGlobalVariables.length = 0;
    Object.keys(mockProviderVariablesMapping).forEach(
      (k) => delete mockProviderVariablesMapping[k],
    );
    mockModelProviders = [];
    mockModelProvidersIsFetched = true;
    mockModelProvidersIsFetching = false;
    mockModelProvidersIsError = false;
    mockModelProvidersIsSuccess = true;
    mockModelProvidersFetchStatus = "idle";
    mockInvalidatedQueryKey = null;
    mockCreateMutateAsync.mockReset();
    mockUpdateMutateAsync.mockReset();
    mockUpdateMutateAsync.mockResolvedValue(undefined);
    mockValidateMutateAsync.mockReset();
    mockValidateMutateAsync.mockResolvedValue({ valid: true });
    deleteCalls.length = 0;
    mockDeleteMutateAsync.mockClear();
    mockSetSuccessData.mockClear();
    mockSetErrorData.mockClear();
    mockInvalidateQueries.mockReset();
    mockInvalidateQueries.mockResolvedValue(undefined);
    mockRefetchQueries.mockReset();
    mockRefetchQueries.mockResolvedValue(undefined);
    mockRefreshAllModelInputs.mockClear();
  });

  it("resets a configured optional variable without deleting its identity", async () => {
    const { result } = renderConfiguredOpenAI();

    act(() => {
      result.current.handleVariableChange("OPENAI_BASE_URL", "");
    });

    expect(result.current.canSave).toBe(true);

    await act(async () => {
      await result.current.handleSaveAllVariables();
    });

    expect(mockUpdateMutateAsync).toHaveBeenCalledWith({
      id: "var-url",
      value: "",
    });
    expect(deleteCalls).toHaveLength(0);
    expect(mockCreateMutateAsync).not.toHaveBeenCalled();
    expect(mockValidateMutateAsync).not.toHaveBeenCalled();
  });

  it("does not validate a replacement credential against an explicitly cleared URL", async () => {
    const { result } = renderConfiguredOpenAI();
    const replacementApiKey = "replacement-api-key"; // pragma: allowlist secret

    act(() => {
      result.current.handleVariableChange("OPENAI_BASE_URL", "");
      result.current.handleVariableChange("OPENAI_API_KEY", replacementApiKey);
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);

    try {
      await act(async () => {
        await result.current.handleSaveAllVariables();
      });

      expect(mockValidateMutateAsync).toHaveBeenCalledWith({
        provider: "OpenAI",
        variables: { OPENAI_API_KEY: replacementApiKey },
      });
      expect(mockUpdateMutateAsync).toHaveBeenNthCalledWith(1, {
        id: "var-url",
        value: "",
      });
      expect(mockUpdateMutateAsync).toHaveBeenNthCalledWith(2, {
        id: "var-key",
        value: replacementApiKey,
      });
      expect(mockUpdateMutateAsync).toHaveBeenCalledTimes(2);
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("reuses the preserved variable after a cleared value is reopened", async () => {
    const { result } = renderConfiguredOpenAI({
      baseUrl: "",
      baseUrlHasValue: false,
    });

    expect(result.current.getConfiguredValue("OPENAI_BASE_URL")).toBe("");
    expect(result.current.isVariableConfigured("OPENAI_BASE_URL")).toBe(false);

    act(() => {
      result.current.handleVariableChange(
        "OPENAI_BASE_URL",
        "https://replacement.example/v1",
      );
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);

    try {
      await act(async () => {
        await result.current.handleSaveAllVariables();
      });

      expect(mockUpdateMutateAsync).toHaveBeenCalledWith({
        id: "var-url",
        value: "https://replacement.example/v1",
      });
      expect(mockCreateMutateAsync).not.toHaveBeenCalled();
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("refreshes provider state when a later write fails after a reset", async () => {
    mockUpdateMutateAsync
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("credential write failed"));

    const { result } = renderConfiguredOpenAI();

    act(() => {
      result.current.handleVariableChange("OPENAI_BASE_URL", "");
      result.current.handleVariableChange("OPENAI_API_KEY", "replacement-key");
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);

    try {
      await act(async () => {
        await result.current.handleSaveAllVariables();
      });

      expect(mockUpdateMutateAsync).toHaveBeenNthCalledWith(1, {
        id: "var-url",
        value: "",
      });
      expect(result.current.hasUserMadeChanges()).toBe(true);
      expect(mockInvalidateQueries).toHaveBeenCalled();
      expect(mockSetErrorData).toHaveBeenCalled();
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("waits for the base URL write before creating the API key", async () => {
    mockProviderVariablesMapping["OpenAI Compatible"] = [
      {
        variable_name: "Base URL",
        variable_key: "OPENAI_COMPATIBLE_BASE_URL",
        required: true,
        is_secret: false,
        is_list: false,
        options: [],
      },
      {
        variable_name: "API Key",
        variable_key: "OPENAI_COMPATIBLE_API_KEY",
        required: false,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockModelProviders = [
      {
        provider: "OpenAI Compatible",
        is_enabled: false,
        is_configured: false,
        models: [],
      },
    ];

    let resolveBaseUrl!: () => void;
    mockCreateMutateAsync.mockImplementation(({ name }: { name: string }) => {
      if (name === "OPENAI_COMPATIBLE_BASE_URL") {
        return new Promise<void>((resolve) => {
          resolveBaseUrl = resolve;
        });
      }
      return Promise.resolve();
    });

    const { result } = renderProviderConfiguration({
      provider: "OpenAI Compatible",
      icon: "Plug",
      is_enabled: false,
      is_configured: false,
      models: [],
    });

    act(() => {
      result.current.handleVariableChange(
        "OPENAI_COMPATIBLE_BASE_URL",
        "https://api.openai.com/v1",
      );
      result.current.handleVariableChange(
        "OPENAI_COMPATIBLE_API_KEY",
        "test-api-key",
      );
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);
    let savePromise!: Promise<void>;

    try {
      await act(async () => {
        savePromise = result.current.handleSaveAllVariables();
        await Promise.resolve();
      });

      expect(mockCreateMutateAsync).toHaveBeenCalledTimes(1);
      expect(mockCreateMutateAsync).toHaveBeenNthCalledWith(
        1,
        expect.objectContaining({ name: "OPENAI_COMPATIBLE_BASE_URL" }),
      );

      await act(async () => {
        resolveBaseUrl();
        await savePromise;
      });

      expect(mockCreateMutateAsync).toHaveBeenCalledTimes(2);
      expect(mockCreateMutateAsync).toHaveBeenNthCalledWith(
        2,
        expect.objectContaining({ name: "OPENAI_COMPATIBLE_API_KEY" }),
      );
      expect(mockSetErrorData).not.toHaveBeenCalled();
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("persists the OpenAI base URL before its primary credential", async () => {
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "OpenAI API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
      {
        variable_name: "OpenAI Base URL",
        variable_key: "OPENAI_BASE_URL",
        required: false,
        is_secret: false,
        is_list: false,
        options: [],
      },
    ];
    mockModelProviders = [
      {
        provider: "OpenAI",
        is_enabled: false,
        is_configured: false,
        models: [],
      },
    ];

    let resolveFirstWrite!: () => void;
    mockCreateMutateAsync
      .mockImplementationOnce(
        () =>
          new Promise<void>((resolve) => {
            resolveFirstWrite = resolve;
          }),
      )
      .mockResolvedValue(undefined);

    const { result } = renderProviderConfiguration({
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: false,
      is_configured: false,
      models: [],
    });

    act(() => {
      result.current.handleVariableChange(
        "OPENAI_API_KEY",
        "custom-endpoint-key",
      );
      result.current.handleVariableChange(
        "OPENAI_BASE_URL",
        "https://example.com/v1",
      );
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);
    let savePromise!: Promise<void>;

    try {
      await act(async () => {
        savePromise = result.current.handleSaveAllVariables();
        await Promise.resolve();
      });

      const callsBeforeFirstWriteResolved =
        mockCreateMutateAsync.mock.calls.map(([{ name }]) => name);

      await act(async () => {
        resolveFirstWrite();
        await savePromise;
      });

      expect(callsBeforeFirstWriteResolved).toEqual(["OPENAI_BASE_URL"]);
      expect(
        mockCreateMutateAsync.mock.calls.map(([{ name }]) => name),
      ).toEqual(["OPENAI_BASE_URL", "OPENAI_API_KEY"]);
      expect(mockSetErrorData).not.toHaveBeenCalled();
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("waits for provider cache invalidation before reporting a saved credential", async () => {
    mockProviderVariablesMapping.OpenAI = [
      {
        variable_name: "OpenAI API Key",
        variable_key: "OPENAI_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockModelProviders = [
      {
        provider: "OpenAI",
        is_enabled: false,
        is_configured: false,
        models: [],
      },
    ];
    mockCreateMutateAsync.mockResolvedValue(undefined);

    let resolveProviderInvalidation!: () => void;
    mockInvalidateQueries.mockImplementation(
      ({ queryKey }: { queryKey: readonly unknown[] }) => {
        if (queryKey[0] === "useGetModelProviders") {
          return new Promise<void>((resolve) => {
            resolveProviderInvalidation = resolve;
          });
        }
        return Promise.resolve();
      },
    );

    const { result } = renderProviderConfiguration({
      provider: "OpenAI",
      icon: "OpenAI",
      is_enabled: false,
      is_configured: false,
      models: [],
    });
    act(() => {
      result.current.handleVariableChange("OPENAI_API_KEY", "test-api-key");
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);
    let savePromise!: Promise<void>;

    try {
      await act(async () => {
        savePromise = result.current.handleSaveAllVariables();
        await Promise.resolve();
      });

      await waitFor(() =>
        expect(mockInvalidateQueries).toHaveBeenCalledWith({
          queryKey: ["useGetModelProviders"],
        }),
      );
      expect(result.current.isFetchingAfterSave).toBe(true);
      expect(mockSetSuccessData).not.toHaveBeenCalled();
      expect(mockRefreshAllModelInputs).not.toHaveBeenCalled();

      await act(async () => {
        resolveProviderInvalidation();
        await savePromise;
      });

      expect(result.current.isFetchingAfterSave).toBe(false);
      expect(mockSetSuccessData).toHaveBeenCalled();
      expect(mockRefreshAllModelInputs).toHaveBeenCalledWith({ silent: true });
    } finally {
      dateNowSpy.mockRestore();
    }
  });

  it("completes a multi-variable save after each own variable-cache refresh", async () => {
    mockProviderVariablesMapping.Anthropic = [
      {
        variable_name: "Base URL",
        variable_key: "ANTHROPIC_BASE_URL",
        required: false,
        is_secret: false,
        is_list: false,
        options: [],
      },
      {
        variable_name: "API Key",
        variable_key: "ANTHROPIC_API_KEY",
        required: true,
        is_secret: true,
        is_list: false,
        options: [],
      },
    ];
    mockModelProviders = [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: false,
        models: [],
      },
    ];
    const globalVariablesKey = ["useGetGlobalVariables", undefined, undefined];
    mockCreateMutateAsync.mockImplementation(async () => {
      mockInvalidatedQueryKey = globalVariablesKey;
    });
    mockRefetchQueries.mockImplementation(async ({ queryKey }) => {
      if (JSON.stringify(queryKey) === JSON.stringify(globalVariablesKey)) {
        mockInvalidatedQueryKey = null;
      }
    });
    const provider: Provider = {
      provider: "Anthropic",
      icon: "Anthropic",
      is_enabled: false,
      is_configured: false,
      models: [],
    };

    const { result } = renderProviderConfiguration(provider);

    act(() => {
      result.current.handleVariableChange(
        "ANTHROPIC_BASE_URL",
        "https://api.anthropic.com",
      );
      result.current.handleVariableChange("ANTHROPIC_API_KEY", "test-api-key");
    });

    const dateNowSpy = jest
      .spyOn(Date, "now")
      .mockImplementationOnce(() => 0)
      .mockImplementation(() => 500);

    try {
      await act(async () => result.current.handleSaveAllVariables());

      expect(
        mockCreateMutateAsync.mock.calls.map(([{ name }]) => name),
      ).toEqual(["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"]);
      expect(
        mockRefetchQueries.mock.calls.filter(
          ([{ queryKey }]) =>
            JSON.stringify(queryKey) === JSON.stringify(globalVariablesKey),
        ),
      ).toEqual([
        [
          { queryKey: globalVariablesKey, exact: true },
          { cancelRefetch: false },
        ],
        [
          { queryKey: globalVariablesKey, exact: true },
          { cancelRefetch: false },
        ],
      ]);
      expect(result.current.isFetchingAfterSave).toBe(false);
      expect(mockInvalidateQueries).toHaveBeenCalledWith({
        queryKey: ["useGetModelProviders"],
      });
      expect(mockSetSuccessData).toHaveBeenCalled();
      expect(mockRefreshAllModelInputs).toHaveBeenCalledWith({ silent: true });
    } finally {
      dateNowSpy.mockRestore();
    }
  });
});
