import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { ReactNode, forwardRef, useContext, useEffect, useState } from "react";
// import "ace-builds/webpack-resolver";
import { APITemplateType, InputFieldType } from "@/types/api";
import { cloneDeep } from "lodash";
import CodeTabsComponent from "../../components/codeTabsComponent";
import IconComponent from "../../components/genericIconComponent";
import { EXPORT_CODE_DIALOG } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { useTweaksStore } from "../../stores/tweaksStore";
import { uniqueTweakType } from "../../types/components";
import { FlowType, NodeType } from "../../types/flow/index";
import BaseModal from "../baseModal";
import { buildTweaks } from "./utils/build-tweaks";
import { checkCanBuildTweakObject } from "./utils/check-can-build-tweak-object";
import { getChangesType } from "./utils/get-changes-types";
import getCodesObj from "./utils/get-codes-obj";
import { getCurlRunCode, getCurlWebhookCode } from "./utils/get-curl-code";
import getJsApiCode from "./utils/get-js-api-code";
import { getNodesWithDefaultValue } from "./utils/get-nodes-with-default-value";
import getPythonApiCode from "./utils/get-python-api-code";
import getPythonCode from "./utils/get-python-code";
import getTabsOrder from "./utils/get-tabs-order";
import getWidgetCode from "./utils/get-widget-code";
import { createTabsArray } from "./utils/tabs-array";

const ApiModal = forwardRef(
  (
    {
      flow,
      children,
      open: myOpen,
      setOpen: mySetOpen,
    }: {
      flow: FlowType;
      children: ReactNode;
      open?: boolean;
      setOpen?: (a: boolean | ((o?: boolean) => boolean)) => void;
    },
    ref,
  ) => {
    const tweaksCode = buildTweaks(flow);
    const tweak = useTweaksStore((state) => state.tweak);
    const addTweaks = useTweaksStore((state) => state.setTweak);
    const setTweaksList = useTweaksStore((state) => state.setTweaksList);
    const tweaksList = useTweaksStore((state) => state.tweaksList);
    const isThereTweaks = Object.keys(tweaksCode).length > 0;
    const [activeTweaks, setActiveTweaks] = useState(false);
    const { autoLogin } = useContext(AuthContext);
    const [open, setOpen] =
      mySetOpen !== undefined && myOpen !== undefined
        ? [myOpen, mySetOpen]
        : useState(false);
    const [activeTab, setActiveTab] = useState("0");
    const pythonApiCode = getPythonApiCode(
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
    const runCurlCode = getCurlRunCode(
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
    const includeWebhook = flow.webhook;
    const codesArray = [
      runCurlCode,
      webhookCurlCode,
      pythonApiCode,
      jsApiCode,
      pythonCode,
      widgetCode,
    ];
    const [tabs, setTabs] = useState(
      createTabsArray(codesArray, includeWebhook),
    );

    const canShowTweaks =
      flow &&
      flow["data"] &&
      flow["data"]!["nodes"] &&
      tweak &&
      tweak?.length > 0 &&
      activeTweaks === true;

    const buildTweaksInitialState = () => {
      const newTweak: any = [];
      const t = buildTweaks(flow);
      newTweak.push(t);
      addTweaks(newTweak);
      addCodes(newTweak);
    };

    useEffect(() => {
      if (flow["data"]!["nodes"].length == 0) {
        addTweaks([]);
        setTweaksList([]);
      } else {
        buildTweaksInitialState();
      }
      setActiveTab("0");

      filterNodes();
    }, [flow["data"]!["nodes"], open]);

    useEffect(() => {
      setTabs(createTabsArray(codesArray, includeWebhook, isThereTweaks));
    }, [open, isThereTweaks]);

    useEffect(() => {
      if (canShowTweaks) {
        const nodes = flow["data"]!["nodes"];
        nodes.forEach((element) => {
          const nodeId = element["id"];
          const template = element["data"]["node"]["template"];

          Object.keys(template).forEach((templateField) => {
            if (checkCanBuildTweakObject(element, templateField)) {
              buildTweakObject(
                nodeId,
                element.data.node.template[templateField].value,
                element.data.node.template[templateField],
              );
            }
          });
        });
      } else {
        buildTweaksInitialState();
      }
    }, [activeTweaks]);

    const filterNodes = () => {
      setTweaksList(getNodesWithDefaultValue(flow));
    };

    const buildTweaksByChange = (nodes: NodeType[]) => {
      if (!flow || !flow.data || !flow.data.nodes) return;

      flow.data.nodes.forEach((currentNode, index) => {
        Object.entries(currentNode!.data!.node!.template).forEach(
          ([key, template]) => {
            if (
              JSON.stringify((template as APITemplateType).value) !==
              JSON.stringify(nodes[index].data.node!.template[key].value)
            ) {
              buildTweakObject(
                nodes[index].id,
                nodes[index].data.node!.template[key].value,
                nodes[index].data.node!.template[key],
              );
            }
          },
        );
      });
    };

    async function buildTweakObject(
      tw: string,
      changes: string | string[] | boolean | number | Object[] | Object,
      template: InputFieldType,
    ) {
      changes = getChangesType(changes, template);

      const existingTweak = tweak.find((element) => element.hasOwnProperty(tw));

      if (existingTweak) {
        existingTweak[tw][template["name"]!] = changes as string;

        if (existingTweak[tw][template["name"]!] == template.value) {
          tweak.forEach((element) => {
            if (element[tw] && Object.keys(element[tw])?.length === 0) {
              const filteredTweaks = tweak.filter((obj) => {
                const prop = obj[Object.keys(obj)[0]].prop;
                return prop !== undefined && prop !== null && prop !== "";
              });
              addTweaks(filteredTweaks);
            }
          });
        }
      } else {
        const newTweak = {
          [tw]: {
            [template["name"]!]: changes,
          },
        } as uniqueTweakType;
        tweak.push(newTweak);
      }

      if (tweak && tweak.length > 0) {
        const cloneTweak = cloneDeep(tweak);
        addCodes(cloneTweak);
        addTweaks(cloneTweak);
      }
    }

    const addCodes = (cloneTweak) => {
      const pythonApiCode = getPythonApiCode(flow?.id, autoLogin, cloneTweak);
      const runCurlCode = getCurlRunCode(
        flow?.id,
        autoLogin,
        cloneTweak,
        flow?.endpoint_name,
      );
      const jsApiCode = getJsApiCode(
        flow?.id,
        autoLogin,
        cloneTweak,
        flow?.endpoint_name,
      );
      const webhookCurlCode = getCurlWebhookCode(
        flow?.id,
        autoLogin,
        flow?.endpoint_name,
      );
      const pythonCode = getPythonCode(flow?.name, cloneTweak);
      const widgetCode = getWidgetCode(flow?.id, flow?.name, autoLogin);
      const codesObj = getCodesObj({
        runCurlCode,
        webhookCurlCode,
        pythonApiCode,
        jsApiCode,
        pythonCode,
        widgetCode,
      });
      const tabsOrder = getTabsOrder(includeWebhook, isThereTweaks);
      if (tabs && tabs?.length > 0) {
        tabs.forEach((tab, idx) => {
          const order = tabsOrder[idx];
          if (order && order.toLowerCase() === tab.name.toLowerCase()) {
            const codeToFind = codesObj.find(
              (c) => c.name.toLowerCase() === tab.name.toLowerCase(),
            );
            tab.code = codeToFind?.code;
          }
        });
      }
    };

    return (
      <BaseModal open={open} setOpen={setOpen}>
        <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
        <BaseModal.Header description={EXPORT_CODE_DIALOG}>
          <span className="pr-2">API</span>
          <IconComponent
            name="Code2"
            className="h-6 w-6 pl-1 text-gray-800 dark:text-white"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content overflowHidden>
          <CodeTabsComponent
            open={open}
            isThereTweaks={isThereTweaks}
            isThereWH={includeWebhook ?? false}
            flow={flow}
            tabs={tabs!}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            tweaks={{
              tweaksList,
              buildTweaks: buildTweaksByChange,
            }}
            activeTweaks={activeTweaks}
            setActiveTweaks={setActiveTweaks}
            allowExport
          />
        </BaseModal.Content>
      </BaseModal>
    );
  },
);

export default ApiModal;
