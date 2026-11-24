import { act, renderHook } from "@testing-library/react";
import { useUtilityStore } from "@/stores/utilityStore";
import { useKnowledgeBaseForm } from "../useKnowledgeBaseForm";

const mockCreate = jest.fn().mockResolvedValue({});
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const ready = {
  isSuccess: true,
  isFetching: false,
  isError: false,
  fetchStatus: "idle",
};

jest.mock("@/controllers/API/queries/models/use-get-model-providers", () => ({
  useGetModelProviders: () => ({
    ...ready,
    data: [
      {
        provider: "OpenAI",
        is_enabled: true,
        models: [
          { model_name: "embed", metadata: { model_type: "embeddings" } },
        ],
      },
    ],
  }),
}));
jest.mock("@/controllers/API/queries/models/use-get-enabled-models", () => ({
  useGetEnabledModels: () => ({
    ...ready,
    data: { enabled_models: { OpenAI: { embed: true } } },
  }),
}));
jest.mock("@/controllers/API/queries/variables", () => ({
  useGetGlobalVariables: () => ({ ...ready, data: [] }),
}));
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-create-knowledge-base",
  () => ({ useCreateKnowledgeBase: () => ({ mutateAsync: mockCreate }) }),
);
jest.mock(
  "@/controllers/API/queries/knowledge-bases/use-get-ingestion-job-status",
  () => ({ useGetIngestionJobStatus: () => ({ data: undefined }) }),
);
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector: (state: {
      setErrorData: jest.Mock;
      setSuccessData: jest.Mock;
    }) => unknown,
  ) =>
    selector({
      setErrorData: mockSetErrorData,
      setSuccessData: mockSetSuccessData,
    }),
}));

describe("knowledge-base provider defaults", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useUtilityStore.setState({
      vectorStoreConfigLoaded: false,
      localVectorStoreAvailable: true,
      defaultVectorStoreBackend: undefined,
      configuredVectorStoreBackends: [],
    });
  });

  it("waits for config before initializing and submitting an OpenSearch base", async () => {
    const { result } = renderHook(() =>
      useKnowledgeBaseForm({
        open: true,
        setOpen: jest.fn(),
        hideAdvanced: true,
      }),
    );
    act(() => {
      result.current.setSourceName("Review_KB");
      result.current.setSelectedEmbeddingModel([
        result.current.embeddingModelOptions[0],
      ]);
    });
    await act(async () => {
      await result.current.handleSubmit();
    });
    expect(mockCreate).not.toHaveBeenCalled();

    act(() => {
      useUtilityStore.setState({
        vectorStoreConfigLoaded: true,
        localVectorStoreAvailable: false,
        defaultVectorStoreBackend: "opensearch",
      });
    });
    expect(result.current.backendType).toBe("opensearch");
    await act(async () => {
      await result.current.handleSubmit();
    });
    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ backend_type: "opensearch" }),
    );
  });

  it.each(["postgres", "opensearch"] as const)(
    "submits an environment configured %s base without saved variables",
    async (backendType) => {
      useUtilityStore.setState({
        vectorStoreConfigLoaded: true,
        localVectorStoreAvailable: false,
        defaultVectorStoreBackend: "postgres",
        configuredVectorStoreBackends: ["postgres", "opensearch"],
      });
      const { result } = renderHook(() =>
        useKnowledgeBaseForm({
          open: true,
          setOpen: jest.fn(),
          hideAdvanced: true,
        }),
      );
      act(() => {
        result.current.setSourceName("Environment_KB");
        result.current.setSelectedEmbeddingModel([
          result.current.embeddingModelOptions[0],
        ]);
        result.current.handleBackendProviderChange(backendType, {});
      });
      await act(async () => {
        await result.current.handleSubmit();
      });
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({ backend_type: backendType }),
      );
    },
  );

  it.each([true, false])(
    "submits the pgVector server default without saved variables (local storage: %s)",
    async (localAvailable) => {
      useUtilityStore.setState({
        vectorStoreConfigLoaded: true,
        localVectorStoreAvailable: localAvailable,
        defaultVectorStoreBackend: "postgres",
      });
      const { result } = renderHook(() =>
        useKnowledgeBaseForm({
          open: true,
          setOpen: jest.fn(),
          hideAdvanced: true,
        }),
      );
      act(() => {
        result.current.setSourceName("Environment_KB");
        result.current.setSelectedEmbeddingModel([
          result.current.embeddingModelOptions[0],
        ]);
      });
      await act(async () => {
        await result.current.handleSubmit();
      });
      expect(mockCreate).toHaveBeenCalledWith(
        expect.objectContaining({
          backend_type: "postgres",
          backend_config: {},
        }),
      );
      expect(mockSetErrorData).not.toHaveBeenCalled();
    },
  );

  it("keeps normalization for a new base and returns its stored name", async () => {
    useUtilityStore.setState({ vectorStoreConfigLoaded: true });
    const onSubmit = jest.fn();
    const { result } = renderHook(() =>
      useKnowledgeBaseForm({
        open: true,
        setOpen: jest.fn(),
        hideAdvanced: true,
        onSubmit,
      }),
    );
    act(() => {
      result.current.setSourceName("  New Research  ");
      result.current.setSelectedEmbeddingModel([
        result.current.embeddingModelOptions[0],
      ]);
    });
    await act(async () => {
      await result.current.handleSubmit();
    });

    expect(mockCreate).toHaveBeenCalledWith(
      expect.objectContaining({ name: "New_Research" }),
    );
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        sourceName: "  New Research  ",
        dirName: "New_Research",
      }),
    );
  });
});
