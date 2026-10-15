/**
 * The rules an edge follows when a write adds it or changes its handles: the
 * editor's copy of the engine's `lfx.services.flow_operations.edge_rules`.
 *
 * An edge connects one output of its source node to one input of its target
 * node, and its handles name them: `sourceHandle.name` is an output of the
 * source, and `targetHandle.fieldName` is a template field of the target. A
 * loop feedback edge instead names an output of its target, with
 * `targetHandle.name`, and that output must declare `allows_loop`.
 *
 * Every edge carries each handle twice: as an object under `data`, and as an
 * escaped JSON string (`œ` stands for `"`). Both forms must be present and
 * agree. Nothing is exempt: group nodes are checked like any node, and an edge
 * may not touch a note, which has no handles.
 */

import { cloneDeep } from "lodash";
import { parseHandle, valuesEqual } from "./canonical";
import { invalidGraph, invalidOperation } from "./errors";
import type { ListIndex } from "./keyed-lists";
import { keyedListAt } from "./schema";
import type { GraphState } from "./state";

type JsonObject = Record<string, unknown>;

export const HANDLE_KEYS = ["sourceHandle", "targetHandle"] as const;
const NOTE_NODE_TYPE = "noteNode";
export const OUTPUTS_PATH = ["data", "node", "outputs"];

/** The input an edge connects at its target: a template field, or a loop output. */
export type Input = { kind: "field" | "output"; name: string };

/** The output an edge leaves from and the input it enters. */
export type Handles = { output: string; input: Input };

/** A key for an input in a node's connections. */
export function inputKey(input: Input): string {
  return `${input.kind}:${input.name}`;
}

/** A node's edges, by the input they enter and the output they leave from. */
export type Connections = {
  inputs: Map<string, Set<string>>;
  outputs: Map<string, Set<string>>;
};

function isObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function edgeError(edge: JsonObject, code: string, reason: string) {
  return invalidOperation(`edge ${String(edge.id)}: ${reason}`, code);
}

/** Read an edge's handles strictly: both forms present, the string parsing to the object. */
export function readHandles(edge: JsonObject): Handles {
  const source = handle(edge, "sourceHandle");
  const target = handle(edge, "targetHandle");
  const output = source.name;
  if (typeof output !== "string" || !output)
    throw edgeError(
      edge,
      "EDGE_HANDLE_INVALID",
      "sourceHandle must name an output",
    );
  const fieldName = target.fieldName;
  const loopOutput = target.name;
  if ((fieldName === undefined) === (loopOutput === undefined))
    throw edgeError(
      edge,
      "EDGE_HANDLE_INVALID",
      "targetHandle must name exactly one of a field or an output",
    );
  const name = fieldName !== undefined ? fieldName : loopOutput;
  if (typeof name !== "string" || !name)
    throw edgeError(
      edge,
      "EDGE_HANDLE_INVALID",
      "targetHandle must name its field or output as a string",
    );
  return {
    output,
    input: { kind: fieldName !== undefined ? "field" : "output", name },
  };
}

function handle(edge: JsonObject, key: string): JsonObject {
  const data = edge.data;
  // `data: null` holds no handle objects, as if it were missing (ops-history, "Repair").
  if (data !== undefined && data !== null && !isObject(data))
    throw edgeError(edge, "EDGE_HANDLE_INVALID", "data must be an object");
  const hasObject = isObject(data) && key in data;
  const hasString = key in edge;
  if (hasObject && !isObject(data[key]))
    throw edgeError(
      edge,
      "EDGE_HANDLE_INVALID",
      `data.${key} must be an object`,
    );
  if (hasString) {
    const parsed = parseHandle(edge[key]);
    if (!parsed)
      throw edgeError(
        edge,
        "EDGE_HANDLE_INVALID",
        `${key} must be an escaped JSON object`,
      );
    if (hasObject && !valuesEqual(parsed, data[key]))
      throw edgeError(
        edge,
        "EDGE_HANDLE_INVALID",
        `${key} and data.${key} name different handles`,
      );
  }
  if (hasObject && hasString) return data[key] as JsonObject;
  if (hasObject || hasString)
    throw edgeError(
      edge,
      "EDGE_HANDLE_FORM_MISSING",
      `${hasObject ? key : `data.${key}`} is missing`,
    );
  throw edgeError(edge, "EDGE_HANDLE_INVALID", `edge has no ${key}`);
}

/** A copy of both forms of an edge's handles, whatever their shape, to tell whether a write changed them. */
export function handleForms(edge: JsonObject): JsonObject {
  const data = edge.data;
  const strings: JsonObject = {};
  for (const key of HANDLE_KEYS) if (key in edge) strings[key] = edge[key];
  let objects: unknown = data;
  if (isObject(data)) {
    const picked: JsonObject = {};
    for (const key of HANDLE_KEYS) if (key in data) picked[key] = data[key];
    objects = picked;
  }
  return cloneDeep({ strings, data: objects }) as JsonObject;
}

/**
 * Check an edge a write adds or rewires, and return its handles. The edge
 * must not touch a note, its handles must be valid and name an output of its
 * source and an input of its target, and a single input must not be taken by
 * another edge.
 */
export function checkEdge(state: GraphState, edge: JsonObject): Handles {
  for (const end of ["source", "target"] as const) {
    if (state.nodes.get(edge[end] as string)!.type === NOTE_NODE_TYPE)
      throw edgeError(
        edge,
        "EDGE_TOUCHES_NOTE",
        `its ${end} ${String(edge[end])} is a note, which has no handles`,
      );
  }
  const handles = state.handles(edge);

  const sourceId = edge.source as string;
  const sourceOutputs = nodeOutputs(state, sourceId);
  if (!sourceOutputs?.slots.has(handles.output))
    throw edgeError(
      edge,
      "EDGE_HANDLE_NOT_FOUND",
      `source node ${sourceId} has no output ${handles.output}`,
    );

  const targetId = edge.target as string;
  const { kind, name } = handles.input;
  let single = true;
  if (kind === "field") {
    const template = nodeBody(state, targetId).template as JsonObject;
    const targetField = template[name];
    if (!isObject(targetField))
      throw edgeError(
        edge,
        "EDGE_HANDLE_NOT_FOUND",
        `target node ${targetId} has no field ${name}`,
      );
    single = targetField.list !== true;
  } else {
    const targetOutputs = nodeOutputs(state, targetId);
    const slot = targetOutputs?.slots.get(name);
    const loopOutput =
      slot === undefined
        ? undefined
        : (targetOutputs!.items[slot] as JsonObject);
    if (!loopOutput || loopOutput.allows_loop !== true)
      throw edgeError(
        edge,
        "EDGE_HANDLE_NOT_FOUND",
        `target node ${targetId} has no loop output ${name}`,
      );
  }

  if (single) {
    const others = [
      ...(state.connections(targetId).inputs.get(inputKey(handles.input)) ??
        []),
    ].filter((id) => id !== edge.id);
    if (others.length > 0)
      throw edgeError(
        edge,
        "EDGE_TARGET_OCCUPIED",
        `${kind} ${name} of node ${targetId} takes one connection and already has ${others.sort()[0]}`,
      );
  }
  return handles;
}

/** A node's `data.node`. Validation and `add_nodes` keep it, and its template, an object. */
export function nodeBody(state: GraphState, nodeId: string): JsonObject {
  return (state.nodes.get(nodeId)!.data as JsonObject).node as JsonObject;
}

/** The index of a node's outputs, or null for a node without an `outputs` key. */
export function nodeOutputs(
  state: GraphState,
  nodeId: string,
): ListIndex | null {
  const body = nodeBody(state, nodeId);
  if (!("outputs" in body)) return null;
  const outputs = body.outputs;
  if (!Array.isArray(outputs))
    throw invalidGraph(`node ${nodeId}: data.node.outputs must be a list`);
  const list = keyedListAt(state.nodes.get(nodeId), OUTPUTS_PATH)!;
  return state.listIndex(list, outputs, `node ${nodeId}: data.node.outputs`);
}
