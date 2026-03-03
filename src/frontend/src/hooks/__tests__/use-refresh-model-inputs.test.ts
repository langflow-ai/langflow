import { act, renderHook } from "@testing-library/react";
import type { APITemplateType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";

// Mock values - must be defined before jest.mock calls
const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetNode = jest.fn();
const mockQueryClient = {
  invalidateQueries: jest.fn().mockResolvedValue(undefined),
};
let mockNodes: AllNodeType[] = [];

// Mock dependencies
jest.mock("@tanstack/react-query", () => ({
  useQueryClient: jest.fn(() => mockQueryClient),
  QueryClient: jest.fn(),
}));

jest.mock("@/controllers/API/api", () => ({
  api: {
    post: jest.fn(),
  },
}));

jest.mock("@/controllers/API/helpers/constants", () => ({
  getURL: jest.fn(() => "/api/custom_component/update"),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
    }),
  },
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      nodes: mockNodes,
      setNode: mockSetNode,
    }),
  },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      currentFlowId: "flow-123",
      currentFlow: { folder_id: "folder-456" },
    }),
  },
}));

// Import after mocks are set up
import { api } from "@/controllers/API/api";
import {
  buildRefreshPayload,
  createUpdatedNode,
  findModelFieldKey,
  isModelNode,
  refreshAllModelInputs,
  useRefreshModelInputs,
} from "../use-refresh-model-inputs";

// ============================================================================
// Helper Function Tests
// ============================================================================

describe("isModelNode", () => {
  it("should return true for a genericNode with a model field", () => {
    const node = createMockModelNode("node-1");
    expect(isModelNode(node)).toBe(true);
  });

  it("should return false for a non-genericNode", () => {
    const node = {
      id: "note-1",
      type: "noteNode",
      position: { x: 0, y: 0 },
      data: { node: { template: {} } },
    } as unknown as AllNodeType;
    expect(isModelNode(node)).toBe(false);
  });

  it("should return false for a genericNode without model fields", () => {
    const node = {
      id: "node-1",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        node: {
          template: {
            text_input: { type: "str", value: "hello" },
          },
        },
      },
    } as unknown as AllNodeType;
    expect(isModelNode(node)).toBe(false);
  });

  it("should return false when template is missing", () => {
    const node = {
      id: "node-1",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: { node: {} },
    } as unknown as AllNodeType;
    expect(isModelNode(node)).toBe(false);
  });
});

describe("findModelFieldKey", () => {
  it("should find the model field key in a template", () => {
    const template: APITemplateType = {
      model_name: {
        type: "model",
        value: "gpt-4",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
      temperature: {
        type: "float",
        value: 0.7,
        required: false,
        list: false,
        show: true,
        readonly: false,
      },
    };
    expect(findModelFieldKey(template)).toBe("model_name");
  });

  it("should return undefined when no model field exists", () => {
    const template: APITemplateType = {
      text: {
        type: "str",
        value: "",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };
    expect(findModelFieldKey(template)).toBeUndefined();
  });

  it("should return the first model field if multiple exist", () => {
    const template: APITemplateType = {
      primary_model: {
        type: "model",
        value: "gpt-4",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
      backup_model: {
        type: "model",
        value: "gpt-3.5",
        required: false,
        list: false,
        show: true,
        readonly: false,
      },
    };
    const result = findModelFieldKey(template);
    expect(result).toBeDefined();
    expect(["primary_model", "backup_model"]).toContain(result);
  });
});

describe("buildRefreshPayload", () => {
  const baseTemplate: APITemplateType = {
    model: {
      type: "model",
      value: "gpt-4",
      required: true,
      list: false,
      show: true,
      readonly: false,
    },
  };

  it("should add flow context when flowId is provided", () => {
    const result = buildRefreshPayload(baseTemplate, "flow-123", undefined);
    expect(result._frontend_node_flow_id).toEqual({ value: "flow-123" });
    expect(result._frontend_node_folder_id).toBeUndefined();
    expect(result.is_refresh).toBe(true);
  });

  it("should add folder context when folderId is provided", () => {
    const result = buildRefreshPayload(baseTemplate, undefined, "folder-456");
    expect(result._frontend_node_flow_id).toBeUndefined();
    expect(result._frontend_node_folder_id).toEqual({ value: "folder-456" });
    expect(result.is_refresh).toBe(true);
  });

  it("should add both flow and folder context when both provided", () => {
    const result = buildRefreshPayload(baseTemplate, "flow-123", "folder-456");
    expect(result._frontend_node_flow_id).toEqual({ value: "flow-123" });
    expect(result._frontend_node_folder_id).toEqual({ value: "folder-456" });
    expect(result.is_refresh).toBe(true);
  });

  it("should preserve original template fields", () => {
    const result = buildRefreshPayload(baseTemplate, "flow-123", "folder-456");
    expect(result.model).toEqual(baseTemplate.model);
  });
});

describe("createUpdatedNode", () => {
  it("should update the node template with new data", () => {
    const currentNode = createMockModelNode("node-1");
    const newTemplate: APITemplateType = {
      model: {
        type: "model",
        value: "gpt-4-turbo",
        options: ["gpt-4", "gpt-4-turbo"],
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };

    const result = createUpdatedNode(currentNode, newTemplate);
    expect(result.data.node.template).toBe(newTemplate);
    expect(result.id).toBe(currentNode.id);
  });

  it("should use provided outputs when available", () => {
    const currentNode = createMockModelNode("node-1");
    const newTemplate: APITemplateType = {
      model: {
        type: "model",
        value: "gpt-4",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };
    const newOutputs = [
      { name: "output", types: ["str"], display_name: "Output" },
    ];

    const result = createUpdatedNode(currentNode, newTemplate, newOutputs);
    expect(result.data.node.outputs).toBe(newOutputs);
  });

  it("should preserve existing outputs when new outputs not provided", () => {
    const currentNode = createMockModelNode("node-1");
    const existingOutputs = [
      { name: "existing", types: ["str"], display_name: "Existing" },
    ];
    (currentNode.data.node as any).outputs = existingOutputs;

    const newTemplate: APITemplateType = {
      model: {
        type: "model",
        value: "gpt-4",
        required: true,
        list: false,
        show: true,
        readonly: false,
      },
    };

    const result = createUpdatedNode(currentNode, newTemplate, undefined);
    expect(result.data.node.outputs).toBe(existingOutputs);
  });
});

// ============================================================================
// Core Function Tests
// ============================================================================

describe("refreshAllModelInputs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
  });

  it("should show success message when no model nodes exist", async () => {
    mockNodes = [];

    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "No model components to refresh",
    });
  });

  it("should not show notifications when silent option is true", async () => {
    mockNodes = [];

    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("should invalidate query cache when queryClient is provided", async () => {
    mockNodes = [];

    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetModelProviders"],
    });
    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetEnabledModels"],
    });
  });

  it("should not invalidate cache when queryClient is not provided", async () => {
    mockNodes = [];

    await refreshAllModelInputs(undefined);

    expect(mockQueryClient.invalidateQueries).not.toHaveBeenCalled();
  });

  it("should refresh model nodes and show success message", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: "gpt-4",
            options: ["gpt-4", "gpt-4-turbo"],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).toHaveBeenCalled();
    expect(mockSetNode).toHaveBeenCalled();
    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "Refreshed 1 model component",
    });
  });

  it("should handle plural correctly for multiple nodes", async () => {
    mockNodes = [createMockModelNode("node-1"), createMockModelNode("node-2")];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: "gpt-4",
            options: ["gpt-4"],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "Refreshed 2 model components",
    });
  });

  it("should clear model value when API returns empty options", async () => {
    mockNodes = [createMockModelNode("node-1")];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: "gpt-4",
            options: [], // Empty options
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    await refreshAllModelInputs(mockQueryClient as any);

    // Should still call setNode to clear the invalid value
    expect(mockSetNode).toHaveBeenCalled();
  });

  it("should handle API errors gracefully", async () => {
    mockNodes = [createMockModelNode("node-1")];

    const consoleWarnSpy = jest.spyOn(console, "warn").mockImplementation();
    (api.post as jest.Mock).mockRejectedValue(new Error("API Error"));

    await refreshAllModelInputs(mockQueryClient as any);

    expect(consoleWarnSpy).toHaveBeenCalled();
    expect(mockSetSuccessData).toHaveBeenCalled(); // Still shows success for the batch
    consoleWarnSpy.mockRestore();
  });

  it("should prevent concurrent refresh operations", async () => {
    mockNodes = [createMockModelNode("node-1")];

    let resolveFirst: () => void;
    const firstCallPromise = new Promise<void>((resolve) => {
      resolveFirst = resolve;
    });

    (api.post as jest.Mock).mockImplementation(
      () =>
        new Promise((resolve) => {
          firstCallPromise.then(() =>
            resolve({
              data: {
                template: {
                  model: {
                    type: "model",
                    options: ["gpt-4"],
                    required: true,
                    list: false,
                    show: true,
                    readonly: false,
                  },
                },
              },
            }),
          );
        }),
    );

    // Start first refresh
    const firstRefresh = refreshAllModelInputs(mockQueryClient as any);

    // Try to start second refresh while first is in progress
    const secondRefresh = refreshAllModelInputs(mockQueryClient as any);

    // Complete first refresh
    resolveFirst!();
    await firstRefresh;
    await secondRefresh;

    // API should only have been called once (second call was blocked)
    expect(api.post).toHaveBeenCalledTimes(1);
  });
});

// ============================================================================
// Hook Tests
// ============================================================================

describe("useRefreshModelInputs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
  });

  it("should return refresh function and deprecated alias", () => {
    const { result } = renderHook(() => useRefreshModelInputs());

    expect(typeof result.current.refresh).toBe("function");
    expect(typeof result.current.refreshAllModelInputs).toBe("function");
    expect(result.current.refresh).toBe(result.current.refreshAllModelInputs);
  });

  it("should call refreshAllModelInputs when refresh is invoked", async () => {
    mockNodes = [];

    const { result } = renderHook(() => useRefreshModelInputs());

    await act(async () => {
      await result.current.refresh();
    });

    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "No model components to refresh",
    });
  });

  it("should memoize the refresh function", () => {
    const { result, rerender } = renderHook(() => useRefreshModelInputs());

    const firstRefresh = result.current.refresh;
    rerender();
    const secondRefresh = result.current.refresh;

    expect(firstRefresh).toBe(secondRefresh);
  });
});

// ============================================================================
// Test Helpers
// ============================================================================

function createMockModelNode(id: string): AllNodeType {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "ChatOpenAI",
      showNode: true,
      node: {
        display_name: "OpenAI Chat",
        description: "OpenAI chat model",
        documentation: "",
        template: {
          model: {
            type: "model",
            value: "gpt-4",
            options: ["gpt-4", "gpt-3.5-turbo"],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
          code: {
            type: "code",
            value: "test code",
            required: false,
            list: false,
            show: false,
            readonly: true,
          },
        },
        tool_mode: false,
      },
    },
  } as unknown as AllNodeType;
}
