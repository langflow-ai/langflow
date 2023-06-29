import { useContext, useState } from "react";
import { PopUpContext } from "../../contexts/popUpContext";
import "ace-builds/src-noconflict/mode-python";
import "ace-builds/src-noconflict/theme-github";
import "ace-builds/src-noconflict/theme-twilight";
import "ace-builds/src-noconflict/ext-language_tools";
// import "ace-builds/webpack-resolver";
import { darkContext } from "../../contexts/darkContext";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/cjs/styles/prism";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { FlowType } from "../../types/flow/index";
import { getCurlCode, getPythonApiCode, getPythonCode } from "../../constants";
import { EXPORT_CODE_DIALOG } from "../../constants";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { Check, Clipboard, Code2 } from "lucide-react";

export default function ApiModal({ flow }: { flow: FlowType }) {
  const [open, setOpen] = useState(true);
  const { dark } = useContext(darkContext);
  const { closePopUp } = useContext(PopUpContext);
  const [activeTab, setActiveTab] = useState("0");
  const [isCopied, setIsCopied] = useState<Boolean>(false);

  const copyToClipboard = () => {
    if (!navigator.clipboard || !navigator.clipboard.writeText) {
      return;
    }

    navigator.clipboard.writeText(tabs[activeTab].code).then(() => {
      setIsCopied(true);

      setTimeout(() => {
        setIsCopied(false);
      }, 2000);
    });
  };
  function setModalOpen(x: boolean) {
    setOpen(x);
    if (x === false) {
      closePopUp();
    }
  }

  const pythonApiCode = getPythonApiCode(flow);

  const curl_code = getCurlCode(flow);
  const pythonCode = getPythonCode(flow);

  const tabs = [
    {
      name: "cURL",
      mode: "bash",
      image: "https://curl.se/logo/curl-symbol-transparent.png",
      code: curl_code,
    },
    {
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      code: pythonApiCode,
    },
    {
      name: "Python Code",
      mode: "python",
      image: "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
      code: pythonCode,
    },
  ];
  return (
    <Dialog open={true} onOpenChange={setModalOpen}>
      <DialogTrigger></DialogTrigger>
      <DialogContent className="lg:max-w-[800px] sm:max-w-[600px] h-[580px]">
        <DialogHeader>
          <DialogTitle className="flex items-center">
            <span className="pr-2">Code</span>
            <Code2
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{EXPORT_CODE_DIALOG}</DialogDescription>
        </DialogHeader>

        <Tabs
          defaultValue={"0"}
          className="w-full h-full overflow-hidden text-center bg-muted rounded-md border"
          onValueChange={(value) => setActiveTab(value)}
        >
          <div className="flex items-center justify-between px-2">
            <TabsList>
              {tabs.map((tab, index) => (
                <TabsTrigger key={index} value={index.toString()}>
                  {tab.name}
                </TabsTrigger>
              ))}
            </TabsList>
            <div className="float-right">
              <button
                className="flex gap-1.5 items-center rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
                onClick={copyToClipboard}
              >
                {isCopied ? <Check size={18} /> : <Clipboard size={15} />}
                {isCopied ? "Copied!" : "Copy code"}
              </button>
            </div>
          </div>

          {tabs.map((tab, index) => (
            <TabsContent
              value={index.toString()}
              className="overflow-hidden w-full h-full px-4 pb-4 -mt-1"
            >
              <SyntaxHighlighter
                className="h-[400px] w-full overflow-auto"
                language={tab.mode}
                style={oneDark}
              >
                {tab.code}
              </SyntaxHighlighter>
            </TabsContent>
          ))}
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
