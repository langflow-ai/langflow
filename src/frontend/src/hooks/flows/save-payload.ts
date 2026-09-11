import type { ReactFlowJsonObject } from "@xyflow/react";
import type { AllNodeType, EdgeType, FlowType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";

type PayloadInput = {
  flow: FlowType;
  /** The last response the client applied; the baseline the next save diffs against. */
  persisted: FlowType | undefined;
  flows: FlowType[] | undefined;
  /** The graph on the canvas right now, or undefined off the flow page. */
  live: { nodes: unknown[]; edges: unknown[] } | undefined;
  /** Whether the person has edited this flow since it was loaded. */
  userEdited: boolean;
};

export type FlowUpdatePayload = {
  id: string;
  name?: string;
  description?: string;
  folder_id?: string | null;
  endpoint_name?: string | null;
  locked?: boolean | null;
  data?: ReactFlowJsonObject<AllNodeType, EdgeType>;
  versionToken: string | null;
  providerScopeChanged?: true;
};

/** Canvas state that belongs to the person looking, not to the flow. */
const UI_ONLY_NODE_KEYS = ["selected", "dragging", "resizing"] as const;

const withoutUiState = (items: unknown[]) =>
  items.map((item) => {
    if (item === null || typeof item !== "object") return item;
    const rest = { ...(item as Record<string, unknown>) };
    for (const key of UI_ONLY_NODE_KEYS) delete rest[key];
    return rest;
  });

/**
 * The parts of a graph two people can disagree about.
 *
 * Neither panning nor clicking a node is an edit, and comparing them made both
 * into one: selecting a node sent the whole graph, took the writer's turn, and
 * refused everyone else's save for a change nobody had made.
 */
const graphOf = (data: FlowType["data"]) => ({
  nodes: withoutUiState(data?.nodes ?? []),
  edges: withoutUiState(data?.edges ?? []),
});

/**
 * What a save actually sends.
 *
 * The graph is left out when it matches the version this client last applied.
 * Renaming a flow used to ship the whole canvas with it, so a rename made while
 * somebody else had moved the flow on was read by the server as a competing graph
 * write and refused — and the rename was then dropped in silence. A save that
 * changes no graph also sends no precondition: it is not taking the writer's turn,
 * so there is nothing for it to be refused against.
 */
export const buildFlowUpdatePayload = ({
  flow,
  persisted,
  flows,
  live,
  userEdited,
}: PayloadInput): FlowUpdatePayload => {
  const { id, name, data, description, folder_id, endpoint_name, locked } =
    flow;

  const asText = (graph: unknown) => customStringify(graph);
  const payloadGraph = asText(graphOf(data));

  const hasBaseline = persisted?.id === id && persisted?.data !== undefined;
  // A caller handing over a graph the canvas does not have — applying a template,
  // say — is writing that graph deliberately, whatever the person has touched.
  const writesItsOwnGraph =
    live !== undefined &&
    payloadGraph !==
      asText(
        graphOf({ nodes: live.nodes, edges: live.edges } as FlowType["data"]),
      );
  // Otherwise only the person's own edits travel. Opening a flow rewrites nodes
  // on its way in (component refreshes, model inputs), so comparing against the
  // baseline alone called a plain rename a graph write and had it refused.
  const graphChanged =
    !hasBaseline ||
    writesItsOwnGraph ||
    (userEdited && payloadGraph !== asText(graphOf(persisted?.data)));

  const persistedForScope =
    persisted?.id === id
      ? persisted
      : flows?.find((savedFlow) => savedFlow.id === id);
  const providerScopeChanged =
    persistedForScope !== undefined &&
    persistedForScope.folder_id !== folder_id;

  return {
    id,
    name,
    description,
    folder_id,
    endpoint_name,
    locked,
    ...(graphChanged && {
      data: data as ReactFlowJsonObject<AllNodeType, EdgeType>,
    }),
    versionToken: graphChanged ? (persisted?.version_token ?? null) : null,
    ...(providerScopeChanged && { providerScopeChanged: true as const }),
  };
};
