import { IconCheck, IconClipboard, IconDownload } from "@tabler/icons-react";
import {
  XMarkIcon,
  CommandLineIcon,
  CodeBracketSquareIcon,
} from "@heroicons/react/24/outline";
import { Fragment, useContext, useRef, useState } from "react";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../../components/ui/dialog";
import { Button } from "../../components/ui/button";
import { FlowType } from "src/types/flow";
import { getCurlCode, getPythonApiCode, getPythonCode } from "../../constants";
import { EXPORT_CODE_DIALOG } from "../../constants";

export default function ApiModal({ flow }: { flow: FlowType }) {
  const [open, setOpen] = useState(true);
  const { dark } = useContext(darkContext);
  const { closePopUp } = useContext(PopUpContext);
  const [activeTab, setActiveTab] = useState(0);
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

  const pythonApiCode = getPythonApiCode(flow.id);

  const curl_code = getCurlCode(flow.id);
  const pythonCode = getPythonCode(flow.name);

  const tabs = [
    {
      name: "Python API",
      mode: "python",
      image:
        "https://images.squarespace-cdn.com/content/v1/5df3d8c5d2be5962e4f87890/1628015119369-OY4TV3XJJ53ECO0W2OLQ/Python+API+Training+Logo.png?format=1000w",
      code: pythonApiCode,
    },
    {
      name: "cURL",
      mode: "bash",
      image: "https://cdn-icons-png.flaticon.com/512/631/631558.png",
      code: curl_code,
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
            <CodeBracketSquareIcon
              className="h-6 w-6 text-gray-800 pl-1 dark:text-white"
              aria-hidden="true"
            />
          </DialogTitle>
          <DialogDescription>{EXPORT_CODE_DIALOG}</DialogDescription>
        </DialogHeader>

        <div className="flex flex-col h-full w-full ">
          <div className="flex px-5 z-10">
            {tabs.map((tab, index) => (
              <button
                key={index}
                onClick={() => {
                  setActiveTab(index);
                }}
                className={
                  "p-1.5 rounded-t-lg w-44 border border-b-0 border-gray-300 dark:border-gray-700 dark:text-gray-300 -mr-px flex justify-center items-center gap-4 " +
                  (activeTab === index
                    ? " bg-white dark:bg-gray-800"
                    : "bg-muted dark:bg-gray-900")
                }
              >
                {tab.name}
                <img src={tab.image} className="w-[23px]" />
              </button>
            ))}
          </div>
          <div className=" overflow-hidden px-4 sm:p-4 sm:pb-0 sm:pt-0 w-full h-full rounded-lg border-gray-200 border-[1px] bg-muted dark:bg-gray-800">
            <div className="items-center mb-2">
              <div className="float-right">
                <button
                  className="flex gap-1.5 items-center rounded bg-none p-1 text-xs text-gray-500 dark:text-gray-300"
                  onClick={copyToClipboard}
                >
                  {isCopied ? (
                    <IconCheck size={18} />
                  ) : (
                    <IconClipboard size={18} />
                  )}
                  {isCopied ? "Copied!" : "Copy code"}
                </button>
              </div>
            </div>
            <SyntaxHighlighter
              className="h-[350px] w-full"
              language={tabs[activeTab].mode}
              style={oneDark}
              customStyle={{ margin: 0 }}
            >
              {tabs[activeTab].code}
            </SyntaxHighlighter>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
