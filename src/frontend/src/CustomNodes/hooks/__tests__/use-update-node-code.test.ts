import { act, renderHook } from "@testing-library/react";
import type { APIClassType } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import useUpdateNodeCode from "../use-update-node-code";

const mockSetComponentsToUpdate = jest.fn();
let mockLatestNode: AllNodeType | undefined;

jest.mock("@/stores/flowStore", () => {
  const useFlowStore = (
    selector?: (state: {
      setComponentsToUpdate: typeof mockSetComponentsToUpdate;
    }) => unknown,
  ) =>
    selector
      ? selector({ setComponentsToUpdate: mockSetComponentsToUpdate })
      : { setComponentsToUpdate: mockSetComponentsToUpdate };
  useFlowStore.getState = () => ({
    getNode: () => mockLatestNode,
  });

  return {
    __esModule: true,
    default: useFlowStore,
  };
});

describe("useUpdateNodeCode", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockLatestNode = {
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
          outputs: [{ name: "result", display_name: "Result", types: ["str"] }],
          edited: true,
        },
      },
    } as unknown as AllNodeType;
  });

  it("updates code rebuilds through explicit collaboration field updates", () => {
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
    const mockSetNode = jest.fn();
    const mockUpdateNodeInternals = jest.fn();

    const { result } = renderHook(() =>
      useUpdateNodeCode(
        "node-1",
        baseNode,
        mockSetNode,
        mockUpdateNodeInternals,
      ),
    );

    act(() => {
      result.current(generatedNode, "confirmed code", "code", "NewType");
    });

    const updatedNode = mockSetNode.mock.calls[0][1] as AllNodeType;
    const mutationOptions = mockSetNode.mock.calls[0][4];

    expect(updatedNode.data.node!.template.code.value).toBe("confirmed code");
    expect(updatedNode.data.node!.template.prompt.value).toBe("local prompt");
    expect(updatedNode.data.node!.template.prompt.show).toBe(false);
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
