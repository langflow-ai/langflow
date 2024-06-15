import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import { ReactNode, forwardRef, useContext, useEffect, useState } from "react";
// import "ace-builds/webpack-resolver";
import { cloneDeep } from "lodash";
import CodeTabsComponent from "../../components/codeTabsComponent";
import IconComponent from "../../components/genericIconComponent";
import { EXPORT_CODE_DIALOG } from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { useTweaksStore } from "../../stores/tweaksStore";
import { TemplateVariableType } from "../../types/api";
import { uniqueTweakType } from "../../types/components";
import { FlowType } from "../../types/flow/index";
import BaseModal from "../baseModal";
import { buildContent } from "./utils/build-content";
import { buildTweaks } from "./utils/build-tweaks";
import { checkCanBuildTweakObject } from "./utils/check-can-build-tweak-object";
import { getChangesType } from "./utils/get-changes-types";
import { getCurlRunCode, getCurlWebhookCode } from "./utils/get-curl-code";
import { getNodesWithDefaultValue } from "./utils/get-nodes-with-default-value";
import getPythonApiCode from "./utils/get-python-api-code";
import getPythonCode from "./utils/get-python-code";
import { getValue } from "./utils/get-value";
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
    const tweak = useTweaksStore((state) => state.tweak);
    const addTweaks = useTweaksStore((state) => state.setTweak);
    const setTweaksList = useTweaksStore((state) => state.setTweaksList);
    const tweaksList = useTweaksStore((state) => state.tweaksList);

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
    const curl_run_code = getCurlRunCode(
      flow?.id,
      autoLogin,
      tweak,
      flow?.endpoint_name,
    );
    const curl_webhook_code = getCurlWebhookCode(
      flow?.id,
      autoLogin,
      flow?.endpoint_name,
    );
    const pythonCode = getPythonCode(flow?.name, tweak);
    const widgetCode = getWidgetCode(flow?.id, flow?.name, autoLogin);
    const includeWebhook = flow.webhook;
    const tweaksCode = buildTweaks(flow);
    const codesArray = [
      curl_run_code,
      curl_webhook_code,
      pythonApiCode,
      pythonCode,
      widgetCode,
      pythonCode,
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

      filterNodes();

      if (Object.keys(tweaksCode).length > 0) {
        setActiveTab("0");
        setTabs(createTabsArray(codesArray, includeWebhook, true));
      } else {
        setTabs(createTabsArray(codesArray, includeWebhook, true));
      }
    }, [flow["data"]!["nodes"], open]);

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

    async function buildTweakObject(
      tw: string,
      changes: string | string[] | boolean | number | Object[] | Object,
      template: TemplateVariableType,
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
      const curl_code = getCurlRunCode(
        flow?.id,
        autoLogin,
        cloneTweak,
        flow?.endpoint_name,
      );
      const pythonCode = getPythonCode(flow?.name, cloneTweak);
      const widgetCode = getWidgetCode(flow?.id, flow?.name, autoLogin);

      if (tabs && tabs?.length > 0) {
        tabs![0].code = curl_code;
        tabs![1].code = pythonApiCode;
        tabs![2].code = pythonCode;
        tabs![3].code = widgetCode;
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
            flow={flow}
            tabs={tabs!}
            activeTab={activeTab}
            setActiveTab={setActiveTab}
            tweaks={{
              tweak,
              tweaksList,
              buildContent,
              buildTweakObject,
              getValue,
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
