import { cloneDeep } from "lodash";
import type { AllNodeType } from "@/types/flow";
import { LANGFLOW_SUPPORTED_TYPES } from "../../../constants/constants";

export const getNodesWithDefaultValue = (
  nodes: AllNodeType[],
  oldTweaks: {
    [key: string]: {
      [key: string]: any;
    };
  },
) => {
  const filteredNodes: AllNodeType[] = [];

  nodes.forEach((node) => {
    if (node?.data?.node?.template && node?.type === "genericNode") {
      const templateKeys = Object.keys(node.data.node.template).filter(
        (templateField) =>
          templateField.charAt(0) !== "_" &&
          node!.data!.node!.template[templateField]?.show &&
          LANGFLOW_SUPPORTED_TYPES.has(
            node!.data!.node!.template[templateField].type,
          ) &&
          templateField !== "code",
      );
      const newNode = cloneDeep(node);
      if (newNode?.data?.node?.template) {
        newNode.data.node.template = templateKeys.reduce((acc, key) => {
          acc[key] = cloneDeep(node?.data?.node?.template[key]);
          acc[key].advanced =
            node.id in oldTweaks && key in oldTweaks[node.id] ? false : true;
          return acc;
        }, {});
      }
      filteredNodes.push(newNode);
    }
  });
  return filteredNodes;
};
