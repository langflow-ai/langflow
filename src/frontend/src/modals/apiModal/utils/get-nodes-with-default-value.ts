import { cloneDeep } from "lodash";
import type { AllNodeType, EdgeType } from "@/types/flow";
import { isFieldTweakable } from "./api-exposure-rules";
import { isFieldExposable } from "./is-field-exposable";

export const getNodesWithDefaultValue = (
  nodes: AllNodeType[],
  edges: EdgeType[],
) => {
  const filteredNodes: AllNodeType[] = [];

  nodes.forEach((node) => {
    if (node?.data?.node?.template && node?.type === "genericNode") {
      const templateKeys = Object.keys(node.data.node.template).filter(
        (templateField) =>
          node!.data!.node!.template[templateField]?.show &&
          isFieldTweakable(
            node.data.type,
            templateField,
            node!.data!.node!.template[templateField],
          ),
      );
      const newNode = cloneDeep(node);
      if (newNode?.data?.node?.template) {
        // API exposure is the persisted per-field api_editable flag on the
        // real node (LE-1810) — the tweaks copy carries it verbatim, except
        // that a field failing the exposure predicate (off-node, connected,
        // tool-mode-disabled) is copied as NOT exposed. The real node's flag
        // is never mutated; exposure resumes once the precondition holds.
        newNode.data.node.template = templateKeys.reduce((acc, key) => {
          acc[key] = cloneDeep(node?.data?.node?.template[key]);
          if (
            acc[key].api_editable === true &&
            !isFieldExposable(node, key, edges)
          ) {
            acc[key].api_editable = false;
          }
          return acc;
        }, {});
      }
      filteredNodes.push(newNode);
    }
  });
  return filteredNodes;
};
