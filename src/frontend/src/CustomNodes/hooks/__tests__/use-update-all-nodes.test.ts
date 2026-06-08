import { act, renderHook } from "@testing-library/react";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import useUpdateAllNodes from "../use-update-all-nodes";

let mockNodes: AllNodeType[] = [];

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = {
    getState: () => ({
      nodes: mockNodes,
    }),
  };

  return {
    __esModule: true,
    default: useFlowStore,
  };
});

describe("useUpdateAllNodes", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockNodes = [
      {
        id: "node-1",
        type: "genericNode",
        position: { x: 0, y: 0 },
        data: {
          id: "node-1",
          type: "OldType",
          description: "Old description",
          display_name: "Old name",
          node: {
            display_name: "Old name",
            description: "Old description",
            template: {
              code: { value: "old code" },
              prompt: { value: "local prompt", show: true },
            },
            outputs: [
              { name: "result", display_name: "Result", types: ["str"] },
            ],
            edited: true,
          },
        },
      } as unknown as AllNodeType,
    ];
  });

  it("bulk rebuilds nodes through explicit collaboration field updates", () => {
    const baseNode = {
      display_name: "Old name",
      description: "Old description",
      template: {
        code: { value: "old code" },
        prompt: { value: "old prompt", show: true },
      },
      outputs: [{ name: "result", display_name: "Result", types: ["str"] }],
      edited: true,
    } as unknown as APIClassType;
    const generatedNode = {
      display_name: "New name",
      description: "New description",
      template: {
        code: { value: "generated code" },
        prompt: { value: "generated prompt", show: false },
      },
      outputs: [
        {
          name: "result",
          display_name: "Generated Result",
          types: ["Message"],
        },
      ],
    } as unknown as APIClassType;
    const mockSetNodes = jest.fn((updater, options) => {
      mockNodes = typeof updater === "function" ? updater(mockNodes) : updater;
      return options;
    });
    const mockUpdateNodeInternals = jest.fn();

    const { result } = renderHook(() =>
      useUpdateAllNodes(mockSetNodes, mockUpdateNodeInternals),
    );

    act(() => {
      result.current([
        {
          nodeId: "node-1",
          baseNode,
          newNode: generatedNode,
          code: "confirmed code",
          name: "code",
          type: "NewType",
        },
      ]);
    });

    const mutationOptions = mockSetNodes.mock.calls[0][1];

    expect(mockNodes[0].data.node!.template.code.value).toBe("confirmed code");
    expect(mockNodes[0].data.node!.template.prompt.value).toBe("local prompt");
    expect(mockNodes[0].data.node!.template.prompt.show).toBe(false);
    expect(mutationOptions.collaborationUpdates).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ["data", "node", "template", "code", "value"],
          value: "confirmed code",
        }),
        expect.objectContaining({
          path: ["data", "node", "template", "prompt", "show"],
          value: false,
        }),
        expect.objectContaining({
          path: ["data", "node", "outputs"],
        }),
        expect.objectContaining({
          path: ["data", "type"],
          value: "NewType",
        }),
      ]),
    );
    expect(
      mutationOptions.collaborationUpdates.some(
        (update) => update.path.join(".") === "data.node.template",
      ),
    ).toBe(false);
    expect(mockUpdateNodeInternals).toHaveBeenCalledWith("node-1");
  });
});
