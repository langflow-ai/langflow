import { connectedFieldsByNode } from "@/CustomNodes/helpers/check-code-validity";
import type { EdgeType, GenericNodeType } from "@/types/flow";
import {
  countFlowEdges,
  nodeWithGroupValues,
  walkFlowNodes,
} from "../grouped-nodes";

function fixture() {
  const leaf = {
    id: "leaf",
    type: "genericNode",
    data: {
      id: "leaf",
      type: "Parser",
      node: {
        template: { input: { type: "str", value: "old" } },
      },
    },
  } as unknown as GenericNodeType;
  const group = {
    id: "group",
    type: "genericNode",
    data: {
      id: "group",
      type: "GroupNode",
      node: {
        template: {
          exposed: {
            value: "saved",
            file_path: ["file-id"],
            load_from_db: true,
            proxy: { id: "leaf", field: "input" },
          },
        },
        flow: { data: { nodes: [leaf], edges: [] } },
      },
    },
  } as unknown as GenericNodeType;
  return { leaf, group };
}

describe("saved group traversal", () => {
  it("combines internal connections and incoming edge proxies, giving the edge proxy precedence", () => {
    const { group } = fixture();
    group.data.node!.flow!.data!.edges = [
      {
        id: "internal",
        source: "other",
        target: "leaf",
        targetHandle: "str|internal|leaf",
      },
    ];
    const incoming = {
      id: "incoming",
      source: "outer",
      target: "group",
      data: {
        targetHandle: {
          fieldName: "exposed",
          proxy: { id: "leaf", field: "from_edge" },
        },
      },
    } as EdgeType;

    const context = [...walkFlowNodes([group], [incoming])].find(
      ({ node }) => node.id === "leaf",
    )!;

    expect(connectedFieldsByNode(context.edges!).get("leaf")).toEqual(
      new Set(["internal", "from_edge"]),
    );
    expect(context.edges![0].data?.targetHandle.fieldName).toBe("internal");
    expect(countFlowEdges([group], [incoming])).toBe(2);
  });

  it.each([undefined, null])(
    "leaves connection knowledge unknown when a saved group has no edge list (%s)",
    (edges) => {
      const { group } = fixture();
      Reflect.set(group.data.node!.flow!.data!, "edges", edges);

      const context = [...walkFlowNodes([group], [])].find(
        ({ node }) => node.id === "leaf",
      )!;

      expect(context.edges).toBeUndefined();
    },
  );

  it("keeps descendants' connectivity unknown after an unreadable incoming group edge", () => {
    const { group } = fixture();
    const incoming = {
      id: "incoming",
      source: "outer",
      target: "group",
      targetHandle: "str|exposed|group",
      data: { targetHandle: {} },
    } as EdgeType;

    const context = [...walkFlowNodes([group], [incoming])].find(
      ({ node }) => node.id === "leaf",
    )!;

    expect(context.edges).toBeUndefined();
  });

  it("copies group values, file paths, and variable references without changing either saved node", () => {
    const { leaf, group } = fixture();
    const context = [...walkFlowNodes([group], [])].find(
      ({ node }) => node.id === "leaf",
    )!;

    const effective = nodeWithGroupValues(context) as GenericNodeType;

    expect(effective.data.node!.template.input).toMatchObject({
      value: "saved",
      file_path: ["file-id"],
      load_from_db: true,
    });
    effective.data.node!.template.input.file_path.push("another");
    expect(group.data.node!.template.exposed.file_path).toEqual(["file-id"]);
    expect(leaf.data.node!.template.input.value).toBe("old");
  });
});
