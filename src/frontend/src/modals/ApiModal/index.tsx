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
import { EXPORT_CODE_DIALOG } from "../../constants/constants";
import { TabsContext } from "../../contexts/tabsContext";
import { FlowType } from "../../types/flow/index";
import { buildTweaks } from "../../utils/reactflowUtils";
import {
  getCurlCode,
  getPythonApiCode,
  getPythonCode,
  getWidgetCode,
} from "../../utils/utils";
import BaseModal from "../baseModal";

const ApiModal = forwardRef(
  (
    {
      flow,
      children,
      disable,
    }: {
      flow: FlowType;
      children: ReactNode;
      disable: boolean;
    },
    ref
  ) => {
    const [open, setOpen] = useState(false);
    const [activeTab, setActiveTab] = useState("0");
    const tweak = useRef([]);
    const tweaksList = useRef([]);
    const { setTweak, getTweak, tabsState } = useContext(TabsContext);
    const pythonApiCode = getPythonApiCode(flow, tweak.current, tabsState);
    const curl_code = getCurlCode(flow, tweak.current, tabsState);
    const pythonCode = getPythonCode(flow, tweak.current, tabsState);
    const widgetCode = getWidgetCode(flow, tabsState);
    const tweaksCode = buildTweaks(flow);
    const [tabs, setTabs] = useState([
      {
        name: "cURL",
        mode: "bash",
        image: "https://curl.se/logo/curl-symbol-transparent.png",
        language: "sh",
        code: curl_code,
      },
      {
        name: "Python API",
        mode: "python",
        image:
          "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
        language: "py",
        code: pythonApiCode,
      },
      {
        name: "Python Code",
        mode: "python",
        image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
        language: "py",
        code: pythonCode,
      },
      {
        name: "Chat Widget HTML",
        description:
          "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://docs.langflow.org/guidelines/widget'>documentation</a>.",
        mode: "html",
        image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
        language: "py",
        code: widgetCode,
      },
    ]);

    function startState() {
      tweak.current = [];
      setTweak([]);
      tweaksList.current = [];
    }

    useEffect(() => {
      if (flow["data"]["nodes"].length == 0) {
        startState();
      } else {
        tweak.current = [];
        const t = buildTweaks(flow);
        tweak.current.push(t);
      }

      filterNodes();

      if (Object.keys(tweaksCode).length > 0) {
        setActiveTab("0");
        setTabs([
          {
            name: "cURL",
            mode: "bash",
            image: "https://curl.se/logo/curl-symbol-transparent.png",
            language: "sh",
            code: curl_code,
          },
          {
            name: "Python API",
            mode: "python",
            image:
              "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
            language: "py",
            code: pythonApiCode,
          },
          {
            name: "Python Code",
            mode: "python",
            language: "py",
            image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
            code: pythonCode,
          },
          {
            name: "Chat Widget HTML",
            description:
              "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://docs.langflow.org/guidelines/widget'>documentation</a>.",
            mode: "html",
            image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
            language: "py",
            code: widgetCode,
          },
          {
            name: "Tweaks",
            mode: "python",
            image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
            language: "py",
            code: pythonCode,
          },
        ]);
      } else {
        setTabs([
          {
            name: "cURL",
            mode: "bash",
            image: "https://curl.se/logo/curl-symbol-transparent.png",
            language: "sh",
            code: curl_code,
          },
          {
            name: "Python API",
            mode: "python",
            image:
              "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
            language: "py",
            code: pythonApiCode,
          },
          {
            name: "Python Code",
            mode: "python",
            image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
            language: "py",
            code: pythonCode,
          },
          {
            name: "Chat Widget HTML",
            description:
              "Insert this code anywhere in your &lt;body&gt; tag. To use with react and other libs, check our <a class='link-color' href='https://docs.langflow.org/guidelines/widget'>documentation</a>.",
            mode: "html",
            image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
            language: "py",
            code: widgetCode,
          },
        ]);
      }
    }, [flow["data"]["nodes"], open]);

    function filterNodes() {
      let arrNodesWithValues = [];

      flow["data"]["nodes"].forEach((node) => {
        Object.keys(node["data"]["node"]["template"])
          .filter(
            (templateField) =>
              templateField.charAt(0) !== "_" &&
              node.data.node.template[templateField].show &&
              (node.data.node.template[templateField].type === "str" ||
                node.data.node.template[templateField].type === "bool" ||
                node.data.node.template[templateField].type === "float" ||
                node.data.node.template[templateField].type === "code" ||
                node.data.node.template[templateField].type === "prompt" ||
                node.data.node.template[templateField].type === "file" ||
                node.data.node.template[templateField].type === "int")
          )
          .map((n, i) => {
            arrNodesWithValues.push(node["id"]);
          });
      });

      tweaksList.current = arrNodesWithValues.filter((value, index, self) => {
        return self.indexOf(value) === index;
      });
    }
    function buildTweakObject(tw, changes, template) {
      if (template.type === "float") {
        changes = parseFloat(changes);
      }
      if (template.type === "int") {
        changes = parseInt(changes);
      }
      if (template.list === true && Array.isArray(changes)) {
        changes = changes?.filter((x) => x !== "");
      }

      const existingTweak = tweak.current.find((element) =>
        element.hasOwnProperty(tw)
      );

      if (existingTweak) {
        existingTweak[tw][template["name"]] = changes;

        if (existingTweak[tw][template["name"]] == template.value) {
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
            [template["name"]]: changes,
          },
        };
        tweak.current.push(newTweak);
      }

      const pythonApiCode = getPythonApiCode(flow, tweak.current, tabsState);
      const curl_code = getCurlCode(flow, tweak.current, tabsState);
      const pythonCode = getPythonCode(flow, tweak.current, tabsState);
      const widgetCode = getWidgetCode(flow, tabsState);

      tabs[0].code = curl_code;
      tabs[1].code = pythonApiCode;
      tabs[2].code = pythonCode;
      tabs[3].code = widgetCode;

      setTweak(tweak.current);
    }

    function buildContent(value) {
      const htmlContent = (
        <div className="w-[200px]">
          <span>{value != null && value != "" ? value : "None"}</span>
        </div>
      );
      return htmlContent;
    }

    function getValue(value, node, template) {
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
      <BaseModal open={open} setOpen={setOpen} disable={disable}>
        <BaseModal.Trigger>{children}</BaseModal.Trigger>
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
            tabs={tabs}
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
