import type { UseMutationResult } from "@tanstack/react-query";
import type { APIClassType, ResponseErrorDetailAPI } from "@/types/api";
import type { AllNodeType } from "@/types/flow";
import { mutateTemplate } from "../mutate-template";

const mockSetNode = jest.fn();
let mockLatestNode: AllNodeType | undefined;

jest.mock("@/constants/constants", () => ({
  SAVE_DEBOUNCE_TIME: 0,
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      getNode: () => mockLatestNode,
      setNode: mockSetNode,
    }),
  },
}));

describe("mutateTemplate", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockLatestNode = {
      id: "node-1",
      type: "genericNode",
      position: { x: 0, y: 0 },
      data: {
        id: "node-1",
        type: "TestComponent",
        node: {
          display_name: "Test Component",
          template: {
            prompt: { value: "local prompt", show: true },
            other: { value: "local other" },
          },
          outputs: [{ name: "result", display_name: "Result", types: ["str"] }],
        },
      },
    } as unknown as AllNodeType;
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("applies refresh responses through explicit three-way collaboration updates", async () => {
    const baseNode = {
      display_name: "Test Component",
      template: {
        prompt: { value: "base prompt", show: true },
        other: { value: "base other" },
      },
      outputs: [{ name: "result", display_name: "Result", types: ["str"] }],
    } as unknown as APIClassType;
    const postTemplateValue = {
      mutateAsync: jest.fn().mockResolvedValue({
        template: {
          prompt: { value: "generated prompt", show: false },
          other: { value: "generated other" },
        },
        outputs: [
          {
            name: "result",
            display_name: "Generated Result",
            types: ["Message"],
          },
        ],
        last_updated: "2026-06-08T00:00:00Z",
      }),
    } as unknown as UseMutationResult<
      APIClassType | undefined,
      ResponseErrorDetailAPI,
      unknown
    >;
    const setNodeClass = jest.fn();
    const setErrorData = jest.fn();

    await mutateTemplate(
      "next prompt",
      "node-1",
      baseNode,
      setNodeClass,
      postTemplateValue,
      setErrorData,
      "prompt",
    );
    await jest.runOnlyPendingTimersAsync();

    const updatedNode = mockSetNode.mock.calls[0][1] as AllNodeType;
    const mutationOptions = mockSetNode.mock.calls[0][4];

    expect(updatedNode.data.node!.template.prompt.value).toBe("local prompt");
    expect(updatedNode.data.node!.template.prompt.show).toBe(false);
    expect(updatedNode.data.node!.template.other.value).toBe("local other");
    expect(mutationOptions.collaborationUpdates).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          path: ["data", "node", "template", "prompt", "show"],
          value: false,
        }),
        expect.objectContaining({
          path: ["data", "node", "outputs"],
        }),
      ]),
    );
    expect(
      mutationOptions.collaborationUpdates.some(
        (update) => update.path.join(".") === "data.node.template",
      ),
    ).toBe(false);
    expect(setNodeClass).toHaveBeenCalledWith(updatedNode.data.node);
    expect(setErrorData).not.toHaveBeenCalled();
  });
});
