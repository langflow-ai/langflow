import { act, renderHook } from "@testing-library/react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { useCreateMemoryModal } from "../useCreateMemoryModal";

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockMutate = jest.fn();
const mockUseGetModelProviders = jest.fn();
const mockUseGetEnabledModels = jest.fn();
const mockUseGetGlobalVariables = jest.fn();
let mockModelProvidersResult: Record<string, unknown>;
let mockEnabledModelsResult: Record<string, unknown>;
let mockGlobalVariablesResult: Record<string, unknown>;

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (s: {
      setErrorData: jest.Mock;
      setSuccessData: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

const mockProviders = [
  {
    provider: "OpenAI",
    is_enabled: true,
    icon: "Bot",
    models: [
      {
        model_name: "text-embedding-3-small",
        metadata: { model_type: "embeddings" },
      },
      { model_name: "gpt-4o-mini", metadata: { model_type: "llm" } },
    ],
  },
];

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: (...args: unknown[]) => {
    mockUseGetModelProviders(...args);
    return mockModelProvidersResult;
  },
}));

jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: (...args: unknown[]) => {
    mockUseGetEnabledModels(...args);
    return mockEnabledModelsResult;
  },
}));

jest.mock("@/controllers/API/queries/memories/use-create-memory", () => ({
  useCreateMemory: () => ({ mutate: mockMutate, isPending: false }),
}));

// No DB providers configured in the test env → default to local Chroma, which
// `isDBProviderConfigured` always treats as configured.
jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: (...args: unknown[]) => {
    mockUseGetGlobalVariables(...args);
    return mockGlobalVariablesResult;
  },
}));

describe("useCreateMemoryModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockModelProvidersResult = {
      data: mockProviders,
      isFetching: false,
      isError: false,
      isSuccess: true,
      fetchStatus: "idle",
    };
    mockEnabledModelsResult = {
      data: {
        enabled_models: {
          OpenAI: {
            "text-embedding-3-small": true,
            "gpt-4o-mini": true,
          },
        },
      },
      isFetching: false,
      isError: false,
      isSuccess: true,
      fetchStatus: "idle",
    };
    mockGlobalVariablesResult = {
      data: [],
      isFetched: true,
      isFetching: false,
      isError: false,
      isSuccess: true,
      fetchStatus: "idle",
    };
  });

  it("scopes provider and global-variable discovery to the current flow", () => {
    renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(mockUseGetModelProviders).toHaveBeenCalledWith(
      { flowId: "flow-1", purpose: "use" },
      { enabled: true },
    );
    expect(mockUseGetEnabledModels).toHaveBeenCalledWith({
      flowId: "flow-1",
      enabled: true,
      purpose: "use",
    });
    expect(mockUseGetGlobalVariables).toHaveBeenCalledWith({
      flowId: "flow-1",
      enabled: true,
    });
  });

  it("builds filtered model options", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.embeddingModelOptions).toHaveLength(1);
    expect(result.current.llmModelOptions).toHaveLength(1);
  });

  it("keeps same-name LLM and embedding authorization separated by model type", () => {
    mockModelProvidersResult = {
      ...mockModelProvidersResult,
      data: [
        {
          provider: "OpenAI",
          is_enabled: true,
          icon: "Bot",
          models: [
            { model_name: "shared", metadata: { model_type: "llm" } },
            {
              model_name: "shared",
              metadata: { model_type: "embeddings" },
            },
          ],
        },
      ],
    };
    mockEnabledModelsResult = {
      ...mockEnabledModelsResult,
      data: {
        enabled_models: { OpenAI: { shared: true } },
        enabled_models_by_type: {
          OpenAI: {
            llm: { shared: true },
            embeddings: { shared: false },
          },
        },
      },
    };

    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.llmModelOptions).toEqual([
      expect.objectContaining({ name: "shared", provider: "OpenAI" }),
    ]);
    expect(result.current.embeddingModelOptions).toEqual([]);
  });

  it("masks stale model catalogs during refresh and blocks a saved selection", () => {
    mockModelProvidersResult = {
      ...mockModelProvidersResult,
      isFetching: true,
    };
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
    });
    act(() => result.current.handleSubmit());

    expect(result.current.modelCatalogReady).toBe(false);
    expect(result.current.embeddingModelOptions).toEqual([]);
    expect(result.current.embeddingSelectionAuthorized).toBe(false);
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("blocks a model revoked from the latest enabled-model catalog", () => {
    mockEnabledModelsResult = {
      ...mockEnabledModelsResult,
      data: { enabled_models: { OpenAI: { "gpt-4o-mini": true } } },
    };
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
    });
    act(() => result.current.handleSubmit());

    expect(result.current.modelCatalogReady).toBe(true);
    expect(result.current.embeddingSelectionAuthorized).toBe(false);
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("fails closed while scoped DB-provider variables are refreshing", () => {
    mockGlobalVariablesResult = {
      ...mockGlobalVariablesResult,
      isFetching: true,
    };
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.globalVariablesReady).toBe(false);
    expect(result.current.backendConfigured).toBe(false);
  });

  it("fails closed while scoped DB-provider variables are paused", () => {
    mockGlobalVariablesResult = {
      ...mockGlobalVariablesResult,
      fetchStatus: "paused",
    };
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.globalVariablesReady).toBe(false);
    expect(result.current.backendConfigured).toBe(false);
  });

  it("validates name before submit", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.handleSubmit();
    });

    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({ title: "Validation error" }),
    );
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("requires preprocessing instructions when preprocessing is enabled", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
      result.current.setPreprocessingEnabled(true);
      result.current.setSelectedPreprocessingModel([
        {
          id: "gpt-4o-mini",
          name: "gpt-4o-mini",
          provider: "OpenAI",
        } as ModelOption,
      ]);
      // deliberately leave preprocessingPrompt empty
    });

    act(() => {
      result.current.handleSubmit();
    });

    expect(mockSetErrorData).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Validation error",
        list: ["Please provide preprocessing instructions"],
      }),
    );
    expect(mockMutate).not.toHaveBeenCalled();
  });

  it("submits valid payload", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
      result.current.setBatchSizeInput("5");
      result.current.setPreprocessingEnabled(true);
      result.current.setSelectedPreprocessingModel([
        {
          id: "gpt-4o-mini",
          name: "gpt-4o-mini",
          provider: "OpenAI",
        } as ModelOption,
      ]);
      result.current.setPreprocessingPrompt("summarize");
    });

    act(() => {
      result.current.handleSubmit();
    });

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        name: "My Memory",
        flow_id: "flow-1",
        embedding_model: "text-embedding-3-small",
        preproc_model: "gpt-4o-mini",
        preproc_instructions: "summarize",
        preprocessing: true,
        threshold: 5,
      }),
    );
  });

  it("omits the implicit Chroma type so the server can choose its default", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.backendType).toBe("chroma");
    expect(result.current.backendConfigured).toBe(true);

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
    });

    act(() => {
      result.current.handleSubmit();
    });

    expect(mockMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        backend_type: undefined,
        backend_config: {},
      }),
    );
  });

  it("blocks submit when the selected backend is not configured", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    act(() => {
      result.current.setName("My Memory");
      result.current.setSelectedEmbeddingModel([
        {
          id: "text-embedding-3-small",
          name: "text-embedding-3-small",
          provider: "OpenAI",
        } as ModelOption,
      ]);
      // Switch to a remote provider with no global variables set → unconfigured.
      result.current.handleBackendProviderChange("opensearch", {});
    });

    expect(result.current.backendConfigured).toBe(false);

    act(() => {
      result.current.handleSubmit();
    });

    expect(mockMutate).not.toHaveBeenCalled();
    expect(mockSetErrorData).toHaveBeenCalled();
  });
});
