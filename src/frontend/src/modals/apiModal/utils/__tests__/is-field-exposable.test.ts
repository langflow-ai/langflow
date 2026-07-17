import type { AllNodeType, EdgeType } from "@/types/flow";
import { scapedJSONStringfy } from "@/utils/reactflowUtils";
import { getNodesWithDefaultValue } from "../get-nodes-with-default-value";
import { isFieldExposable } from "../is-field-exposable";

const makeNode = (
  template: Record<string, unknown>,
  overrides: Partial<{ toolMode: boolean; id: string }> = {},
): AllNodeType =>
  ({
    id: overrides.id ?? "node-1",
    type: "genericNode",
    position: { x: 0, y: 0 },
    data: {
      id: overrides.id ?? "node-1",
      type: "TestNode",
      node: {
        template,
        tool_mode: overrides.toolMode ?? false,
      },
    },
  }) as AllNodeType;

const edgeInto = (nodeId: string, fieldName: string): EdgeType =>
  ({
    id: `edge-${fieldName}`,
    source: "other-node",
    target: nodeId,
    sourceHandle: scapedJSONStringfy({
      dataType: "Other",
      id: "other-node",
      name: "output",
      output_types: ["Message"],
    }),
    targetHandle: scapedJSONStringfy({
      fieldName,
      id: nodeId,
      inputTypes: ["Message"],
      type: "str",
    }),
  }) as EdgeType;

const exposedField = {
  show: true,
  type: "str",
  value: "v",
  advanced: false,
  api_editable: true,
};

describe("isFieldExposable (LE-1810 single exposure predicate)", () => {
  it("exposes an on-node, unconnected field flagged api_editable", () => {
    const node = makeNode({ param: { ...exposedField } });
    expect(isFieldExposable(node, "param", [])).toBe(true);
  });

  it("does not expose when api_editable is false or absent", () => {
    const node = makeNode({
      off: { ...exposedField, api_editable: false },
      missing: { show: true, type: "str", value: "v", advanced: false },
    });
    expect(isFieldExposable(node, "off", [])).toBe(false);
    expect(isFieldExposable(node, "missing", [])).toBe(false);
  });

  it("does not expose an off-node (advanced) field even when flagged", () => {
    const node = makeNode({
      param: { ...exposedField, advanced: true },
    });
    expect(isFieldExposable(node, "param", [])).toBe(false);
  });

  it("does not expose a field whose handle is edge-connected", () => {
    const node = makeNode({ param: { ...exposedField } });
    const edges = [edgeInto("node-1", "param")];
    expect(isFieldExposable(node, "param", edges)).toBe(false);
  });

  it("ignores edges targeting other nodes or other fields", () => {
    const node = makeNode({ param: { ...exposedField } });
    const edges = [edgeInto("node-2", "param"), edgeInto("node-1", "other")];
    expect(isFieldExposable(node, "param", edges)).toBe(true);
  });

  it("does not expose a tool-mode-disabled field", () => {
    const node = makeNode(
      { param: { ...exposedField, tool_mode: true } },
      { toolMode: true },
    );
    expect(isFieldExposable(node, "param", [])).toBe(false);
  });

  it("keeps exposing a tool_mode-capable field while tool mode is off", () => {
    const node = makeNode(
      { param: { ...exposedField, tool_mode: true } },
      { toolMode: false },
    );
    expect(isFieldExposable(node, "param", [])).toBe(true);
  });

  it("never exposes code or internal fields", () => {
    const node = makeNode({
      code: { ...exposedField },
      _internal: { ...exposedField },
    });
    expect(isFieldExposable(node, "code", [])).toBe(false);
    expect(isFieldExposable(node, "_internal", [])).toBe(false);
  });

  it("returns false for a missing template", () => {
    const node = makeNode({});
    expect(isFieldExposable(node, "ghost", [])).toBe(false);
  });
});

describe("getNodesWithDefaultValue exposure copy (LE-1810)", () => {
  it("carries api_editable verbatim for exposable fields", () => {
    const node = makeNode({ param: { ...exposedField } });
    const [copy] = getNodesWithDefaultValue([node], []);
    expect(copy.data.node?.template.param.api_editable).toBe(true);
  });

  it("copies a connected exposed field as NOT exposed without touching the real node", () => {
    const node = makeNode({ param: { ...exposedField } });
    const edges = [edgeInto("node-1", "param")];
    const [copy] = getNodesWithDefaultValue([node], edges);
    expect(copy.data.node?.template.param.api_editable).toBe(false);
    // Non-destructive: the real node keeps its persisted flag.
    expect(node.data.node?.template.param.api_editable).toBe(true);
  });

  it("copies an off-node exposed field as NOT exposed", () => {
    const node = makeNode({
      param: { ...exposedField, advanced: true },
    });
    const [copy] = getNodesWithDefaultValue([node], []);
    expect(copy.data.node?.template.param.api_editable).toBe(false);
  });
});
