import { renderHook } from "@testing-library/react";
import { useProviderActions } from "../use-provider-actions";

// Mock all dependencies
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
  })),
}));

jest.mock("@/controllers/API/queries/models/use-update-enabled-models", () => ({
  useUpdateEnabledModels: jest.fn(() => ({ mutate: jest.fn() })),
}));

jest.mock("@/controllers/API/queries/models/use-set-default-model", () => ({
  useSetDefaultModel: jest.fn(() => ({ mutate: jest.fn() })),
}));

jest.mock("@/controllers/API/queries/models/use-clear-default-model", () => ({
  useClearDefaultModel: jest.fn(() => ({ mutate: jest.fn() })),
}));

jest.mock("@/controllers/API/queries/variables", () => ({
  useDeleteGlobalVariables: jest.fn(() => ({ mutate: jest.fn() })),
  usePostGlobalVariables: jest.fn(() => ({ mutate: jest.fn() })),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn(() => ({
    setErrorData: jest.fn(),
    setSuccessData: jest.fn(),
  })),
}));

jest.mock("@/constants/providerConstants", () => ({
  PROVIDER_VARIABLE_MAPPING: {
    Ollama: "OLLAMA_BASE_URL",
    OpenAI: "OPENAI_API_KEY",
  },
  VARIABLE_CATEGORY: {
    CREDENTIAL: "credential",
    GLOBAL: "global",
  },
}));

describe("useProviderActions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("returns all required handler functions", () => {
    const { result } = renderHook(() => useProviderActions());

    expect(result.current).toHaveProperty("handleToggleModel");
    expect(result.current).toHaveProperty("handleBatchToggleModels");
    expect(result.current).toHaveProperty("handleSetDefaultModel");
    expect(result.current).toHaveProperty("handleClearDefaultModel");
    expect(result.current).toHaveProperty("handleEnableProvider");
    expect(result.current).toHaveProperty("handleDeleteProvider");
  });

  it("handleToggleModel is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleToggleModel).toBe("function");
  });

  it("handleBatchToggleModels is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleBatchToggleModels).toBe("function");
  });

  it("handleSetDefaultModel is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleSetDefaultModel).toBe("function");
  });

  it("handleClearDefaultModel is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleClearDefaultModel).toBe("function");
  });

  it("handleEnableProvider is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleEnableProvider).toBe("function");
  });

  it("handleDeleteProvider is a function", () => {
    const { result } = renderHook(() => useProviderActions());
    expect(typeof result.current.handleDeleteProvider).toBe("function");
  });

  it("hook can be called without errors", () => {
    expect(() => {
      renderHook(() => useProviderActions());
    }).not.toThrow();
  });

  it("all handlers exist after rerender", () => {
    const { result, rerender } = renderHook(() => useProviderActions());

    rerender();

    // All handlers should still exist after rerender
    expect(result.current.handleToggleModel).toBeDefined();
    expect(result.current.handleBatchToggleModels).toBeDefined();
    expect(result.current.handleSetDefaultModel).toBeDefined();
    expect(result.current.handleClearDefaultModel).toBeDefined();
    expect(result.current.handleEnableProvider).toBeDefined();
    expect(result.current.handleDeleteProvider).toBeDefined();
  });
});
