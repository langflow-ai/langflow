import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import type { Provider } from "../components/types";
import { useProviderConfiguration } from "../hooks/useProviderConfiguration";

// ---------------------------------------------------------------------------
// Shared mock plumbing
// ---------------------------------------------------------------------------

const mockGlobalVariables: Array<{ id: string; name: string; value?: string }> =
  [];
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

const deleteCalls: Array<{ id: string | undefined }> = [];
const mockDeleteMutateAsync = jest.fn((params: { id: string | undefined }) => {
  deleteCalls.push(params);
  return Promise.resolve(undefined);
});

const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockInvalidateQueries = jest.fn();
const mockRefetchQueries = jest.fn();

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
    refetchQueries: mockRefetchQueries,
  }),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useDeleteGlobalVariables: () => ({
    mutateAsync: mockDeleteMutateAsync,
    isPending: false,
  }),
  useGetGlobalVariables: () => ({ data: mockGlobalVariables }),
  usePatchGlobalVariables: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
  usePostGlobalVariables: () => ({
    mutateAsync: jest.fn(),
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({
    data: mockModelProviders,
    isFetching: false,
  }),
}));

jest.mock(
  "@/controllers/API/queries/models/use-get-provider-variables",
  () => ({
    useGetProviderVariables: () => ({ data: mockProviderVariablesMapping }),
  }),
);

jest.mock("@/controllers/API/queries/models/use-validate-provider", () => ({
  useValidateProvider: () => ({
    mutateAsync: jest.fn(() => Promise.resolve({ valid: true })),
  }),
}));

jest.mock("@/hooks/use-refresh-model-inputs", () => ({
  useRefreshModelInputs: () => ({
    refreshAllModelInputs: jest.fn(),
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

describe("useProviderConfiguration.handleDisconnect", () => {
  beforeEach(() => {
    mockGlobalVariables.length = 0;
    Object.keys(mockProviderVariablesMapping).forEach(
      (k) => delete mockProviderVariablesMapping[k],
    );
    mockModelProviders = [];
    deleteCalls.length = 0;
    mockDeleteMutateAsync.mockClear();
    mockDeleteMutateAsync.mockImplementation((params) => {
      deleteCalls.push(params);
      return Promise.resolve(undefined);
    });
    mockSetSuccessData.mockClear();
    mockSetErrorData.mockClear();
    mockInvalidateQueries.mockClear();
    mockRefetchQueries.mockClear();
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
});
