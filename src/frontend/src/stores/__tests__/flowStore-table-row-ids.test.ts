import { act } from "@testing-library/react";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { hasTableRowIds } from "@/utils/table-row-ids";

jest.mock("@xyflow/react", () => ({
  addEdge: jest.fn(),
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
    getState: () => ({ setErrorData: jest.fn(), setSuccessData: jest.fn() }),
  },
}));

jest.mock("../flowsManagerStore", () => ({
  __esModule: true,
  default: {
    getState: () => ({
      currentFlow: undefined,
      currentFlowId: "flow-1",
      setCurrentFlow: jest.fn(),
      autoSaving: true,
    }),
  },
}));

jest.mock("../tweaksStore", () => ({
  useTweaksStore: { getState: () => ({ initialSetup: jest.fn() }) },
}));

jest.mock("@/CustomNodes/helpers/check-code-validity", () => ({
  checkCodeValidity: jest.fn(() => null),
}));

import useFlowStore from "../flowStore";

type Row = Record<string, unknown>;

const node = (
  id: string,
  rows: Row[],
  extra: Record<string, unknown> = {},
): AllNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "APIRequest",
      node: {
        display_name: id,
        description: "",
        template: {
          headers: { type: "table", value: rows },
          url: { type: "str", value: "", ...extra },
        },
      },
    },
  }) as unknown as AllNodeType;

const headers = (id: string): Row[] =>
  (
    useFlowStore.getState().nodes.find((n) => n.id === id)!.data as unknown as {
      node: { template: { headers: { value: Row[] } } };
    }
  ).node.template.headers.value;

describe("flowStore table row ids", () => {
  const legacyRows = [{ key: "Accept", value: "json" }];

  beforeEach(() => {
    act(() => {
      useFlowStore.setState({
        nodes: [node("a", legacyRows)],
        edges: [] as EdgeType[],
        autoSaveFlow: undefined,
      });
    });
  });

  it("leaves a legacy table alone when another field of its node changes", () => {
    act(() =>
      useFlowStore
        .getState()
        .setNode("a", node("a", legacyRows, { value: "https://x" })),
    );

    expect(headers("a")).toEqual(legacyRows);
  });

  it("writes a legacy table whole, with ids, on its first edit", () => {
    act(() =>
      useFlowStore
        .getState()
        .setNode("a", node("a", [...legacyRows, { key: "X", value: "1" }])),
    );

    const rows = headers("a");
    expect(hasTableRowIds(rows)).toBe(true);
    expect(rows.map((row) => row.key)).toEqual(["Accept", "X"]);
  });

  it("gives the default rows of an added component ids", () => {
    act(() =>
      useFlowStore
        .getState()
        .setNodes((nodes) => [...nodes, node("b", [{ key: "default" }])]),
    );

    expect(headers("a")).toEqual(legacyRows);
    expect(hasTableRowIds(headers("b"))).toBe(true);
  });

  it("gives rows ids when the canvas is replaced with new components", () => {
    act(() =>
      useFlowStore.getState().setNodesAndEdges([node("c", [{ key: "x" }])], []),
    );

    expect(hasTableRowIds(headers("c"))).toBe(true);
  });
});
