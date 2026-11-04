import { act, renderHook } from "@testing-library/react";
import { cloneDeep } from "lodash";
import type { APIClassType } from "@/types/api";
import type {
  AllNodeType,
  EdgeType,
  FlowType,
  GenericNodeType,
} from "@/types/flow";
import { nodeWithGroupValues, walkFlowNodes } from "@/utils/grouped-nodes";
import {
  cleanEdges,
  generateNodeTemplate,
  scapedJSONStringfy,
  scapeJSONParse,
} from "@/utils/reactflowUtils";
import useUpdateAllNodes from "../use-update-all-nodes";

const component = (id: string, value: string): GenericNodeType =>
  ({
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "Prompt",
      node: {
        display_name: "Prompt",
        template: {
          code: { type: "code", value: "old code" },
          input: { type: "str", value, show: true, input_types: ["Message"] },
        },
        outputs: [
          {
            name: "out",
            display_name: "Output",
            types: ["Message"],
            selected: "Message",
          },
        ],
      },
    },
  }) as unknown as GenericNodeType;

function group(
  id: string,
  nodes: AllNodeType[],
  edges: EdgeType[] = [],
): GenericNodeType {
  const flow = { name: id, data: { nodes, edges } } as FlowType;
  return {
    id,
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id,
      type: "GroupNode",
      node: {
        flow,
        template: generateNodeTemplate(flow),
        outputs: [],
      } as unknown as APIClassType,
    },
  };
}

function setup(initialNodes: AllNodeType[]) {
  let nodes = initialNodes;
  const updateNodeInternals = jest.fn();
  const setNodes = (
    change: AllNodeType[] | ((nodes: AllNodeType[]) => AllNodeType[]),
  ) => {
    nodes = typeof change === "function" ? change(nodes) : change;
  };
  const { result } = renderHook(() =>
    useUpdateAllNodes(setNodes, updateNodeInternals),
  );
  return {
    result,
    getNodes: () => nodes as GenericNodeType[],
    updateNodeInternals,
  };
}

const savedHandleFormats = ["legacy", "structured", "escaped"] as const;

function connectedGroup(format: (typeof savedHandleFormats)[number]) {
  const source = component("source", "");
  const target = component("target", "");
  // Old output handles used the joined output type as the output name.
  if (format === "legacy") {
    source.data.node!.output_types = ["Message"];
    source.data.node!.outputs![0].name = "Message";
  }
  const sourceHandle = {
    id: "source",
    dataType: "Prompt",
    name: source.data.node!.outputs![0].name,
    output_types: ["Message"],
  };
  const targetHandle = {
    id: "target",
    fieldName: "input",
    type: "str",
    inputTypes: ["Message"],
  };
  const edge = {
    id: "internal",
    source: "source",
    target: "target",
    ...(format === "structured"
      ? { data: { sourceHandle, targetHandle } }
      : {
          sourceHandle:
            format === "legacy"
              ? "Message|source"
              : scapedJSONStringfy(sourceHandle),
          targetHandle:
            format === "legacy"
              ? "str|input|target"
              : scapedJSONStringfy(targetHandle),
        }),
  } as EdgeType;
  return { initial: group("group", [source, target], [edge]), target, edge };
}

describe("grouped component updates", () => {
  it("updates a nested node and its proxy contracts without losing group or sibling values", () => {
    const leaf = component("leaf", "stale child value");
    const inner = group("inner", [
      leaf,
      component("sibling", "stale sibling value"),
    ]);
    const outer = group("outer", [inner]);
    outer.data.node!.template.input_leaf_inner.value = "saved group value";
    outer.data.node!.template.input_leaf_inner.load_from_db = true;
    outer.data.node!.template.input_sibling_inner.value = "outer sibling value";
    inner.data.node!.template.input_sibling.value = "saved sibling value";
    const initial = cloneDeep(outer);
    const context = Array.from(walkFlowNodes([outer], [])).find(
      ({ node }) => node.id === "leaf",
    )!;
    const rebuilt = (nodeWithGroupValues(context) as GenericNodeType).data
      .node!;
    rebuilt.template.extra = {
      type: "str",
      value: "new default",
      show: true,
      required: false,
      list: false,
      readonly: false,
    };
    rebuilt.outputs![0].types = ["Data"];
    rebuilt.outputs![0].selected = "Data";
    const { result, getNodes, updateNodeInternals } = setup([outer]);

    act(() =>
      result.current([
        { nodeId: "leaf", newNode: rebuilt, name: "code", code: "new code" },
      ]),
    );

    const updatedOuter = getNodes()[0];
    const updatedInner = updatedOuter.data.node!.flow!.data!
      .nodes[0] as GenericNodeType;
    const updatedLeaf = updatedInner.data.node!.flow!.data!
      .nodes[0] as GenericNodeType;
    expect(updatedLeaf.data.node!.template.input).toMatchObject({
      value: "saved group value",
      load_from_db: true,
    });
    expect(updatedLeaf.data.node!.template.code.value).toBe("new code");
    expect(updatedLeaf.data.node!.edited).toBe(false);
    expect(updatedOuter.data.node!.template.extra_leaf_inner.value).toBe(
      "new default",
    );
    expect(updatedOuter.data.node!.template.input_leaf_inner.value).toBe(
      "saved group value",
    );
    expect(updatedInner.data.node!.template.input_sibling.value).toBe(
      "saved sibling value",
    );
    expect(updatedOuter.data.node!.template.input_sibling_inner.value).toBe(
      "outer sibling value",
    );
    expect(updatedOuter.data.node!.outputs).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ name: "inner_leaf_out", types: ["Data"] }),
      ]),
    );
    expect(updateNodeInternals).toHaveBeenCalledWith("outer");
    expect(outer).toEqual(initial);
  });

  it.each(savedHandleFormats)(
    "preserves a compatible internal edge saved with %s handles",
    (format) => {
      const { initial, target, edge } = connectedGroup(format);
      const { result, getNodes } = setup([initial]);

      act(() =>
        result.current([
          {
            nodeId: "target",
            newNode: target.data.node!,
            name: "code",
            code: "new code",
          },
        ]),
      );

      const edges = getNodes()[0].data.node!.flow!.data!.edges;
      expect(edges).toHaveLength(1);
      expect(edges[0].data?.targetHandle).toMatchObject({
        fieldName: "input",
        type: "str",
      });
      expect(edges[0].data?.sourceHandle).toMatchObject({
        name: format === "legacy" ? "Message" : "out",
      });
      expect(getNodes()[0].data.node!.template.input_target).toBeUndefined();
      expect(initial.data.node!.flow!.data!.edges).toEqual([edge]);
    },
  );

  it("normalizes mixed saved edge formats without reinterpreting current handles as legacy", () => {
    const { initial, target } = connectedGroup("legacy");
    const data = initial.data.node!.flow!.data!;
    const source = data.nodes[0] as GenericNodeType;
    source.data.node!.outputs!.push({
      ...source.data.node!.outputs![0],
      name: "out",
    });
    data.edges = savedHandleFormats.map((format) => ({
      ...connectedGroup(format).edge,
      id: format,
    }));
    const { result, getNodes } = setup([initial]);

    act(() =>
      result.current([
        {
          nodeId: "target",
          newNode: target.data.node!,
          name: "code",
          code: "new code",
        },
      ]),
    );

    expect(getNodes()[0].data.node!.flow!.data!.edges).toHaveLength(3);
  });

  it.each(savedHandleFormats)(
    "cleans a removed input's internal edge saved with %s handles before refreshing group proxies",
    (format) => {
      const { initial, target } = connectedGroup(format);
      const rebuilt = cloneDeep(target.data.node!);
      delete rebuilt.template.input;
      const { result, getNodes } = setup([initial]);

      act(() =>
        result.current([
          {
            nodeId: "target",
            newNode: rebuilt,
            name: "code",
            code: "new code",
          },
        ]),
      );

      expect(getNodes()[0].data.node!.flow!.data!.edges).toEqual([]);
      expect(getNodes()[0].data.node!.template.input_target).toBeUndefined();
      expect(initial.data.node!.flow!.data!.edges).toHaveLength(1);
    },
  );

  it("keeps saved proxy names and external connections when a grouped input remains compatible", () => {
    const source = component("source", "");
    const leaf = component("leaf", "child value");
    const wrapper = group("group", [leaf]);
    wrapper.data.node!.template.exposed =
      wrapper.data.node!.template.input_leaf;
    delete wrapper.data.node!.template.input_leaf;
    wrapper.data.node!.outputs = [
      {
        ...leaf.data.node!.outputs![0],
        name: "saved_output",
        proxy: { id: "leaf", name: "out", nodeDisplayName: "Prompt" },
      },
    ];
    const sourceHandle = {
      id: "source",
      dataType: "Prompt",
      name: "out",
      output_types: ["Message"],
    };
    const targetHandle = {
      id: "group",
      fieldName: "exposed",
      type: "str",
      inputTypes: ["Message"],
      proxy: { id: "leaf", field: "input" },
    };
    const edge = {
      id: "external",
      source: "source",
      target: "group",
      sourceHandle: scapedJSONStringfy(sourceHandle),
      targetHandle: scapedJSONStringfy(targetHandle),
      data: { sourceHandle, targetHandle },
    } as EdgeType;
    const { result, getNodes } = setup([source, wrapper]);

    act(() =>
      result.current([
        {
          nodeId: "leaf",
          newNode: leaf.data.node!,
          name: "code",
          code: "new code",
        },
      ]),
    );

    expect(getNodes()[1].data.node!.template.exposed.proxy).toEqual({
      id: "leaf",
      field: "input",
    });
    expect(getNodes()[1].data.node!.outputs![0].name).toBe("saved_output");
    expect(cleanEdges(getNodes(), [edge]).edges).toHaveLength(1);
  });
});

describe("grouped ChatOutput migration", () => {
  it.each([1, 2])(
    "preserves an external connection through %i group levels",
    (depth) => {
      const { nodes, edge, exposed, proxy } = updateGroupedChatOutput(depth);
      const result = cleanEdges(nodes, [edge]);

      expect(result.brokenEdges).toEqual([]);
      expect(result.edges).toHaveLength(1);
      const migrated = result.edges[0];
      expect(scapeJSONParse(migrated.targetHandle!)).toEqual({
        id: "outer",
        fieldName: exposed,
        type: "other",
        inputTypes: ["Message"],
        proxy,
      });
      expect(migrated.data!.targetHandle).toEqual(
        scapeJSONParse(migrated.targetHandle!),
      );
      expect(cleanEdges(nodes, result.edges)).toEqual(result);
    },
  );

  it.each([1, 2])(
    "still rejects an incompatible connection through %i group levels",
    (depth) => {
      const { nodes, edge } = updateGroupedChatOutput(depth, ["Data"]);
      const result = cleanEdges(nodes, [edge]);

      expect(result.edges).toHaveLength(0);
      expect(result.brokenEdges).toHaveLength(1);
    },
  );
});

function updateGroupedChatOutput(depth: number, inputTypes = ["Message"]) {
  const source = component("source", "");
  const leaf = component("leaf", "saved message");
  leaf.data.type = "ChatOutput";
  Object.assign(leaf.data.node!, {
    metadata: { component_class_name: "ChatOutput" },
  });
  leaf.data.node!.template.input_value = {
    ...leaf.data.node!.template.input,
    _input_type: "MessageInput",
  };
  delete leaf.data.node!.template.input;
  const child = depth === 1 ? leaf : group("inner", [leaf]);
  const wrapper = group("outer", [child]);
  const generatedName =
    depth === 1 ? "input_value_leaf" : "input_value_leaf_inner";
  const exposed = "saved_exposed_name";
  wrapper.data.node!.template[exposed] =
    wrapper.data.node!.template[generatedName];
  delete wrapper.data.node!.template[generatedName];
  const proxy = cloneDeep(wrapper.data.node!.template[exposed].proxy);
  const sourceHandle = {
    id: "source",
    dataType: "Prompt",
    name: "out",
    output_types: ["Message"],
  };
  const targetHandle = {
    id: "outer",
    fieldName: exposed,
    type: "str",
    inputTypes: ["Message"],
    proxy,
  };
  const edge = {
    id: "external",
    source: "source",
    target: "outer",
    sourceHandle: scapedJSONStringfy(sourceHandle),
    targetHandle: scapedJSONStringfy(targetHandle),
    data: { sourceHandle, targetHandle },
  } as EdgeType;
  const rebuilt = cloneDeep(leaf.data.node!);
  Object.assign(rebuilt.template.input_value, {
    type: "other",
    _input_type: "HandleInput",
    input_types: inputTypes,
  });
  const { result, getNodes } = setup([source, wrapper]);

  act(() =>
    result.current([
      { nodeId: "leaf", newNode: rebuilt, name: "code", code: "new code" },
    ]),
  );

  expect(getNodes()[1].data.node!.template[exposed].type).toBe("other");
  expect(getNodes()[1].data.node!.template[exposed].value).toBe(
    "saved message",
  );
  return { nodes: getNodes(), edge, exposed, proxy };
}
