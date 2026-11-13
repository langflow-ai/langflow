import { act } from "@testing-library/react";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { scapedJSONStringfy, updateIds } from "@/utils/reactflowUtils";

jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn((edge, edges) => [...edges, edge]),
  applyEdgeChanges: jest.fn((_changes, edges) => edges),
  applyNodeChanges: jest.fn((_changes, nodes) => nodes),
}));

jest.mock("../../i18n", () => ({
  __esModule: true,
  default: { t: jest.fn((key: string) => key) },
}));

jest.mock("../alertStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      setErrorData: jest.fn(),
      setSuccessData: jest.fn(),
      setNoticeData: jest.fn(),
    }),
  },
}));

jest.mock("../flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      currentFlow: undefined,
      currentFlowId: undefined,
      setCurrentFlow: jest.fn(),
    }),
  },
}));

jest.mock("../darkStore", () => ({
  useDarkStore: { getState: () => ({ dark: false }) },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: { getState: () => ({ initialSetup: jest.fn() }) },
}));

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(() => null),
}));

import useFlowStore from "../flowStore";

const OPAQUE_ID = /^e-[0-9A-Za-z]{21}$/;

const node = (id: string, type: string): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type,
      node: { display_name: type, description: "", template: {} },
    },
  }) as unknown as AllNodeType;

const sourceHandle = (id: string) =>
  scapedJSONStringfy({
    dataType: "ChatInput",
    id,
    name: "message",
    output_types: ["Message"],
  });
const targetHandle = (id: string) =>
  scapedJSONStringfy({
    fieldName: "input_value",
    id,
    inputTypes: ["Message"],
    type: "str",
  });

const edge = (source: string, target: string, id: string): EdgeType =>
  ({
    id,
    source,
    target,
    sourceHandle: sourceHandle(source),
    targetHandle: targetHandle(target),
    data: {},
  }) as EdgeType;

describe("edge ids", () => {
  beforeEach(() => {
    act(() => {
      useFlowStore.setState({
        nodes: [node("ChatInput-a", "ChatInput"), node("Agent-b", "Agent")],
        edges: [],
        autoSaveFlow: undefined,
        currentFlow: undefined,
      });
    });
  });

  it("gives a new connection an opaque id", () => {
    act(() =>
      useFlowStore.getState().onConnect({
        source: "ChatInput-a",
        target: "Agent-b",
        sourceHandle: sourceHandle("ChatInput-a"),
        targetHandle: targetHandle("Agent-b"),
      }),
    );

    const [connected] = useFlowStore.getState().edges;
    expect(connected.id).toMatch(OPAQUE_ID);
    expect(connected.id).not.toContain("ChatInput");
  });

  it("gives pasted edges new opaque ids", () => {
    act(() =>
      useFlowStore.getState().paste(
        {
          nodes: [node("Prompt-a", "Prompt"), node("Agent-c", "Agent")],
          edges: [edge("Prompt-a", "Agent-c", "reactflow__edge-old")],
        },
        { x: 0, y: 0, paneX: 1, paneY: 1 },
      ),
    );

    const pasted = useFlowStore.getState().edges;
    expect(pasted).toHaveLength(1);
    expect(pasted[0].id).toMatch(OPAQUE_ID);
    expect(pasted[0].source).not.toBe("Prompt-a");
  });

  it("keeps the id of an edge whose ends keep their ids", () => {
    const nodes = [node("P-1", "P"), node("Q-1", "Q"), node("R-1", "R")];
    const stays = edge("Q-1", "R-1", "stays-the-same");
    const renamed = edge("P-1", "Q-1", "legacy-id");

    // Only the selected node gets a new id, as when grouping.
    updateIds({ nodes, edges: [stays, renamed] }, {
      nodes: [node("P-1", "P")],
      edges: [],
    } as never);

    expect(stays.id).toBe("stays-the-same");
    expect(renamed.id).toMatch(OPAQUE_ID);
  });
});
