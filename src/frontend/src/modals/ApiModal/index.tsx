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
import { Code2 } from "lucide-react";
import CodeTabsComponent from "../../components/codeTabsComponent";
import {
  EXPORT_CODE_DIALOG,
  getCurlCode,
  getPythonApiCode,
  getPythonCode,
} from "../../constants";
import { TabsContext } from "../../contexts/tabsContext";
import { FlowType } from "../../types/flow/index";
import { buildTweaks } from "../../utils";
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
    const [open, setOpen] = useState(false);
    const [activeTab, setActiveTab] = useState("0");
    const tweak = useRef([]);
    const tweaksList = useRef([]);
    const { setTweak, getTweak, tabsState } = useContext(TabsContext);
    const pythonApiCode = getPythonApiCode(flow, tweak.current, tabsState);
    const curl_code = getCurlCode(flow, tweak.current, tabsState);
    const pythonCode = getPythonCode(flow, tweak.current, tabsState);
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
        ]);
      }
    }, [flow["data"]["nodes"], open]);

    function filterNodes() {
      let arrNodesWithValues = [];

      flow["data"]["nodes"].forEach((t) => {
        Object.keys(t["data"]["node"]["template"])
          .filter(
            (n) =>
              n.charAt(0) !== "_" &&
              t.data.node.template[n].show &&
              (t.data.node.template[n].type === "str" ||
                t.data.node.template[n].type === "bool" ||
                t.data.node.template[n].type === "float" ||
                t.data.node.template[n].type === "code" ||
                t.data.node.template[n].type === "prompt" ||
                t.data.node.template[n].type === "file" ||
                t.data.node.template[n].type === "int")
          )
          .map((n, i) => {
            arrNodesWithValues.push(t["id"]);
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

      const pythonApiCode = getPythonApiCode(flow, tweak.current);
      const curl_code = getCurlCode(flow, tweak.current);
      const pythonCode = getPythonCode(flow, tweak.current);

      tabs[0].code = curl_code;
      tabs[1].code = pythonApiCode;
      tabs[2].code = pythonCode;

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
      <BaseModal open={open} setOpen={setOpen}>
        <BaseModal.Trigger>{children}</BaseModal.Trigger>
        <BaseModal.Header description={EXPORT_CODE_DIALOG}>
          <span className="pr-2">Code</span>
          <Code2
            strokeWidth={1.5}
            className="h-6 w-6 pl-1 text-primary "
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
