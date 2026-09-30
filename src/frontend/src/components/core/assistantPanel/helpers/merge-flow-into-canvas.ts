/**
 * Merge a flow proposal into the existing canvas state additively.
 *
 * The default "Continue on flow proposal" semantic is destructive: it
 * calls `setNodes(proposal.nodes) + setEdges(proposal.edges)`, replacing
 * everything on the canvas. That's correct when the user explicitly
 * wants to build from scratch on an empty canvas, but hostile when the
 * canvas already has work the user values.
 *
 * This helper produces the additive alternative:
 *
 *   1. Detect ID collisions between proposal nodes and existing nodes;
 *      rename the proposal-side colliders by appending a fresh suffix.
 *      The component-type prefix (e.g. ``ChatInput-``) is preserved so
 *      the renamed id still parses by downstream code that splits on
 *      ``-`` to identify component types.
 *   2. Rewrite proposal edges so their ``source`` and ``target`` track
 *      the remapped node ids. Edge ids that collide with existing
 *      canvas edges are also re-suffixed.
 *   3. Offset proposal node positions so they don't overlap the
 *      existing canvas — placed to the RIGHT of the existing bounding
 *      box with a fixed gap. Relative spacing inside the proposal is
 *      preserved.
 *
 * The function is pure (no React, no @xyflow state) — suitable for unit
 * tests and predictable use from any caller.
 */

const POSITION_GAP_PX = 80;
const ID_SUFFIX_ENTROPY = 6; // ~36^6 ≈ 2 billion combinations; collision-resistant for any realistic canvas

interface CanvasNode {
  id: string;
  position: { x: number; y: number };
  [key: string]: unknown;
}

interface CanvasEdge {
  id: string;
  source: string;
  target: string;
  [key: string]: unknown;
}

interface FlowProposal {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export interface MergeResult {
  nodes: CanvasNode[];
  edges: CanvasEdge[];
}

export function mergeFlowIntoCanvas(
  existingNodes: CanvasNode[],
  existingEdges: CanvasEdge[],
  proposal: FlowProposal,
): MergeResult {
  // Empty canvas → return the proposal as-is; no offset, no remap.
  if (existingNodes.length === 0) {
    return {
      nodes: proposal.nodes,
      edges: proposal.edges,
    };
  }

  // 1. ID remap pass — build a map old→new for any colliding node id.
  const existingNodeIds = new Set(existingNodes.map((n) => n.id));
  const existingEdgeIds = new Set(existingEdges.map((e) => e.id));
  const nodeIdRemap = new Map<string, string>();
  for (const node of proposal.nodes) {
    if (existingNodeIds.has(node.id)) {
      nodeIdRemap.set(node.id, _generateUniqueNodeId(node.id, existingNodeIds));
    }
  }

  // 2. Bounding-box offset — push the proposal to the right of the canvas.
  const offset = _computeRightOffset(existingNodes, proposal.nodes);

  // 3. Rewrite proposal nodes — apply remap and offset.
  const newNodes: CanvasNode[] = proposal.nodes.map((node) => ({
    ...node,
    id: nodeIdRemap.get(node.id) ?? node.id,
    position: {
      x: node.position.x + offset.dx,
      y: node.position.y + offset.dy,
    },
  }));

  // 4. Rewrite proposal edges — apply both the node-id remap and the
  //    edge-id remap (when the edge id itself collides).
  const newEdges: CanvasEdge[] = proposal.edges.map((edge) => ({
    ...edge,
    id: existingEdgeIds.has(edge.id)
      ? _generateUniqueEdgeId(edge.id, existingEdgeIds)
      : edge.id,
    source: nodeIdRemap.get(edge.source) ?? edge.source,
    target: nodeIdRemap.get(edge.target) ?? edge.target,
  }));

  return {
    nodes: [...existingNodes, ...newNodes],
    edges: [...existingEdges, ...newEdges],
  };
}

// ---------------------------------------------------------------------------
// internals
// ---------------------------------------------------------------------------

function _generateUniqueNodeId(
  collidingId: string,
  taken: Set<string>,
): string {
  // Component type lives before the first '-'. Preserve it so downstream
  // code that splits on '-' to read the type keeps working.
  const dashAt = collidingId.indexOf("-");
  const prefix = dashAt === -1 ? collidingId : collidingId.slice(0, dashAt);
  let candidate = "";
  do {
    candidate = `${prefix}-${_randomSuffix()}`;
  } while (taken.has(candidate));
  taken.add(candidate);
  return candidate;
}

function _generateUniqueEdgeId(
  collidingId: string,
  taken: Set<string>,
): string {
  let candidate = "";
  do {
    candidate = `${collidingId}-${_randomSuffix()}`;
  } while (taken.has(candidate));
  taken.add(candidate);
  return candidate;
}

function _randomSuffix(): string {
  // Base-36 random suffix. Deterministic-shape, collision-resistant at
  // the scales we care about (< 10k nodes per canvas).
  let s = "";
  for (let i = 0; i < ID_SUFFIX_ENTROPY; i++) {
    s += Math.floor(Math.random() * 36).toString(36);
  }
  return s;
}

function _computeRightOffset(
  existing: CanvasNode[],
  proposal: CanvasNode[],
): { dx: number; dy: number } {
  if (proposal.length === 0) return { dx: 0, dy: 0 };

  const existingRightEdge = Math.max(...existing.map((n) => n.position.x));
  const proposalLeftEdge = Math.min(...proposal.map((n) => n.position.x));

  // Place the proposal's leftmost node at existing_right_edge + GAP.
  // Negative deltas (proposal already to the right) collapse to GAP to
  // keep behavior predictable.
  const dx = existingRightEdge - proposalLeftEdge + POSITION_GAP_PX;

  // Vertical: keep the proposal's relative y intact — the user can
  // re-arrange. A perfect top-alignment would require careful bbox math
  // for node sizes we don't have access to here.
  return { dx, dy: 0 };
}
