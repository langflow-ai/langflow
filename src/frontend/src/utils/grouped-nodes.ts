import { cloneDeep } from "lodash";
import type { InputFieldType } from "@/types/api";
import type {
  AllNodeType,
  EdgeType,
  GenericNodeType,
  targetHandleType,
} from "@/types/flow";

export type FlowNodeContext = {
  node: AllNodeType;
  edges: EdgeType[] | undefined;
  ancestors: GenericNodeType[];
};

function targetHandle(edge: EdgeType): Partial<targetHandleType> | undefined {
  if (edge.data?.targetHandle) return edge.data.targetHandle;
  if (!edge.targetHandle) return undefined;
  try {
    return JSON.parse(edge.targetHandle.replaceAll("œ", '"'));
  } catch {
    const parts = edge.targetHandle.split("|");
    return parts.length >= 3 ? { fieldName: parts[1] } : undefined;
  }
}

/** Walk saved groups with the same connections their child nodes receive. */
export function* walkFlowNodes(
  nodes: AllNodeType[],
  edges?: EdgeType[],
  ancestors: GenericNodeType[] = [],
): Generator<FlowNodeContext> {
  edges = edges?.map((edge) => {
    const handle = targetHandle(edge);
    return edge.data?.targetHandle || !handle
      ? edge
      : {
          ...edge,
          data: { ...edge.data, targetHandle: handle } as EdgeType["data"],
        };
  });
  for (const node of nodes) {
    yield { node, edges, ancestors };
    if (node.type !== "genericNode") continue;
    const nested = node.data.node?.flow?.data;
    if (!nested?.nodes) continue;

    let nestedEdges: EdgeType[] | undefined;
    if (edges !== undefined && Array.isArray(nested.edges)) {
      nestedEdges = [...nested.edges];
      for (const edge of edges) {
        if (edge.target !== node.id) continue;
        const handle = targetHandle(edge);
        const proxy =
          handle?.proxy ??
          node.data.node?.template[handle?.fieldName ?? ""]?.proxy;
        if (!proxy) continue;
        nestedEdges.push({
          ...edge,
          target: proxy.id,
          data: {
            ...edge.data,
            targetHandle: {
              ...handle,
              id: proxy.id,
              fieldName: proxy.field,
              // The next group resolves its own proxy from its template.
              proxy: undefined,
            } as targetHandleType,
          } as EdgeType["data"],
        });
      }
    }
    yield* walkFlowNodes(nested.nodes, nestedEdges, [...ancestors, node]);
  }
}

const SAVED_FIELD_PROPERTIES = ["value", "load_from_db", "file_path"] as const;

export function copySavedFieldValues(
  source: InputFieldType,
  target: InputFieldType,
): void {
  for (const key of SAVED_FIELD_PROPERTIES) {
    if (Object.hasOwn(source, key)) target[key] = cloneDeep(source[key]);
  }
}

/** Group inputs are authoritative at execution time, even if the child is stale. */
export function nodeWithGroupValues({
  node,
  ancestors,
}: FlowNodeContext): AllNodeType {
  if (!ancestors.length || node.type !== "genericNode") return node;
  const result = cloneDeep(node);
  const template = result.data.node?.template;
  if (!template) return result;
  let childId = node.id;
  let fields = new Map(Object.keys(template).map((name) => [name, name]));
  for (const group of [...ancestors].reverse()) {
    const parentFields = new Map<string, string>();
    for (const [name, field] of Object.entries(group.data.node!.template)) {
      if (field?.proxy?.id !== childId) continue;
      const leafName = fields.get(field.proxy.field);
      if (!leafName || !template[leafName]) continue;
      copySavedFieldValues(field, template[leafName]);
      parentFields.set(name, leafName);
    }
    childId = group.id;
    fields = parentFields;
  }
  return result;
}

export function countFlowEdges(
  nodes: AllNodeType[],
  edges: EdgeType[],
): number {
  let count = edges.length;
  for (const { node } of walkFlowNodes(nodes)) {
    if (node.type === "genericNode") {
      count += node.data.node?.flow?.data?.edges?.length ?? 0;
    }
  }
  return count;
}
