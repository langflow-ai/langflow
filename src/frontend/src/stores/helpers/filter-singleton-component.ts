import type { Node } from "@xyflow/react";
import type { EdgeType } from "../../types/flow";
import useAlertStore from "../alertStore";

export function filterSingletonComponent(
  selection: { nodes: Node[]; edges: EdgeType[] },
  componentType: string,
  existsInFlow: boolean,
  noticeMessage: string,
): void {
  if (
    !selection.nodes.some((node) => node.data.type === componentType) ||
    !existsInFlow
  ) {
    return;
  }

  useAlertStore.getState().setNoticeData({ title: noticeMessage });
  selection.nodes = selection.nodes.filter(
    (node) => node.data.type !== componentType,
  );
  selection.edges = selection.edges.filter(
    (edge) =>
      selection.nodes.some((node) => edge.source === node.id) &&
      selection.nodes.some((node) => edge.target === node.id),
  );
}
