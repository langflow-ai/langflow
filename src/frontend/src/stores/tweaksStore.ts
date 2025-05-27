import { getChangesType } from "@/modals/apiModal/utils/get-changes-types";
import { getNodesWithDefaultValue } from "@/modals/apiModal/utils/get-nodes-with-default-value";
import { AllNodeType, NodeDataType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";
import { create } from "zustand";
import { TweaksStoreType } from "../types/zustand/tweaks";
import useFlowStore from "./flowStore";

export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
  tweaks: {},
  nodes: [],
  setNodes: (change) => {
    let newChange = typeof change === "function" ? change(get().nodes) : change;

    set({
      nodes: newChange,
    });
    get().updateTweaks();
  },
  setNode: (id, change) => {
    let newChange =
      typeof change === "function"
        ? change(get().nodes.find((node) => node.id === id)!)
        : change;
    get().setNodes((oldNodes) =>
      oldNodes.map((node) => {
        if (node.id === id) {
          if ((node.data as NodeDataType).node?.frozen) {
            (newChange.data as NodeDataType).node!.frozen = false;
          }
          return newChange;
        }
        return node;
      }),
    );
  },
  getNode: (id: string) => {
    return get().nodes.find((node) => node.id === id);
  },
  newInitialSetup: (nodes: AllNodeType[]) => {
    useFlowStore.getState().unselectAll();
    set({
      nodes: getNodesWithDefaultValue(nodes),
    });
    get().updateTweaks();
  },
  updateTweaks: () => {
    const nodes = get().nodes;
    const originalNodes = useFlowStore.getState().nodes;
    const tweak = {};
    nodes.forEach((node) => {
      const originalNodeTemplate = originalNodes?.find((n) => n.id === node.id)
        ?.data?.node?.template;
      const nodeTemplate = node.data?.node?.template;
      if (originalNodeTemplate && nodeTemplate && node.type === "genericNode") {
        const currentTweak = {};
        Object.keys(nodeTemplate).forEach((name) => {
          if (
            customStringify(nodeTemplate[name]) !==
            customStringify(originalNodeTemplate[name])
          ) {
            currentTweak[name] = getChangesType(
              nodeTemplate[name].value,
              nodeTemplate[name],
            );
          }
        });
        if (Object.keys(currentTweak).length > 0) {
          tweak[node.id] = currentTweak;
        }
      }
    });
    set({
      tweaks: tweak,
    });
  },
}));
