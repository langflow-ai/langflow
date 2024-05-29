import { FlowType } from "../../../types/flow";

export function buildTweaks(flow: FlowType) {
  return flow.data!.nodes.reduce((acc, node) => {
    acc[node.data.id] = {};
    return acc;
  }, {});
}
