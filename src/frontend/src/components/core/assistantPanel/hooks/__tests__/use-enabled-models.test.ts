import { renderHook } from "@testing-library/react";
import type { AssistantModel } from "../../assistant-panel.types";
import { useEnabledModels } from "../use-enabled-models";

const mockUseGetModelProviders = jest.fn();
const mockUseGetEnabledModels = jest.fn();

let mockProvidersResult: Record<string, unknown>;
let mockEnabledModelsResult: Record<string, unknown>;

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: (...args: unknown[]) => {
    mockUseGetModelProviders(...args);
    return mockProvidersResult;
  },
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: (...args: unknown[]) => {
    mockUseGetEnabledModels(...args);
    return mockEnabledModelsResult;
  },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: { currentFlowId: string }) => unknown) =>
    selector({ currentFlowId: "flow-1" }),
}));

const providers = [
  {
    provider: "OpenAI",
    icon: "OpenAI",
    is_enabled: true,
    models: [
      { model_name: "gpt-4o", metadata: { model_type: "llm" } },
      {
        model_name: "text-embedding-3-small",
        metadata: { model_type: "embeddings" },
      },
    ],
  },
];

const selectedModel: AssistantModel = {
  id: "OpenAI-gpt-4o",
  name: "gpt-4o",
  provider: "OpenAI",
  displayName: "gpt-4o",
};

describe("useEnabledModels", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockProvidersResult = {
      data: providers,
      isFetching: false,
      isError: false,
      isSuccess: true,
      fetchStatus: "idle",
    };
    mockEnabledModelsResult = {
      data: { enabled_models: { OpenAI: { "gpt-4o": true } } },
      isFetching: false,
      isError: false,
      isSuccess: true,
      fetchStatus: "idle",
    };
  });

  it("loads both policy catalogs in the active flow scope", () => {
    renderHook(() => useEnabledModels());

    expect(mockUseGetModelProviders).toHaveBeenCalledWith(
      { flowId: "flow-1", purpose: "use" },
      { enabled: true },
    );
    expect(mockUseGetEnabledModels).toHaveBeenCalledWith({
      flowId: "flow-1",
      enabled: true,
      purpose: "use",
    });
  });

  it("offers and authorizes only explicitly enabled LLMs after both queries succeed", () => {
    const { result } = renderHook(() => useEnabledModels());

    expect(result.current.isCatalogReady).toBe(true);
    expect(result.current.filteredProviders).toEqual([
      expect.objectContaining({
        provider: "OpenAI",
        models: [{ model_name: "gpt-4o", metadata: { model_type: "llm" } }],
      }),
    ]);
    expect(result.current.isModelEnabled(selectedModel)).toBe(true);
    expect(
      result.current.isModelEnabled({
        ...selectedModel,
        id: "OpenAI-gpt-4.1",
        name: "gpt-4.1",
      }),
    ).toBe(false);
  });

  it("masks stale provider data while a scoped refresh is pending", () => {
    mockProvidersResult = {
      ...mockProvidersResult,
      isFetching: true,
    };

    const { result } = renderHook(() => useEnabledModels());

    expect(result.current.isCatalogReady).toBe(false);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.filteredProviders).toEqual([]);
    expect(result.current.hasEnabledModels).toBe(false);
    expect(result.current.isModelEnabled(selectedModel)).toBe(false);
  });

  it("masks stale enabled-model data after a scoped refresh error", () => {
    mockEnabledModelsResult = {
      ...mockEnabledModelsResult,
      isError: true,
      isSuccess: false,
    };

    const { result } = renderHook(() => useEnabledModels());

    expect(result.current.isCatalogReady).toBe(false);
    expect(result.current.isError).toBe(true);
    expect(result.current.filteredProviders).toEqual([]);
    expect(result.current.isModelEnabled(selectedModel)).toBe(false);
  });

  it("fails closed while an otherwise successful catalog query is paused", () => {
    mockEnabledModelsResult = {
      ...mockEnabledModelsResult,
      fetchStatus: "paused",
    };

    const { result } = renderHook(() => useEnabledModels());

    expect(result.current.isCatalogReady).toBe(false);
    expect(result.current.filteredProviders).toEqual([]);
    expect(result.current.isModelEnabled(selectedModel)).toBe(false);
  });

  it("uses the typed LLM map for same-name models and only falls back per untyped provider", () => {
    mockProvidersResult = {
      ...mockProvidersResult,
      data: [
        {
          provider: "OpenAI",
          icon: "OpenAI",
          is_enabled: true,
          models: [
            { model_name: "shared", metadata: { model_type: "llm" } },
            {
              model_name: "shared",
              metadata: { model_type: "embeddings" },
            },
          ],
        },
        {
          provider: "Legacy",
          icon: "Bot",
          is_enabled: true,
          models: [
            { model_name: "legacy-chat", metadata: { model_type: "llm" } },
          ],
        },
      ],
    };
    mockEnabledModelsResult = {
      ...mockEnabledModelsResult,
      data: {
        enabled_models: {
          OpenAI: { shared: true },
          Legacy: { "legacy-chat": true },
        },
        enabled_models_by_type: {
          OpenAI: {
            llm: { shared: false },
            embeddings: { shared: true },
          },
        },
      },
    };

    const { result } = renderHook(() => useEnabledModels());

    expect(result.current.filteredProviders).toEqual([
      expect.objectContaining({
        provider: "Legacy",
        models: [
          { model_name: "legacy-chat", metadata: { model_type: "llm" } },
        ],
      }),
    ]);
    expect(
      result.current.isModelEnabled({
        id: "OpenAI-shared",
        name: "shared",
        provider: "OpenAI",
        displayName: "shared",
      }),
    ).toBe(false);
  });
});
