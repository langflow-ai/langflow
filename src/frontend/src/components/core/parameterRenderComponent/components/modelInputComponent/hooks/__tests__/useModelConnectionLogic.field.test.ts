import { renderHook } from "@testing-library/react";
import { scapeJSONParse } from "@/utils/reactflowUtils";
import { useModelConnectionLogic } from "../useModelConnectionLogic";

const mockNode = {
  id: "router",
  data: {
    node: {
      template: {
        model: { type: "model", value: [{ name: "keep" }] },
        llm: {
          type: "model",
          value: [{ name: "gpt-6-luna" }],
          input_types: ["LanguageModel"],
        },
      },
    },
  },
};
const mockSetNode = jest.fn();
const mockSetFilterType = jest.fn();

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      getNode: () => mockNode,
      setNode: mockSetNode,
      setFilterEdge: jest.fn(),
      setFilterType: mockSetFilterType,
      nodes: [],
    }),
  },
}));

jest.mock("@/stores/typesStore", () => ({
  useTypesStore: { getState: () => ({ data: {} }) },
}));

describe("useModelConnectionLogic with a field name", () => {
  it("puts the field it was given into connection mode, not template.model", () => {
    const { result } = renderHook(() =>
      useModelConnectionLogic({
        nodeId: "router",
        fieldName: "llm",
        closePopover: jest.fn(),
        clearSelection: jest.fn(),
      }),
    );

    result.current.handleExternalOptions("connect_other_models");

    const updater = mockSetNode.mock.calls[0][1];
    const template = updater(mockNode).data.node.template;
    expect(template.llm).toMatchObject({ value: [], _connection_mode: true });
    expect(template.model).toEqual(mockNode.data.node.template.model);

    const { targetHandle } = mockSetFilterType.mock.calls[0][0];
    expect(scapeJSONParse(targetHandle).fieldName).toBe("llm");
  });
});
