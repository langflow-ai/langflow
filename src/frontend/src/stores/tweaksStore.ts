import { getChangesType } from "@/modals/apiModal/utils/get-changes-types";
import { getNodesWithDefaultValue } from "@/modals/apiModal/utils/get-nodes-with-default-value";
import { createTabsArray } from "@/modals/apiModal/utils/tabs-array";
import { AllNodeType, FlowType, NodeDataType } from "@/types/flow";
import { GetCodesType } from "@/types/tweaks";
import { customStringify } from "@/utils/reactflowUtils";
import { create } from "zustand";
import { TweaksStoreType } from "../types/zustand/tweaks";
import useFlowStore from "./flowStore";

export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
  activeTweaks: false,
  tweaks: {},
  setActiveTweaks: (activeTweaks: boolean) => {
    set({ activeTweaks }), get().refreshTabs();
  },
  nodes: [],
  setNodes: (change) => {
    let newChange = typeof change === "function" ? change(get().nodes) : change;

    set({
      nodes: newChange,
    });
    get().refreshTabs();
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
  autoLogin: false,
  flow: null,
  getCodes: {},
  initialSetup: (
    autoLogin: boolean,
    flow: FlowType,
    getCodes: GetCodesType,
  ) => {
    useFlowStore.getState().unselectAll();
    set({
      nodes: getNodesWithDefaultValue(flow?.data?.nodes ?? []),
      autoLogin,
      flow,
      getCodes,
    });
    get().refreshTabs();
  },
  newInitialSetup: (nodes: AllNodeType[]) => {
    useFlowStore.getState().unselectAll();
    set({
      nodes: getNodesWithDefaultValue(nodes),
    });
    get().updateTweaks();
  },
  tabs: [],
  refreshTabs: () => {
    const autoLogin = get().autoLogin;
    const flow = get().flow;
    const tweak = {};
    const nodes = get().nodes;
    const originalNodes = flow?.data?.nodes;
    if (!flow) return;

    nodes.forEach((node) => {
      const originalNodeTemplate = originalNodes?.find((n) => n.id === node.id)
        ?.data?.node?.template;
      const nodeTemplate = node.data?.node?.template;
      if (originalNodeTemplate && nodeTemplate && node.type === "genericNode") {
        const currentTweak = {};
        Object.keys(nodeTemplate).forEach((name) => {
          if (
            customStringify(nodeTemplate[name]) !==
              customStringify(originalNodeTemplate[name]) ||
            get().activeTweaks
          ) {
            currentTweak[name] = getChangesType(
              nodeTemplate[name].value,
              nodeTemplate[name],
            );
          }
        });
        tweak[node.id] = currentTweak;
      }
    });
    const codesObj = {};
    const getCodes = get().getCodes;

    const props = {
      flowId: flow?.id,
      flowName: flow?.name,
      isAuth: autoLogin,
      tweaksBuildedObject: tweak,
      endpointName: flow?.endpoint_name,
      activeTweaks: get().activeTweaks,
    };

    if (getCodes) {
      if (getCodes.getCurlRunCode) {
        codesObj["runCurlCode"] = getCodes.getCurlRunCode(props);
      }
      if (getCodes.getCurlWebhookCode && !!flow.webhook) {
        codesObj["webhookCurlCode"] = getCodes.getCurlWebhookCode(props);
      }
      if (getCodes.getJsApiCode) {
        codesObj["jsApiCode"] = getCodes.getJsApiCode(props);
      }
      if (getCodes.getPythonApiCode) {
        codesObj["pythonApiCode"] = getCodes.getPythonApiCode(props);
      }
      if (getCodes.getPythonCode) {
        codesObj["pythonCode"] = getCodes.getPythonCode(props);
      }
      if (getCodes.getWidgetCode) {
        codesObj["widgetCode"] = getCodes.getWidgetCode(props);
      }
    }

    set({
      tabs: createTabsArray(codesObj, nodes.length > 0),
    });
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
