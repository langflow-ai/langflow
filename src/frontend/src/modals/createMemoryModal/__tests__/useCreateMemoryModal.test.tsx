import { act, renderHook } from "@testing-library/react";
import type { ModelOption } from "@/components/core/parameterRenderComponent/components/modelInputComponent/types";
import { useCreateMemoryModal } from "../useCreateMemoryModal";

const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockMutate = jest.fn();

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
  useGetModelProviders: () => ({ data: mockProviders }),
}));

jest.mock("@/controllers/API/queries/memories/use-create-memory", () => ({
  useCreateMemory: () => ({ mutate: mockMutate, isPending: false }),
}));

describe("useCreateMemoryModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("builds filtered model options", () => {
    const { result } = renderHook(() =>
      useCreateMemoryModal({ flowId: "flow-1", onClose: jest.fn() }),
    );

    expect(result.current.embeddingModelOptions).toHaveLength(1);
    expect(result.current.llmModelOptions).toHaveLength(1);
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
});
