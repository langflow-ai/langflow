import { getChangesType } from "@/modals/apiModal/utils/get-changes-types";
import {
  getCurlRunCode,
  getCurlWebhookCode,
} from "@/modals/apiModal/utils/get-curl-code";
import getJsApiCode from "@/modals/apiModal/utils/get-js-api-code";
import { getNodesWithDefaultValue } from "@/modals/apiModal/utils/get-nodes-with-default-value";
import getPythonApiCode from "@/modals/apiModal/utils/get-python-api-code";
import getPythonCode from "@/modals/apiModal/utils/get-python-code";
import getWidgetCode from "@/modals/apiModal/utils/get-widget-code";
import { createTabsArray } from "@/modals/apiModal/utils/tabs-array";
import { FlowType, NodeDataType } from "@/types/flow";
import { customStringify } from "@/utils/reactflowUtils";
import { create } from "zustand";
import { TweaksStoreType } from "../types/zustand/tweaks";
import useFlowStore from "./flowStore";

export const useTweaksStore = create<TweaksStoreType>((set, get) => ({
  activeTweaks: false,
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
  initialSetup: (autoLogin: boolean, flow: FlowType) => {
    useFlowStore.getState().unselectAll();
    set({
      nodes: getNodesWithDefaultValue(flow?.data?.nodes ?? []),
      autoLogin,
      flow,
    });
    get().refreshTabs();
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
      if (originalNodeTemplate && nodeTemplate) {
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

    const pythonApiCode = getPythonApiCode(flow?.id, autoLogin, tweak);
    const runCurlCode = getCurlRunCode(
      flow?.id,
      autoLogin,
      tweak,
      flow?.endpoint_name,
    );
    const jsApiCode = getJsApiCode(
      flow?.id,
      autoLogin,
      tweak,
      flow?.endpoint_name,
    );
    const webhookCurlCode = getCurlWebhookCode(
      flow?.id,
      autoLogin,
      flow?.endpoint_name,
    );
    const pythonCode = getPythonCode(flow?.name, tweak);
    const widgetCode = getWidgetCode(flow?.id, flow?.name, autoLogin);

    const codesArray = [
      runCurlCode,
      webhookCurlCode,
      pythonApiCode,
      jsApiCode,
      pythonCode,
      widgetCode,
    ];
    set({
      tabs: createTabsArray(codesArray, !!flow.webhook, nodes.length > 0),
    });
  },
}));
