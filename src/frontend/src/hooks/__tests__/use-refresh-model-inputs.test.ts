import { act, renderHook, waitFor } from "@testing-library/react";
import type { APIClassType, APITemplateType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";

// Mock values - must be defined before jest.mock calls
const mockSetSuccessData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetNode = jest.fn();
let mockModelProviders: Array<{
  provider: string;
  is_enabled: boolean;
  is_configured: boolean;
  models?: Array<{ model_name: string }>;
}> = [];
const mockQueryClient = {
  invalidateQueries: jest.fn().mockResolvedValue(undefined),
  fetchQuery: jest.fn().mockImplementation(async () => mockModelProviders),
};
let mockNodes: AllNodeType[] = [];
let mockComponentsToUpdate: Array<{
  id: string;
  display_name: string;
  outdated: boolean;
  blocked: boolean;
  breakingChange: boolean;
  userEdited: boolean;
}> = [];
let mockAllowCustomComponents = true;
let mockCurrentFlowId = "flow-123";
let mockCurrentFolderId = "folder-456";
// biome-ignore lint/suspicious/noExplicitAny: legacy
let mockTemplates: Record<string, any> = {};

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
      componentsToUpdate: mockComponentsToUpdate,
    }),
  },
  syncNodeTranslations: jest.fn(),
}));

jest.mock("@/stores/utilityStore", () => ({
  useUtilityStore: {
    getState: () => ({ allowCustomComponents: mockAllowCustomComponents }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: {
    getState: () => ({ templates: mockTemplates }),
  },
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      currentFlowId: mockCurrentFlowId,
      currentFlow: { folder_id: mockCurrentFolderId },
    }),
  },
}));

// Import after mocks are set up
import { api } from "@/controllers/API/api";
import { diffGraphs } from "@/utils/flow-diff";
import {
  clearLoadRefreshes,
  withoutLoadRefreshes,
} from "@/utils/load-refreshes";
import {
  buildRefreshPayload,
  createUpdatedNode,
  isModelNode,
  refreshAllModelInputs,
  useRefreshModelInputs,
} from "../use-refresh-model-inputs";

beforeEach(() => {
  mockCurrentFlowId = "flow-123";
  mockCurrentFolderId = "folder-456";
});

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
    // biome-ignore lint/suspicious/noExplicitAny: legacy
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
    mockModelProviders = [];
    mockComponentsToUpdate = [];
    mockAllowCustomComponents = true;
    mockTemplates = {};
  });

  it("should show success message when no model nodes exist", async () => {
    mockNodes = [];

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockSetSuccessData).toHaveBeenCalledWith({
      title: "No model components to refresh",
    });
  });

  it("should not show notifications when silent option is true", async () => {
    mockNodes = [];

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(mockSetSuccessData).not.toHaveBeenCalled();
  });

  it("should invalidate query cache when queryClient is provided", async () => {
    mockNodes = [];

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetModelProviders"],
    });
    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetEnabledModels"],
    });
    expect(mockQueryClient.invalidateQueries).toHaveBeenCalledWith({
      queryKey: ["useGetProviderVariables"],
    });
  });

  it("should not invalidate cache when queryClient is not provided", async () => {
    mockNodes = [];

    await refreshAllModelInputs(undefined);

    expect(mockQueryClient.invalidateQueries).not.toHaveBeenCalled();
    expect(mockQueryClient.fetchQuery).not.toHaveBeenCalled();
  });

  it("should refresh model nodes and show success message", async () => {
    const modelNode = createMockModelNode("node-1");
    Object.assign(modelNode.data.node!, {
      metadata: { component_class_name: "Second" },
    });
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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        frontend_node: { metadata: { component_class_name: "Second" } },
      }),
    );
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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    // Should still call setNode to clear the invalid value
    expect(mockSetNode).toHaveBeenCalled();
  });

  describe("a node with two shown model fields", () => {
    const JEV = [{ name: "jev-latest", provider: "TypeSafe", icon: "Bot" }];
    const routerNode = (): AllNodeType => {
      const node = createMockModelNodeWithValue("router", [
        { name: "gpt-4", provider: "OpenAI", icon: "OpenAI" },
      ]);
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      const template = (node.data as any).node.template;
      template.model.model_type = "language";
      template.decision_model = {
        type: "model",
        model_type: "decision",
        value: JEV,
        options: [],
        show: true,
      };
      return node;
    };
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    const respondWith = (template: any) => ({ data: { template } });

    it("refreshes each field in turn, on top of the previous response", async () => {
      mockNodes = [routerNode()];
      (api.post as jest.Mock)
        .mockImplementationOnce(async (_url, body) =>
          respondWith({ ...body.template, marker: { value: "first" } }),
        )
        .mockImplementationOnce(async (_url, body) =>
          respondWith({ ...body.template, marker2: { value: "second" } }),
        );

      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(undefined as any, { silent: true });

      const calls = (api.post as jest.Mock).mock.calls;
      expect(calls.map(([, body]) => body.field)).toEqual([
        "model",
        "decision_model",
      ]);
      expect(calls[1][1].template.marker).toEqual({ value: "first" });
      expect(calls[1][1].field_value).toEqual(JEV);

      expect(mockSetNode).toHaveBeenCalledTimes(1);
      const updater = mockSetNode.mock.calls[0][1];
      const updated = updater(routerNode());
      const template = updated.data.node.template;
      expect(template.marker2).toEqual({ value: "second" });
      // A decision value is never filled or swapped, even with no options.
      expect(template.decision_model.value).toEqual(JEV);
    });

    it("writes nothing when either field was picked while in flight", async () => {
      mockNodes = [routerNode()];
      (api.post as jest.Mock)
        .mockImplementationOnce(async (_url, body) =>
          respondWith(body.template),
        )
        .mockImplementationOnce(async (_url, body) => {
          const picked = routerNode();
          // biome-ignore lint/suspicious/noExplicitAny: legacy
          (picked.data as any).node.template.decision_model.value = [
            { name: "gpt-6-luna", provider: "OpenAI", icon: "OpenAI" },
          ];
          mockNodes = [picked];
          return respondWith(body.template);
        });

      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(undefined as any, { silent: true });

      expect(api.post).toHaveBeenCalledTimes(2);
      expect(mockSetNode).not.toHaveBeenCalled();
    });

    it("writes nothing when a mode switch in flight shows other model fields", async () => {
      // Language Model mode: only the language model is shown when the refresh starts.
      const start = routerNode();
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      (start.data as any).node.template.decision_model.show = false;
      mockNodes = [start];
      (api.post as jest.Mock).mockImplementationOnce(async (_url, body) => {
        // Switched to Decision Model mode, with a decision model picked; the
        // language model's value is untouched.
        const switched = routerNode();
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        (switched.data as any).node.template.model.show = false;
        mockNodes = [switched];
        return respondWith(body.template);
      });

      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(undefined as any, { silent: true });

      expect(api.post).toHaveBeenCalledTimes(1);
      expect(mockSetNode).not.toHaveBeenCalled();
    });

    it("writes nothing when the Decision Type changed in flight", async () => {
      const withKind = (kind: string, outputs: string[]) => {
        const node = routerNode();
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        const data = (node.data as any).node;
        data.template.decision_kind = { type: "str", value: kind, show: true };
        data.outputs = outputs.map((name) => ({ name, types: ["Message"] }));
        return node;
      };
      mockNodes = [withKind("Choice", ["category_1_result", "default_result"])];
      (api.post as jest.Mock)
        .mockImplementationOnce(async (_url, body) =>
          respondWith(body.template),
        )
        .mockImplementationOnce(async (_url, body) => {
          // Switched to Boolean, which replaces the outputs; no model changed.
          mockNodes = [withKind("Boolean", ["true_result", "false_result"])];
          return respondWith(body.template);
        });

      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(undefined as any, { silent: true });

      expect(api.post).toHaveBeenCalledTimes(2);
      expect(mockSetNode).not.toHaveBeenCalled();
    });

    it("skips a hidden model field", async () => {
      const node = routerNode();
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      (node.data as any).node.template.decision_model.show = false;
      mockNodes = [node];
      (api.post as jest.Mock).mockImplementation(async (_url, body) =>
        respondWith(body.template),
      );

      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(undefined as any, { silent: true });

      expect(
        (api.post as jest.Mock).mock.calls.map(([, body]) => body.field),
      ).toEqual(["model"]);
    });
  });

  it("should not autosave the flow it refreshes", async () => {
    // The refresh runs on every flow open. Autosaving it writes the flow
    // nobody edited (#8995), which under an edit precondition also takes the
    // first writer's turn.
    mockNodes = [createMockModelNode("node-1")];

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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(mockSetNode).toHaveBeenCalledWith(
      "node-1",
      expect.any(Function),
      false,
      undefined,
      { autoSave: false },
    );
  });

  describe("attributing what the refresh rewrote", () => {
    const refreshedTo = (value: string) =>
      (api.post as jest.Mock).mockResolvedValue({
        data: {
          template: {
            model: {
              type: "model",
              value,
              options: [value],
              required: true,
              list: false,
              show: true,
              readonly: false,
            },
          },
        },
      });
    const refreshOnlyChange = () => {
      const base = createMockModelNodeWithValue("node-1", "");
      const updater = mockSetNode.mock.calls[0][1];
      const refreshed = updater(createMockModelNodeWithValue("node-1", ""));
      const changes = diffGraphs(
        { nodes: [base], edges: [] },
        { nodes: [refreshed], edges: [] },
      );
      expect(changes.length).toBeGreaterThan(0);
      return { changes, kept: withoutLoadRefreshes("flow-123", changes) };
    };

    beforeEach(() => {
      clearLoadRefreshes();
      mockNodes = [createMockModelNodeWithValue("node-1", "")];
      refreshedTo("gpt-4");
    });

    it("should record the fields a refresh on flow open rewrote", async () => {
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(mockQueryClient as any, {
        silent: true,
        origin: "load",
      });

      expect(refreshOnlyChange().kept).toEqual([]);
    });

    it("should not record a refresh the person asked for", async () => {
      // biome-ignore lint/suspicious/noExplicitAny: legacy
      await refreshAllModelInputs(mockQueryClient as any, { silent: false });

      const { changes, kept } = refreshOnlyChange();
      expect(kept).toEqual(changes);
    });
  });

  it("should handle API errors gracefully", async () => {
    mockNodes = [createMockModelNode("node-1")];

    const consoleWarnSpy = jest.spyOn(console, "warn").mockImplementation();
    (api.post as jest.Mock).mockRejectedValue(new Error("API Error"));

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(consoleWarnSpy).toHaveBeenCalled();
    expect(mockSetSuccessData).toHaveBeenCalled(); // Still shows success for the batch
    consoleWarnSpy.mockRestore();
  });

  it("should queue concurrent refresh operations", async () => {
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
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    const firstRefresh = refreshAllModelInputs(mockQueryClient as any);

    // Try to start second refresh while first is in progress
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    const secondRefresh = refreshAllModelInputs(mockQueryClient as any);

    // Complete first refresh
    resolveFirst!();
    await firstRefresh;
    await secondRefresh;

    // Second call should be queued and run after first completes (2 total calls)
    expect(api.post).toHaveBeenCalledTimes(2);
  });

  it("discards a deferred response after the active flow scope changes", async () => {
    mockNodes = [createMockModelNode("shared-node-id")];
    let resolveResponse: ((value: unknown) => void) | undefined;
    (api.post as jest.Mock).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    const refresh = refreshAllModelInputs(mockQueryClient as any, {
      silent: true,
    });
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));

    mockCurrentFlowId = "flow-456";
    mockCurrentFolderId = "folder-789";
    resolveResponse?.({
      data: {
        template: {
          model: {
            type: "model",
            options: ["scope-a-model"],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });
    await refresh;

    expect(mockSetNode).not.toHaveBeenCalled();
  });
});

// ============================================================================
// Outdated Component Guard Tests
// ============================================================================

describe("refreshAllModelInputs — outdated component guard", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
    mockModelProviders = [];
    mockComponentsToUpdate = [];
    mockAllowCustomComponents = true;
    mockTemplates = {};
  });

  it("should skip API call for outdated nodes when allowCustomComponents is false", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = [
      {
        id: "node-1",
        display_name: "OpenAI Chat",
        outdated: true,
        blocked: false,
        breakingChange: false,
        userEdited: false,
      },
    ];

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).not.toHaveBeenCalled();
    expect(mockSetNode).not.toHaveBeenCalled();
  });

  it("should NOT skip API call when allowCustomComponents is true even if outdated", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];
    mockAllowCustomComponents = true;
    mockTemplates = {};
    mockComponentsToUpdate = [
      {
        id: "node-1",
        display_name: "OpenAI Chat",
        outdated: true,
        blocked: false,
        breakingChange: false,
        userEdited: false,
      },
    ];

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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("should NOT skip API call for user-edited outdated nodes", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];
    mockAllowCustomComponents = false;
    mockTemplates = {
      ChatOpenAI: {
        template: { code: { value: "test code" } },
      },
    };
    mockComponentsToUpdate = [
      {
        id: "node-1",
        display_name: "OpenAI Chat",
        outdated: true,
        blocked: false,
        breakingChange: false,
        userEdited: true,
      },
    ];

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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("should skip only outdated nodes, refresh non-outdated ones", async () => {
    const outdatedNode = createMockModelNode("node-outdated");
    const freshNode = createMockModelNode("node-fresh");
    mockNodes = [outdatedNode, freshNode];
    mockAllowCustomComponents = false;
    mockTemplates = {
      ChatOpenAI: {
        template: { code: { value: "test code" } },
      },
    };
    mockComponentsToUpdate = [
      {
        id: "node-outdated",
        display_name: "Outdated",
        outdated: true,
        blocked: false,
        breakingChange: false,
        userEdited: false,
      },
    ];

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

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    // Only the fresh node should have been refreshed
    expect(api.post).toHaveBeenCalledTimes(1);
  });

  it("should skip via template code mismatch even when componentsToUpdate is empty", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = []; // Empty — simulating race condition
    mockTemplates = {
      ChatOpenAI: {
        template: { code: { value: "new_server_code" } },
      },
    };

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).not.toHaveBeenCalled();
  });

  it("should skip API calls for blocked nodes when custom components are disabled", async () => {
    const modelNode = createMockModelNode("node-1");
    mockNodes = [modelNode];
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = [
      {
        id: "node-1",
        display_name: "Unknown Custom Node",
        outdated: false,
        blocked: true,
        breakingChange: false,
        userEdited: false,
      },
    ];

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).not.toHaveBeenCalled();
    expect(mockSetNode).not.toHaveBeenCalled();
  });

  it("should skip API calls for CustomComponent nodes even when the generic template exists", async () => {
    const customComponentNode = createMockCustomComponentModelNode("node-1");
    mockNodes = [customComponentNode];
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = [];
    mockTemplates = {
      CustomComponent: {
        template: {
          code: { value: "user custom code" },
        },
      },
    };

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).not.toHaveBeenCalled();
    expect(mockSetNode).not.toHaveBeenCalled();
  });

  it("should suppress 403 as fallback when guards miss due to missing node code", async () => {
    const modelNode = createMockModelNode("node-1");
    delete (modelNode.data.node.template as Record<string, unknown>).code;
    mockNodes = [modelNode];
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = [];

    const consoleWarnSpy = jest.spyOn(console, "warn").mockImplementation();
    (api.post as jest.Mock).mockRejectedValue({
      response: {
        status: 403,
        data: { detail: "Custom components not allowed" },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any);

    expect(api.post).toHaveBeenCalledTimes(1);
    consoleWarnSpy.mockRestore();
  });
});

describe("refreshAllModelInputs — disconnected provider", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
    mockModelProviders = [
      {
        provider: "Anthropic",
        is_enabled: false,
        is_configured: false,
      },
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
      },
    ];
    mockComponentsToUpdate = [];
    mockAllowCustomComponents = true;
    mockTemplates = {};
  });

  function getRefreshedModelValue() {
    const [, updater] = mockSetNode.mock.calls[0];
    const updated = updater(mockNodes[0]);
    // biome-ignore lint/suspicious/noExplicitAny: legacy
    return (updated as any).data.node.template.model.value;
  }

  it("should replace the saved model when its provider was disconnected", async () => {
    mockNodes = [createMockModelNodeWithValue("node-1", ANTHROPIC_SAVED_VALUE)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: ANTHROPIC_SAVED_VALUE,
            options: [OPENAI_OPTION, STICKY_ANTHROPIC_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual([
      expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
    ]);
  });

  it("should not fall back to a sticky option that is listed first", async () => {
    mockNodes = [createMockModelNodeWithValue("node-1", ANTHROPIC_SAVED_VALUE)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: ANTHROPIC_SAVED_VALUE,
            options: [STICKY_ANTHROPIC_OPTION, OPENAI_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual([
      expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
    ]);
  });

  it("should keep the saved model when no selectable option remains", async () => {
    mockNodes = [createMockModelNodeWithValue("node-1", ANTHROPIC_SAVED_VALUE)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: ANTHROPIC_SAVED_VALUE,
            options: [STICKY_ANTHROPIC_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual(ANTHROPIC_SAVED_VALUE);
  });

  it("should keep a model selected while the refresh request was in flight", async () => {
    const pickedMidFlight = [
      {
        name: "gpt-4o-mini",
        provider: "OpenAI Compatible",
        icon: "Plug",
        metadata: {},
      },
    ];
    mockNodes = [createMockModelNodeWithValue("node-1", [])];
    let resolveResponse: ((value: unknown) => void) | undefined;
    (api.post as jest.Mock).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    const refresh = refreshAllModelInputs(mockQueryClient as any, {
      silent: true,
    });
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));

    mockNodes = [createMockModelNodeWithValue("node-1", pickedMidFlight)];
    resolveResponse?.({
      data: {
        template: {
          model: {
            type: "model",
            value: [],
            options: [OPENAI_OPTION, { ...pickedMidFlight[0], metadata: {} }],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });
    await refresh;

    const applied = mockSetNode.mock.calls.map(
      ([, updater]) =>
        // biome-ignore lint/suspicious/noExplicitAny: legacy
        (updater(mockNodes[0]) as any).data.node.template.model.value,
    );
    expect(applied).not.toContainEqual([
      expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
    ]);
  });

  it.each([
    ["field", "display_name"],
    ["field", "info"],
    ["field", "placeholder"],
    ["output", "display_name"],
    ["output", "info"],
  ])(
    "applies refresh and preserves in-flight %s %s presentation",
    async (target, key) => {
      const initial = createMockModelNodeWithValue("node-1", []);
      const initialData = initial.data.node as APIClassType;
      initialData.outputs = [
        {
          name: "response",
          types: ["Message"],
          display_name: "Response",
          info: "Before",
        },
      ];
      initialData.template.model = {
        ...initialData.template.model,
        display_name: "Model",
        info: "Before",
        placeholder: "Before",
      };
      mockNodes = [initial];
      let resolveResponse: ((value: unknown) => void) | undefined;
      (api.post as jest.Mock).mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveResponse = resolve;
          }),
      );
      const refresh = refreshAllModelInputs(undefined, { silent: true });
      await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
      const live = JSON.parse(JSON.stringify(initial)) as AllNodeType;
      const liveData = live.data.node as APIClassType;
      const changed =
        target === "field" ? liveData.template.model : liveData.outputs![0];
      Object.assign(changed, { [key]: "Live presentation" });
      mockNodes = [live];
      resolveResponse?.({
        data: {
          ...initialData,
          template: {
            ...initialData.template,
            model: { ...initialData.template.model, options: [OPENAI_OPTION] },
          },
        },
      });
      await refresh;
      expect(mockSetNode).toHaveBeenCalledTimes(1);
      const updated = mockSetNode.mock.calls[0][1](live).data
        .node as APIClassType;
      expect(updated.template.model.value).toEqual([
        expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
      ]);
      expect(
        target === "field" ? updated.template.model : updated.outputs![0],
      ).toMatchObject({ [key]: "Live presentation" });
    },
  );

  it.each([
    "value",
    "nested value.info",
    "output types",
    "model show",
    "advanced",
    "api_editable",
    "load_from_db",
  ])("rejects a delayed refresh after a substantive %s edit", async (edit) => {
    const initial = createMockModelNodeWithValue("node-1", []);
    const initialData = initial.data.node as APIClassType;
    initialData.template.context = {
      ...initialData.template.model,
      type: "str",
      value: { info: "Original input" },
    };
    initialData.outputs = [
      { name: "response", types: ["Message"], display_name: "Response" },
    ];
    mockNodes = [initial];
    let resolveResponse: ((value: unknown) => void) | undefined;
    (api.post as jest.Mock).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const refresh = refreshAllModelInputs(undefined, { silent: true });
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const live = JSON.parse(JSON.stringify(initial)) as AllNodeType;
    const liveData = live.data.node as APIClassType;
    if (edit === "output types") liveData.outputs![0].types = ["Data"];
    else if (edit === "model show") liveData.template.model.show = false;
    else if (["advanced", "api_editable", "load_from_db"].includes(edit)) {
      liveData.template.context[edit] = true;
    } else
      liveData.template.context.value =
        edit === "value" ? "Changed input" : { info: "Changed nested input" };
    mockNodes = [live];
    resolveResponse?.({
      data: {
        ...initialData,
        template: {
          ...initialData.template,
          model: { ...initialData.template.model, options: [OPENAI_OPTION] },
        },
      },
    });
    await refresh;
    expect(mockSetNode).not.toHaveBeenCalled();
  });

  it("applies the delayed model after concurrent mount refresh hydrates context, options, and credential visibility", async () => {
    const initial = createMockModelNodeWithValue("node-1", []);
    const initialData = initial.data.node as APIClassType;
    initialData.template.model.options = [];
    initialData.template.api_key = {
      ...initialData.template.model,
      type: "str",
      show: true,
      value: "",
    };
    mockNodes = [initial];
    let resolveResponse: ((value: unknown) => void) | undefined;
    (api.post as jest.Mock).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );
    const refresh = refreshAllModelInputs(undefined, { silent: true });
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const live = JSON.parse(JSON.stringify(initial)) as AllNodeType;
    const liveData = live.data.node as APIClassType;
    liveData.template._frontend_node_flow_id = {
      ...initialData.template.code,
      value: mockCurrentFlowId,
    };
    liveData.template._frontend_node_folder_id = {
      ...initialData.template.code,
      value: mockCurrentFolderId,
    };
    liveData.template.api_key.show = false;
    liveData.template.model.options = [OPENAI_OPTION];
    mockNodes = [live];
    resolveResponse?.({ data: liveData });
    await refresh;
    expect(mockSetNode).toHaveBeenCalledTimes(1);
    expect(getRefreshedModelValue()).toEqual([
      expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
    ]);
  });

  it("should apply the refresh when an empty model only changed representation in flight", async () => {
    mockNodes = [createMockModelNodeWithValue("node-1", "")];
    let resolveResponse: ((value: unknown) => void) | undefined;
    (api.post as jest.Mock).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          resolveResponse = resolve;
        }),
    );

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    const refresh = refreshAllModelInputs(mockQueryClient as any, {
      silent: true,
    });
    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));

    mockNodes = [createMockModelNodeWithValue("node-1", [])];
    resolveResponse?.({
      data: {
        template: {
          model: {
            type: "model",
            value: [],
            options: [OPENAI_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });
    await refresh;

    expect(getRefreshedModelValue()).toEqual([
      expect.objectContaining({ name: "gpt-5.6", provider: "OpenAI" }),
    ]);
  });

  it("should keep the saved model when it is still enabled", async () => {
    const savedValue = [
      { name: "gpt-5.6", provider: "OpenAI", icon: "OpenAI" },
    ];
    mockNodes = [createMockModelNodeWithValue("node-1", savedValue)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: savedValue,
            options: [OPENAI_OPTION, STICKY_ANTHROPIC_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: legacy
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual(savedValue);
  });

  it("should preserve a sticky saved model when its provider is configured", async () => {
    mockModelProviders = [
      {
        provider: "Anthropic",
        is_enabled: true,
        is_configured: true,
        models: [{ model_name: "claude-sonnet-5" }],
      },
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
      },
    ];
    mockNodes = [createMockModelNodeWithValue("node-1", ANTHROPIC_SAVED_VALUE)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: ANTHROPIC_SAVED_VALUE,
            options: [OPENAI_OPTION, STICKY_ANTHROPIC_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual(ANTHROPIC_SAVED_VALUE);
    expect(mockQueryClient.fetchQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        queryKey: [
          "useGetModelProviders",
          undefined,
          undefined,
          "flow-123",
          undefined,
          "configure",
        ],
      }),
    );
    expect(
      mockQueryClient.invalidateQueries.mock.invocationCallOrder[0],
    ).toBeLessThan(mockQueryClient.fetchQuery.mock.invocationCallOrder[0]);
  });

  it("should preserve a sticky saved model when provider status cannot be refreshed", async () => {
    mockNodes = [createMockModelNodeWithValue("node-1", ANTHROPIC_SAVED_VALUE)];
    mockQueryClient.fetchQuery.mockRejectedValueOnce(
      new Error("provider catalog unavailable"),
    );

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: ANTHROPIC_SAVED_VALUE,
            options: [OPENAI_OPTION, STICKY_ANTHROPIC_OPTION],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual(ANTHROPIC_SAVED_VALUE);
  });

  it("should match provider and model name when replacing a disconnected selection", async () => {
    const azureSavedValue = [
      {
        name: "gpt-4o",
        provider: "Azure AI Foundry",
        icon: "Azure",
      },
    ];
    mockModelProviders = [
      {
        provider: "Azure AI Foundry",
        is_enabled: false,
        is_configured: false,
      },
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
      },
    ];
    mockNodes = [createMockModelNodeWithValue("node-1", azureSavedValue)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: azureSavedValue,
            options: [
              {
                name: "gpt-4o",
                provider: "OpenAI",
                icon: "OpenAI",
                metadata: {},
              },
              {
                name: "gpt-4o",
                provider: "Azure AI Foundry",
                icon: "Azure",
                metadata: { not_enabled_locally: true },
              },
            ],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual([
      expect.objectContaining({ name: "gpt-4o", provider: "OpenAI" }),
    ]);
  });

  it("should retain name-only matching for legacy saved values without a provider", async () => {
    const legacySavedValue = [{ name: "gpt-4o", icon: "Bot" }];
    mockModelProviders = [
      {
        provider: "OpenAI",
        is_enabled: true,
        is_configured: true,
      },
    ];
    mockNodes = [createMockModelNodeWithValue("node-1", legacySavedValue)];

    (api.post as jest.Mock).mockResolvedValue({
      data: {
        template: {
          model: {
            type: "model",
            value: legacySavedValue,
            options: [
              {
                name: "gpt-4o",
                provider: "OpenAI",
                icon: "OpenAI",
                metadata: {},
              },
            ],
            required: true,
            list: false,
            show: true,
            readonly: false,
          },
        },
      },
    });

    // biome-ignore lint/suspicious/noExplicitAny: test query-client double
    await refreshAllModelInputs(mockQueryClient as any, { silent: true });

    expect(getRefreshedModelValue()).toEqual(legacySavedValue);
  });
});

// ============================================================================
// Hook Tests
// ============================================================================

describe("useRefreshModelInputs", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [];
    mockModelProviders = [];
    mockComponentsToUpdate = [];
    mockAllowCustomComponents = true;
    mockTemplates = {};
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

const OPENAI_OPTION = {
  name: "gpt-5.6",
  provider: "OpenAI",
  icon: "OpenAI",
  metadata: {},
};

// The backend re-injects a saved selection missing from the enabled catalog as
// a sticky-default option, so its presence must not make the value look valid.
const STICKY_ANTHROPIC_OPTION = {
  name: "claude-sonnet-5",
  provider: "Anthropic",
  icon: "Anthropic",
  metadata: { not_enabled_locally: true },
};

const ANTHROPIC_SAVED_VALUE = [
  { name: "claude-sonnet-5", provider: "Anthropic", icon: "Anthropic" },
];

function createMockModelNodeWithValue(
  id: string,
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  value: any,
): AllNodeType {
  const node = createMockModelNode(id);
  // biome-ignore lint/suspicious/noExplicitAny: legacy
  (node.data as any).node.template.model.value = value;
  return node;
}

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

function createMockCustomComponentModelNode(id: string): AllNodeType {
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "CustomComponent",
      showNode: true,
      node: {
        display_name: "Custom Component",
        description: "User-defined custom component",
        documentation: "",
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
          code: {
            type: "code",
            value: "user custom code",
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
