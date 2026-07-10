/**
 * Regression guard for the assistant "Add to canvas" apply path.
 *
 * A loop flow built by lfx's `build_flow_from_spec` must survive `cleanEdges`
 * (the survival gate run by resetFlow/setNodes on apply) with EVERY edge
 * intact — group-output sources (Loop item/done), the item dual-role
 * output+loop-target, and dynamic TypeConverter outputs alike. The fixtures
 * are the exact JSON produced by the builder for the canonical 5-node recipe
 * and the 4-node no-ChatInput variant from the manual bug report.
 */

import type { AllNodeType, EdgeType } from "@/types/flow";
import { cleanEdges } from "../reactflowUtils";
import canonicalLoop from "./fixtures/canonical_loop.json";
import generatedComponentLoop from "./fixtures/generated_component_loop.json";
import variantLoop from "./fixtures/variant_loop.json";

interface BuiltFlow {
  data: { nodes: AllNodeType[]; edges: EdgeType[] };
}

const cases: Array<[string, BuiltFlow]> = [
  [
    "canonical 5-node loop (ChatInput -> Loop -> Parser -> TypeConverter loop, Loop.done -> ChatOutput)",
    canonicalLoop as unknown as BuiltFlow,
  ],
  ["4-node no-ChatInput loop variant", variantLoop as unknown as BuiltFlow],
  [
    "generated-component loop tail (data.type=CustomComponent, class-named id)",
    generatedComponentLoop as unknown as BuiltFlow,
  ],
];

describe("loop flow survives the apply/cleanEdges path", () => {
  it.each(cases)("keeps every built edge for the %s", (_label, flow) => {
    const nodes = flow.data.nodes;
    const edges = flow.data.edges;

    const { edges: survived, brokenEdges } = cleanEdges(nodes, edges);

    expect(brokenEdges).toEqual([]);
    expect(survived).toHaveLength(edges.length);
  });
});
