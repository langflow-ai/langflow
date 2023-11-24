import "ace-builds/src-noconflict/ext-language_tools";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import {
  ReactNode,
  forwardRef,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
// import "ace-builds/webpack-resolver";
import CodeTabsComponent from "../../components/codeTabsComponent";
import IconComponent from "../../components/genericIconComponent";
import {
  EXPORT_CODE_DIALOG,
  LANGFLOW_SUPPORTED_TYPES,
} from "../../constants/constants";
import { AuthContext } from "../../contexts/authContext";
import { FlowsContext } from "../../contexts/flowsContext";
import { TemplateVariableType } from "../../types/api";
import { tweakType, uniqueTweakType } from "../../types/components";
import { FlowType, NodeType } from "../../types/flow/index";
import { buildTweaks, convertArrayToObj } from "../../utils/reactflowUtils";
import {
  getCurlCode,
  getPythonApiCode,
  getPythonCode,
  getWidgetCode,
  tabsArray,
} from "../../utils/utils";
import BaseModal from "../baseModal";

const ApiModal = forwardRef(
  (
    {
      flow,
      children,
    }: {
      flow: FlowType;
      children: ReactNode;
    },
    ref
  ) => {
    const { autoLogin } = useContext(AuthContext);
    const [open, setOpen] = useState(false);
    const [activeTab, setActiveTab] = useState("0");
    const tweak = useRef<tweakType>([]);
    const tweaksList = useRef<string[]>([]);
    const { setTweak, getTweak, tabsState } = useContext(FlowsContext);
    const pythonApiCode = getPythonApiCode(
      flow,
      autoLogin,
      tweak.current,
      tabsState
    );
    const curl_code = getCurlCode(flow, autoLogin, tweak.current, tabsState);
    const pythonCode = getPythonCode(flow, tweak.current, tabsState);
    const widgetCode = getWidgetCode(flow, autoLogin, tabsState);
    const tweaksCode = buildTweaks(flow);
    const codesArray = [
      curl_code,
      pythonApiCode,
      pythonCode,
      widgetCode,
      pythonCode,
    ];
    const [tabs, setTabs] = useState(tabsArray(codesArray, 0));

    function startState() {
      tweak.current = [];
      setTweak([]);
      tweaksList.current = [];
    }

    useEffect(() => {
      if (flow["data"]!["nodes"].length == 0) {
        startState();
      } else {
        tweak.current = [];
        const t = buildTweaks(flow);
        tweak.current.push(t);
      }

      filterNodes();

      if (Object.keys(tweaksCode).length > 0) {
        setActiveTab("0");
        setTabs(tabsArray(codesArray, 1));
      } else {
        setTabs(tabsArray(codesArray, 1));
      }
    }, [flow["data"]!["nodes"], open]);

    function filterNodes() {
      let arrNodesWithValues: string[] = [];

      flow["data"]!["nodes"].forEach((node) => {
        Object.keys(node["data"]["node"]["template"])
          .filter(
            (templateField) =>
              templateField.charAt(0) !== "_" &&
              node.data.node.template[templateField].show &&
              LANGFLOW_SUPPORTED_TYPES.has(
                node.data.node.template[templateField].type
              )
          )
          .map((n, i) => {
            arrNodesWithValues.push(node["id"]);
          });
      });

      tweaksList.current = arrNodesWithValues.filter((value, index, self) => {
        return self.indexOf(value) === index;
      });
    }
    function buildTweakObject(
      tw: string,
      changes: string | string[] | boolean | number | Object[] | Object,
      template: TemplateVariableType
    ) {
      if (typeof changes === "string" && template.type === "float") {
        changes = parseFloat(changes);
      }
      if (typeof changes === "string" && template.type === "int") {
        changes = parseInt(changes);
      }
      if (template.list === true && Array.isArray(changes)) {
        changes = changes?.filter((x) => x !== "");
      }

      if (template.type === "dict" && Array.isArray(changes)) {
        changes = convertArrayToObj(changes);
      }

      if (template.type === "NestedDict") {
        changes = JSON.stringify(changes);
      }

      const existingTweak = tweak.current.find((element) =>
        element.hasOwnProperty(tw)
      );

      if (existingTweak) {
        existingTweak[tw][template["name"]!] = changes as string;

        if (existingTweak[tw][template["name"]!] == template.value) {
          tweak.current.forEach((element) => {
            if (element[tw] && Object.keys(element[tw])?.length === 0) {
              tweak.current = tweak.current.filter((obj) => {
                const prop = obj[Object.keys(obj)[0]].prop;
                return prop !== undefined && prop !== null && prop !== "";
              });
            }
          });
        }
      } else {
        const newTweak = {
          [tw]: {
            [template["name"]!]: changes,
          },
        } as uniqueTweakType;
        tweak.current.push(newTweak);
      }

      const pythonApiCode = getPythonApiCode(
        flow,
        autoLogin,
        tweak.current,
        tabsState
      );
      const curl_code = getCurlCode(flow, autoLogin, tweak.current, tabsState);
      const pythonCode = getPythonCode(flow, tweak.current, tabsState);
      const widgetCode = getWidgetCode(flow, autoLogin, tabsState);

      tabs![0].code = curl_code;
      tabs![1].code = pythonApiCode;
      tabs![2].code = pythonCode;
      tabs![3].code = widgetCode;

      setTweak(tweak.current);
    }

    function buildContent(value: string) {
      const htmlContent = (
        <div className="w-[200px]">
          <span>{value != null && value != "" ? value : "None"}</span>
        </div>
      );
      return htmlContent;
    }

    function getValue(
      value: string,
      node: NodeType,
      template: TemplateVariableType
    ) {
      let returnValue = value ?? "";

      if (getTweak.length > 0) {
        for (const obj of getTweak) {
          Object.keys(obj).forEach((key) => {
            const value = obj[key];
            if (key == node["id"]) {
              Object.keys(value).forEach((key) => {
                if (key == template["name"]) {
                  returnValue = value[key];
                }
              });
            }
          });
        }
      } else {
        return value ?? "";
      }
      return returnValue;
    }

    return (
      <BaseModal open={open} setOpen={setOpen}>
        <BaseModal.Trigger asChild>{children}</BaseModal.Trigger>
        <BaseModal.Header description={EXPORT_CODE_DIALOG}>
          <span className="pr-2">Code</span>
          <IconComponent
            name="Code2"
            className="h-6 w-6 pl-1 text-gray-800 dark:text-white"
            aria-hidden="true"
          />
        </BaseModal.Header>
        <BaseModal.Content>
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
          />
        </BaseModal.Content>
      </BaseModal>
    );
  }
);

export default ApiModal;
